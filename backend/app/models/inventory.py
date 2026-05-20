from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, func, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Formatted matching the required sequence logic: PRD-2026-XXXX
    product_code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)  # [cite: 32]
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # [cite: 33]
    brand: Mapped[str] = mapped_column(String(50), nullable=False)  # [cite: 34]
    price: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 35]
    size: Mapped[str] = mapped_column(String(20), nullable=True)  # [cite: 36]
    color: Mapped[str] = mapped_column(String(20), nullable=True)  # [cite: 37]
    rating: Mapped[float] = mapped_column(Float, default=0.0)  # [cite: 38]
    return_rate: Mapped[float] = mapped_column(Float, default=0.0)  # [cite: 39]
    abc_class: Mapped[str] = mapped_column(String(2), default="C", nullable=False)  # Determined dynamically by ML Task

    # Relationship references
    stocks = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    supplier_links = relationship("ProductSupplier", back_populates="product")
    sales_orders = relationship("Sales", back_populates="product")
    returns = relationship("ReturnRecords", back_populates="product")

class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, default=0)  # [cite: 150]
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0)  # [cite: 151]
    incoming_stock: Mapped[int] = mapped_column(Integer, default=0)  # [cite: 152]
    safety_stock: Mapped[int] = mapped_column(Integer, default=50)  # [cite: 153]
    reorder_point: Mapped[int] = mapped_column(Integer, default=100)  # [cite: 154]

    # Model relationships
    product = relationship("Product", back_populates="stocks")
    warehouse = relationship("Warehouse", back_populates="stocks")

class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)  # INBOUND, OUTBOUND, ADJUSTMENT, RETURN
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_before: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_id: Mapped[str] = mapped_column(String(50), nullable=True)  # Links to Order ID or PO ID
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())