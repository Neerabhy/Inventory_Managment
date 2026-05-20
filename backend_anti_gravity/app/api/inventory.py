"""
api/inventory.py — Inventory routes: products, stock levels, movements ledger, ABC analysis, KPIs.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend_anti_gravity.app.api.deps import get_current_user, get_db, require_procurement
from backend_anti_gravity.app.core.config import settings
from backend_anti_gravity.app.models.auth import User
from backend_anti_gravity.app.models.analytics import KpiDefinition, Sale
from backend_anti_gravity.app.models.inventory import Inventory, InventoryMovement, Product, ProductSupplier
from backend_anti_gravity.app.schemas.inventory import (
    AbcAnalysisOut, AbcItem, InventoryOut, InventoryUpdate,
    KpiDefinitionOut, MovementCreate, MovementOut,
    ProductCreate, ProductOut, ProductSupplierCreate, ProductSupplierOut, ProductUpdate,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


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
    if is_active is not None:
        q = q.where(Product.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        q = q.where(Product.name.ilike(pattern) | Product.sku.ilike(pattern))
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
        q = q.where(Inventory.quantity_on_hand <= Product.reorder_point)
    if city:
        q = q.where(Inventory.warehouse_city == city)
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
