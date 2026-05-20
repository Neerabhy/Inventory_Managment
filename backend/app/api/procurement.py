from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.api.deps import get_db, get_current_user, RoleChecker
from app.models.auth import User
from app.models.inventory import Product
from app.models.procurement import Supplier, ProductSupplier, PurchaseOrder, ProcurementDecision
from app.schemas.procurement import ProcurementRecommendationResponse, PurchaseOrderCreate, PurchaseOrderResponse
from app.ml.vendor_ranker import vendor_ranker_engine

router = APIRouter(prefix="/procurement", tags=["Procurement Optimization"])

@router.get("/recommendations/{product_id}", response_model=ProcurementRecommendationResponse)
async def get_vendor_recommendations(
    product_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Invokes the Vendor Ranking ML model to find the best supplier for a given SKU."""
    # Fetch Product
    prod_result = await db.execute(select(Product).where(Product.id == product_id))
    product = prod_result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Fetch available suppliers for this product
    sup_result = await db.execute(
        select(ProductSupplier, Supplier)
        .join(Supplier)
        .where(ProductSupplier.product_id == product_id)
    )
    suppliers_data = sup_result.all()

    # Format data for ML Engine
    vendor_options = [
        {
            "supplier_id": s.id,
            "supplier_name": s.supplier_name,
            "supplier_price": ps.supplier_price,
            "lead_time_days": ps.lead_time_days,
            "quality_level": ps.quality_level,
            "reliability": s.reliability
        }
        for ps, s in suppliers_data
    ]

    # Run multi-criteria scoring
    ranked_vendors = vendor_ranker_engine.predict(vendor_options)

    return ProcurementRecommendationResponse(
        product_id=product.id,
        product_name=product.product_name,
        current_stock=0, # In production, pull from Inventory table
        suggested_reorder_quantity=100,
        rankings=ranked_vendors
    )

@router.post("/orders", response_model=PurchaseOrderResponse)
async def create_purchase_order(
    po_in: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["SYS_ADMIN", "PROCUREMENT_MGR"]))
):
    """Creates a PO and logs if the user manually overrode the AI's top recommendation."""
    import uuid
    
    # 1. Create the PO
    new_po = PurchaseOrder(
        po_number=f"PO-2026-{uuid.uuid4().hex[:6].upper()}",
        product_id=po_in.product_id,
        supplier_id=po_in.supplier_id,
        warehouse_id=po_in.warehouse_id,
        quantity_ordered=po_in.quantity_ordered,
        procurement_cost=po_in.procurement_cost,
        delivery_deadline=po_in.delivery_deadline
    )
    db.add(new_po)
    await db.commit()
    await db.refresh(new_po)

    # 2. Log the Procurement Decision (Tracking Human vs AI Overrides)
    decision = ProcurementDecision(
        purchase_order_id=new_po.id,
        system_recommended_supplier_id=po_in.supplier_id, # In full prod, store actual ML #1 here
        override_flag=po_in.override_flag,
        override_reason=po_in.override_reason,
        user_id=current_user.id
    )
    db.add(decision)
    await db.commit()

    return new_po