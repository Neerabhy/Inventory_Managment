"""
api/inventory.py — Inventory routes: products, stock levels, movements ledger, ABC analysis, KPIs.
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .deps import get_current_user, get_db, require_procurement
from ..core.config import settings
from ..ml.dynamic_pricing import DynamicPricingModel
from ..ml.stockout import StockoutPredictor
from ..models.analytics import KpiDefinition, Sale
from ..models.auth import User
from ..models.inventory import Inventory, InventoryMovement, Product, ProductSupplier
from ..models.predictions import InventoryReorderPlan
from ..models.procurement import PurchaseOrder
from ..services.prediction_service import consume_vendor_recommendations
from ..schemas.inventory import (
    AbcAnalysisOut,
    AbcItem,
    InventoryOut,
    InventoryUpdate,
    KpiDefinitionOut,
    MovementCreate,
    MovementOut,
    ProductCreate,
    ProductOut,
    ProductSupplierCreate,
    ProductSupplierOut,
    ProductUpdate,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


async def _supplier_order_terms(
    db: AsyncSession,
    product_id: int,
    supplier_id: int,
    product: Product,
) -> tuple[float, Optional[str]]:
    mapping = await db.scalar(
        select(ProductSupplier).where(
            ProductSupplier.product_id == product_id,
            ProductSupplier.supplier_id == supplier_id,
        )
    )
    unit_cost = float(
        mapping.supplier_price
        if mapping and mapping.supplier_price is not None
        else product.manufacturing_cost or 0
    )
    lead_days = int(mapping.lead_time_days or 0) if mapping else 0
    expected_delivery = (
        (datetime.datetime.utcnow() + datetime.timedelta(days=lead_days)).date().isoformat()
        if lead_days > 0
        else None
    )
    return unit_cost, expected_delivery


# ── Stock Alert Schema ─────────────────────────────────────────────────
class StockAlertOut(BaseModel):
    product_id: int
    product_name: str
    sku: str
    category: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    selling_price: Optional[float] = None
    current_stock: int
    safety_stock: int
    reorder_point: int
    warehouse_city: Optional[str] = None
    warehouse_id: int
    incoming_qty: int          # total pending PO quantity
    has_pending_order: bool
    pending_order_id: Optional[int] = None
    pending_order_qty: Optional[int] = None
    pending_order_value: Optional[float] = None
    model_config = {"from_attributes": True}


# ── Stock Alerts Endpoint ──────────────────────────────────────────────
@router.get("/stock-alerts", response_model=List[StockAlertOut])
async def get_stock_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Return all inventory positions at or below reorder point,
    enriched with incoming_qty from pending purchase orders.
    Reads ONLY from inventory, products, and purchase_orders — never writes.
    """
    PENDING_STATUSES = ("Draft", "Pending", "Ordered", "Confirmed", "Approved")

    # All low-stock inventory rows
    inv_result = await db.execute(
        select(Inventory, Product)
        .join(Product, Inventory.product_id == Product.id)
        .order_by(Inventory.current_stock.asc())
    )
    rows = inv_result.all()

    alerts: List[StockAlertOut] = []
    for inv, prod in rows:
        plan = await db.scalar(
            select(InventoryReorderPlan).where(
                InventoryReorderPlan.product_id == prod.id,
                InventoryReorderPlan.warehouse_id == inv.warehouse_id,
            )
        )
        reorder_threshold = (
            plan.recommended_reorder_point if plan else inv.reorder_point
        )
        if inv.current_stock > reorder_threshold:
            continue
        # Sum pending PO quantities for this exact product + warehouse.
        po_qty_result = await db.execute(
            select(
                func.coalesce(func.sum(PurchaseOrder.quantity), 0),
                PurchaseOrder.id,
                PurchaseOrder.quantity,
            )
            .where(PurchaseOrder.product_id == prod.id)
            .where(PurchaseOrder.warehouse_id == inv.warehouse_id)
            .where(PurchaseOrder.status.in_(PENDING_STATUSES))
            .order_by(PurchaseOrder.id.desc())
            .limit(1)
        )
        po_row = po_qty_result.one_or_none()

        # Total incoming from pending POs for this inventory row's warehouse only.
        total_incoming_result = await db.execute(
            select(
                func.coalesce(func.sum(PurchaseOrder.quantity), 0),
                func.coalesce(func.sum(PurchaseOrder.quantity * PurchaseOrder.unit_cost), 0),
            )
            .where(PurchaseOrder.product_id == prod.id)
            .where(PurchaseOrder.warehouse_id == inv.warehouse_id)
            .where(PurchaseOrder.status.in_(PENDING_STATUSES))
        )
        incoming_row = total_incoming_result.one()
        incoming_qty = int(incoming_row[0] or 0)
        pending_value = float(incoming_row[1] or 0)
        has_pending = incoming_qty > 0
        pending_po_id = int(po_row[1]) if po_row and po_row[1] else None
        pending_po_qty = int(po_row[2]) if po_row and po_row[2] else None

        cities = {1: "Delhi", 2: "Mumbai", 3: "Bangalore", 4: "Jaipur", 5: "Kolkata"}
        alerts.append(StockAlertOut(
            product_id=prod.id,
            product_name=prod.product_name,
            sku=prod.sku or "",
            category=prod.category,
            brand=prod.brand,
            image_url=prod.image_url,
            selling_price=prod.selling_price,
            current_stock=int(inv.current_stock),
            safety_stock=int(inv.safety_stock),
            reorder_point=int(reorder_threshold),
            warehouse_city=cities.get(inv.warehouse_id, "Unknown"),
            warehouse_id=inv.warehouse_id,
            incoming_qty=incoming_qty,
            has_pending_order=has_pending,
            pending_order_id=pending_po_id,
            pending_order_qty=pending_po_qty,
            pending_order_value=pending_value,
        ))

    return alerts



# ── Products ─────────────────────────────────────────────────────────
@router.get("/products", response_model=List[ProductOut])
async def list_products(
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or SKU"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all products with optional filters for category, active state, and text search."""
    q = select(Product).options(selectinload(Product.inventory_records))
    if category:
        q = q.where(Product.category == category)
    if is_active is True:
        q = q.where(Product.status != "Discontinued")
    elif is_active is False:
        q = q.where(Product.status == "Discontinued")
    if search:
        pattern = f"%{search}%"
        q = q.where(Product.product_name.ilike(pattern) | Product.sku.ilike(pattern))
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Create a new product SKU.  The database trigger will auto-format product_code.
    Also creates an Inventory record initialised to zero stock.
    """
    product = Product(**payload.model_dump())
    db.add(product)
    await db.flush()  # obtain product.id

    # Initialise inventory record
    inventory = Inventory(product_id=product.id)
    db.add(inventory)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Fetch a single product by its primary key."""
    result = await db.execute(
        select(Product).options(selectinload(Product.inventory_records)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    """Partially update a product record."""
    result = await db.execute(
        select(Product).options(selectinload(Product.inventory_records)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


# ── Inventory Stock ──────────────────────────────────────────────────
@router.get("/stock", response_model=List[InventoryOut])
async def list_stock(
    below_reorder: Optional[bool] = Query(None, description="Filter products at/below reorder point"),
    city: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    List real-time stock levels.
    Supports filtering for items at/below their reorder threshold (restock alerts).
    """
    q = select(Inventory).join(Product, Inventory.product_id == Product.id)
    if below_reorder:
        # Use actual mapped ORM columns — NOT Python @property decorators
        q = q.where(Inventory.current_stock <= Inventory.reorder_point)
    # warehouse_city is not a column, filtering by city is disabled or needs join if applicable
    # if city:
    #     q = q.where(Inventory.warehouse_city == city)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/stock/{product_id}", response_model=InventoryOut)
async def get_stock(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Fetch current stock level for a specific product."""
    result = await db.execute(select(Inventory).where(Inventory.product_id == product_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory record not found.")
    return inv


@router.patch("/stock/{product_id}", response_model=InventoryOut)
async def update_stock(
    product_id: int,
    payload: InventoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Update stock levels.  Validates warehouse_city against serviceable_cities.
    Writes an ADJUSTMENT movement to the audit ledger.
    """
    if payload.warehouse_city and payload.warehouse_city not in settings.serviceable_cities:
        raise HTTPException(
            status_code=400,
            detail=f"City '{payload.warehouse_city}' is not in the serviceable cities list: {settings.serviceable_cities}",
        )

    result = await db.execute(select(Inventory).where(Inventory.product_id == product_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory record not found.")

    stock_before = inv.quantity_on_hand
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)

    stock_after = inv.quantity_on_hand
    if stock_before != stock_after:
        movement = InventoryMovement(
            product_id=product_id,
            movement_type="ADJUSTMENT",
            quantity_delta=stock_after - stock_before,
            stock_before=stock_before,
            stock_after=stock_after,
            performed_by=current_user.username,
            note="Manual stock adjustment via API",
        )
        db.add(movement)

    await db.commit()
    await db.refresh(inv)
    return inv


# ── ML: Stockout Risk ────────────────────────────────────────────────
@router.get("/stock/{product_id}/stockout-risk")
async def get_stockout_risk(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Run the XGBoost StockoutPredictor model on a product's current inventory state.
    Returns stockout_risk (0/1), stockout_probability, and risk_label (HIGH/LOW).
    """
    

    result = await db.execute(
        select(Inventory, Product)
        .join(Product, Inventory.product_id == Product.id)
        .where(Inventory.product_id == product_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Inventory record not found.")

    inv, prod = row

    # Get total sales for this product
    sales_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(Sale.quantity), 0)).where(Sale.product_id == product_id)
    )
    total_sales = float(sales_result.scalar_one() or 0)

    predictor = StockoutPredictor()
    prediction = predictor.predict(
        product_id=product_id,
        current_stock=float(inv.current_stock or 0),
        safety_stock=float(inv.safety_stock or 0),
        inventory_turnover=float(inv.inventory_turnover or 0),
        category=prod.category or "Unknown",
        brand=prod.brand or "Unknown",
        selling_price=float(prod.selling_price or 0),
        warehouse_city="Delhi",  # default; real city via warehouse join if needed
        total_sales=total_sales,
    )
    return prediction


# ── ML: Dynamic Pricing ───────────────────────────────────────────────
@router.get("/products/{product_id}/pricing")
async def get_dynamic_pricing(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Run the XGBoost DynamicPricingModel to recommend an optimal selling price
    based on inventory levels, demand velocity, and product attributes.
    """
    

    result = await db.execute(
        select(Product, Inventory)
        .outerjoin(Inventory, Inventory.product_id == Product.id)
        .where(Product.id == product_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found.")

    prod, inv = row

    # Get total units sold and total orders
    sales_result = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(Sale.quantity), 0),
            sqlfunc.coalesce(sqlfunc.count(Sale.id), 0),
        ).where(Sale.product_id == product_id)
    )
    units_row = sales_result.one()
    total_units_sold = float(units_row[0] or 0)
    total_orders     = float(units_row[1] or 0)

    model = DynamicPricingModel()
    recommendation = model.predict(
        category=prod.category or "Unknown",
        brand=prod.brand or "Unknown",
        manufacturing_cost=float(prod.manufacturing_cost or 0),
        current_price=float(prod.selling_price or 0),
        current_stock=float(inv.current_stock if inv else 0),
        safety_stock=float(inv.safety_stock if inv else 0),
        inventory_turnover=float(inv.inventory_turnover if inv else 0),
        total_units_sold=total_units_sold,
        total_orders=total_orders,
    )
    return {
        "product_id":   product_id,
        "product_name": prod.product_name,
        **recommendation,
    }


# ── Movements Ledger ─────────────────────────────────────────────────
@router.get("/movements", response_model=List[MovementOut])
async def list_movements(
    product_id: Optional[int] = Query(None),
    movement_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Paginated audit ledger of all inventory movements."""
    q = select(InventoryMovement).order_by(InventoryMovement.created_at.desc())
    if product_id:
        q = q.where(InventoryMovement.product_id == product_id)
    if movement_type:
        q = q.where(InventoryMovement.movement_type == movement_type)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/movements", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
async def record_movement(
    payload: MovementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Manually record an inventory movement and atomically update stock levels.
    Validates the product exists and that the resulting stock is non-negative.
    """
    result = await db.execute(select(Inventory).where(Inventory.product_id == payload.product_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory record not found.")

    stock_before = inv.quantity_on_hand
    stock_after = stock_before + payload.quantity_delta
    if stock_after < 0:
        raise HTTPException(status_code=400, detail="Movement would result in negative stock.")

    inv.quantity_on_hand = stock_after
    movement = InventoryMovement(
        product_id=payload.product_id,
        movement_type=payload.movement_type,
        quantity_delta=payload.quantity_delta,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_id=payload.reference_id,
        note=payload.note,
        performed_by=current_user.username,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


# ── Product-Supplier Mappings ────────────────────────────────────────
@router.get("/products/{product_id}/suppliers", response_model=List[ProductSupplierOut])
async def list_product_suppliers(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all supplier mappings for a product."""
    result = await db.execute(
        select(ProductSupplier).where(ProductSupplier.product_id == product_id)
    )
    return result.scalars().all()


@router.post("/products/{product_id}/suppliers", response_model=ProductSupplierOut, status_code=201)
async def add_product_supplier(
    product_id: int,
    payload: ProductSupplierCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    """Add a supplier mapping to a product (enforces UNIQUE(product_id, supplier_id))."""
    ps = ProductSupplier(product_id=product_id, **payload.model_dump())
    db.add(ps)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This product-supplier mapping already exists.")
    await db.refresh(ps)
    return ps


# ── Reorder Endpoints ───────────────────────────────────────────────
@router.post("/reorder/{product_id}", response_model=dict, status_code=201)
async def reorder_product(
    product_id: int,
    supplier_id: int = Query(..., description="Supplier ID to order from"),
    warehouse_id: int = Query(1, ge=1, description="Warehouse ID to restock"),
    quantity: int = Query(default=100, ge=1, description="Quantity to order"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Create a purchase order to restock a single low-stock product.
    Requires supplier_id and optional quantity (default 100).
    """
    
    # Validate product exists
    prod = await db.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found.")

    inventory = await db.scalar(
        select(Inventory).where(
            Inventory.product_id == product_id,
            Inventory.warehouse_id == warehouse_id,
        )
    )
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found for this warehouse.")

    unit_cost, expected_delivery = await _supplier_order_terms(db, product_id, supplier_id, prod)

    order = PurchaseOrder(
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        order_date=datetime.datetime.utcnow().isoformat(),
        expected_delivery=expected_delivery,
        quantity=quantity,
        unit_cost=unit_cost,
        status="Draft",
    )
    db.add(order)
    await consume_vendor_recommendations(db, product_id)
    await db.commit()
    await db.refresh(order)
    return {
        "success": True,
        "order_id": order.id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "warehouse_id": warehouse_id,
        "quantity": quantity,
        "status": "Draft",
    }


@router.post("/reorder-all", response_model=dict, status_code=201)
async def reorder_all_low_stock(
    supplier_id: int = Query(..., description="Supplier ID to order from"),
    quantity_per_product: int = Query(default=100, ge=1, description="Quantity per product"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Create purchase orders for ALL products currently at or below reorder point.
    Uses the actual ORM columns (not Python @property decorators) for the filter.
    """
    
    # Use actual mapped columns, not @property decorators
    low_stock_result = await db.execute(
        select(Inventory).join(Product, Inventory.product_id == Product.id)
    )
    inv_rows = low_stock_result.scalars().all()
    low_stock_items = []
    for inv in inv_rows:
        plan = await db.scalar(
            select(InventoryReorderPlan).where(
                InventoryReorderPlan.product_id == inv.product_id,
                InventoryReorderPlan.warehouse_id == inv.warehouse_id,
            )
        )
        threshold = plan.recommended_reorder_point if plan else inv.reorder_point
        if inv.current_stock <= threshold:
            low_stock_items.append(inv)
    if not low_stock_items:
        return {"success": True, "orders_created": 0, "message": "No low-stock products found."}

    created_orders = []
    for inv in low_stock_items:
        prod = await db.get(Product, inv.product_id)
        if not prod:
            continue
        unit_cost, expected_delivery = await _supplier_order_terms(
            db, inv.product_id, supplier_id, prod
        )
        order = PurchaseOrder(
            supplier_id=supplier_id,
            warehouse_id=inv.warehouse_id,
            product_id=inv.product_id,
            order_date=datetime.datetime.utcnow().isoformat(),
            expected_delivery=expected_delivery,
            quantity=quantity_per_product,
            unit_cost=unit_cost,
            status="Draft",
        )
        db.add(order)
        await consume_vendor_recommendations(db, inv.product_id)
        created_orders.append(inv.product_id)

    await db.commit()
    return {
        "success": True,
        "orders_created": len(created_orders),
        "product_ids": created_orders,
        "supplier_id": supplier_id,
        "quantity_per_product": quantity_per_product,
    }


# ── ABC Analysis ─────────────────────────────────────────────────────
@router.get("/abc-analysis", response_model=AbcAnalysisOut)
async def abc_analysis(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Pareto / ABC classification of products by revenue contribution.
    Class A: top 80% cumulative revenue.
    Class B: 80–95% cumulative revenue.
    Class C: remaining 95–100%.
    """
    result = await db.execute(
        select(
            Product.id,
            Product.name,
            Product.product_code,
            func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"),
        )
        .outerjoin(Sale, Sale.product_id == Product.id)
        .group_by(Product.id)
        .order_by(func.sum(Sale.total_amount).desc().nullslast())
    )
    rows = result.all()

    grand_total = sum(float(r.total_revenue) for r in rows) or 1.0
    items: list[AbcItem] = []
    cumulative = 0.0
    for r in rows:
        rev = float(r.total_revenue)
        pct = rev / grand_total * 100
        cumulative += pct
        abc_class = "A" if cumulative <= 80 else ("B" if cumulative <= 95 else "C")
        items.append(AbcItem(
            product_id=r.id,
            product_name=r.name,
            product_code=r.product_code,
            total_revenue=r.total_revenue,
            revenue_pct=round(pct, 2),
            cumulative_pct=round(cumulative, 2),
            abc_class=abc_class,
        ))

    return AbcAnalysisOut(
        items=items,
        total_products=len(items),
        class_a_count=sum(1 for i in items if i.abc_class == "A"),
        class_b_count=sum(1 for i in items if i.abc_class == "B"),
        class_c_count=sum(1 for i in items if i.abc_class == "C"),
    )


# ── KPI Definitions ──────────────────────────────────────────────────
@router.get("/kpis", response_model=List[KpiDefinitionOut])
async def list_kpi_definitions(
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Return KPI definitions for dynamic frontend tooltip cards.
    Optionally filter by category (INVENTORY | PROCUREMENT | LOGISTICS | RETURNS | REVENUE).
    """
    q = select(KpiDefinition)
    if category:
        q = q.where(KpiDefinition.category == category)
    result = await db.execute(q)
    return result.scalars().all()
