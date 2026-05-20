from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    supplier_name: Mapped[str] = mapped_column(String(100), nullable=False)  # [cite: 79]
    contact_email: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_performance: Mapped[float] = mapped_column(Float, default=1.0)  # [cite: 80]
    quality_score: Mapped[float] = mapped_column(Float, default=5.0)  # [cite: 81]
    reliability: Mapped[float] = mapped_column(Float, default=1.0)  # [cite: 82]
    cost_efficiency: Mapped[float] = mapped_column(Float, default=1.0)  # [cite: 83]

    # Relationships
    product_links = relationship("ProductSupplier", back_populates="supplier")
    warehouse_links = relationship("WarehouseSupplier", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")

class ProductSupplier(Base):
    """Junction table connecting products to multiple suppliers[cite: 95, 97]."""
    __tablename__ = "product_suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    supplier_price: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 106]
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)  # [cite: 107]
    quality_level: Mapped[float] = mapped_column(Float, default=5.0)  # [cite: 108]
    supply_capacity: Mapped[int] = mapped_column(Integer, nullable=False)  # [cite: 109]

    product = relationship("Product", back_populates="supplier_links")
    supplier = relationship("Supplier", back_populates="product_links")

class WarehouseSupplier(Base):
    """Junction table defining which suppliers serve specific warehouses[cite: 133, 135]."""
    __tablename__ = "warehouse_suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    delivery_cost: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 137]
    delivery_time_days: Mapped[int] = mapped_column(Integer, nullable=False)  # [cite: 138]

    supplier = relationship("Supplier", back_populates="warehouse_links")

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    po_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)  # [cite: 171]
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)  # [cite: 172]
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)  # [cite: 173]
    procurement_cost: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 175]
    order_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, DISPATCHED, ARRIVED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    delivery_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # [cite: 174]

    supplier = relationship("Supplier", back_populates="purchase_orders")
    decision_audits = relationship("ProcurementDecision", back_populates="purchase_order")

class ProcurementDecision(Base):
    """Audit table to monitor system automated choices and manual adjustments."""
    __tablename__ = "procurement_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    system_recommended_supplier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    override_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    purchase_order = relationship("PurchaseOrder", back_populates="decision_audits")
    reviewed_by = relationship("User", back_populates="procurement_overrides")