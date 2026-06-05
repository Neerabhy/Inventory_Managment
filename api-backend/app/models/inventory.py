"""
models/inventory.py — Product, Inventory, InventoryMovement, ProductSupplier ORM models.
Mapped to the actual inventory-database schema.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Product(Base):
    """Master product / SKU record."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column("product_id", Integer, primary_key=True, autoincrement=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    model_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mrp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selling_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manufacturing_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    return_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    defect_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    warranty_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fragile_flag: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    battery_included: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    launch_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_code: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)

    # Relationships
    inventory_records: Mapped[List["Inventory"]] = relationship("Inventory", back_populates="product")
    product_suppliers: Mapped[List["ProductSupplier"]] = relationship("ProductSupplier", back_populates="product")
    sales: Mapped[List["Sale"]] = relationship("Sale", back_populates="product")  # type: ignore
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="product")  # type: ignore
    returns: Mapped[List["Return"]] = relationship("Return", back_populates="product")  # type: ignore

    # Convenience properties for frontend compatibility
    @property
    def name(self) -> str:
        return self.product_name

    @property
    def unit_price(self) -> Optional[float]:
        return self.selling_price or self.mrp

    @property
    def cost_price(self) -> Optional[float]:
        return self.manufacturing_cost

    @property
    def is_fragile(self) -> bool:
        return bool(self.fragile_flag)

    @property
    def is_active(self) -> bool:
        return self.status != "Discontinued" if self.status else True

    @property
    def sub_category(self) -> Optional[str]:
        return self.subcategory

    @property
    def weight_kg(self) -> Optional[float]:
        return self.weight

    @property
    def reorder_point(self) -> int:
        """Get reorder point from the first inventory record."""
        if self.inventory_records:
            return self.inventory_records[0].reorder_point or 10
        return 10


class Inventory(Base):
    """Real-time stock position per product per warehouse."""
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column("inventory_id", Integer, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    current_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incoming_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    _inventory_turnover: Mapped[Optional[float]] = mapped_column("inventory_turnover", Float, nullable=True)
    last_updated: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="inventory_records")

    @property
    def inventory_turnover(self) -> float:
        return self._inventory_turnover if self._inventory_turnover else 2.5

    # Frontend compatibility properties
    @property
    def quantity_on_hand(self) -> int:
        return self.current_stock

    @property
    def quantity_reserved(self) -> int:
        return self.reserved_stock

    @property
    def quantity_in_transit(self) -> int:
        return self.incoming_stock

    @property
    def available_quantity(self) -> int:
        return self.current_stock - self.reserved_stock

    @property
    def warehouse_location(self) -> Optional[str]:
        return f"WH-{self.warehouse_id}"

    @property
    def warehouse_city(self) -> Optional[str]:
        cities = {1: "Delhi", 2: "Mumbai", 3: "Bangalore", 4: "Jaipur", 5: "Kolkata"}
        return cities.get(self.warehouse_id, "Unknown")

    @property
    def updated_at(self) -> Optional[str]:
        return self.last_updated


class InventoryMovement(Base):
    """Immutable audit ledger for stock mutations."""
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column("movement_id", Integer, primary_key=True, autoincrement=True)
    inventory_id: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_before: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    movement_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())

    # Frontend compatibility
    @property
    def quantity_delta(self) -> int:
        return self.quantity_changed

    @property
    def note(self) -> Optional[str]:
        return self.movement_reason


class ProductSupplier(Base):
    """Many-to-many junction between products and suppliers."""
    __tablename__ = "product_suppliers"

    id: Mapped[int] = mapped_column("product_supplier_id", Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False, index=True)
    supplier_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minimum_order_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    preferred_supplier_flag: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contract_status: Mapped[str] = mapped_column(String(50), default="Active", nullable=False)
    supplier_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="product_suppliers")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="product_suppliers")  # type: ignore

    @property
    def is_preferred(self) -> bool:
        return bool(self.preferred_supplier_flag)

    @property
    def moq(self) -> Optional[int]:
        return self.minimum_order_qty
