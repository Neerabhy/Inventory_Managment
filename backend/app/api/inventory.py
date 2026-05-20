from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.api.deps import get_db, get_current_user, RoleChecker
from app.models.auth import User
from app.models.inventory import Product, Inventory, InventoryMovement
from app.schemas.inventory import ProductCreate, ProductResponse, InventoryResponse, StockAdjustmentRequest

router = APIRouter(prefix="/inventory", tags=["Inventory & SKU Management"])

@router.get("/products", response_model=List[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches the active product catalog."""
    result = await db.execute(select(Product))
    return result.scalars().all()

@router.post("/products", response_model=ProductResponse)
async def create_product(
    product_in: ProductCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["SYS_ADMIN", "PROCUREMENT_MGR"]))
):
    """Creates a new product. Auto-generates a PRD-2026-XXXX code if not provided."""
    db_product = Product(
        product_code=product_in.product_code or f"PRD-2026-{uuid.uuid4().hex[:4].upper()}",
        product_name=product_in.product_name,
        category=product_in.category,
        brand=product_in.brand,
        price=product_in.price,
        size=product_in.size,
        color=product_in.color
    )
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.post("/adjust", status_code=status.HTTP_200_OK)
async def adjust_stock(
    adjustment: StockAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["SYS_ADMIN", "WAREHOUSE_OPS"]))
):
    """Adjusts warehouse stock and writes an immutable ledger entry."""
    # Fetch current inventory record
    result = await db.execute(
        select(Inventory).where(
            Inventory.product_id == adjustment.product_id,
            Inventory.warehouse_id == adjustment.warehouse_id
        )
    )
    inventory = result.scalars().first()
    
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory tracking record not found.")

    stock_before = inventory.current_stock
    stock_after = stock_before + adjustment.quantity
    
    if stock_after < 0:
        raise HTTPException(status_code=400, detail="Adjustment results in negative stock.")

    # Update state
    inventory.current_stock = stock_after

    # Write immutable ledger log
    movement = InventoryMovement(
        product_id=adjustment.product_id,
        warehouse_id=adjustment.warehouse_id,
        movement_type=adjustment.movement_type,
        quantity=adjustment.quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        reference_id=adjustment.reference_id
    )
    db.add(movement)
    await db.commit()
    
    return {"status": "success", "stock_after": stock_after}