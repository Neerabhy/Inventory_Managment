from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    location_city: Mapped[str] = mapped_column(String(50), nullable=False)  # [cite: 57]
    loyalty_level: Mapped[str] = mapped_column(String(20), default="BRONZE")  # Bronze, Silver, Gold [cite: 61]
    fraud_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # From Isolation Forest Anomaly Engine

    sales_orders = relationship("Sales", back_populates="customer")
    returns = relationship("ReturnRecords", back_populates="customer")

class Sales(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)  # [cite: 201]
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)  # [cite: 203]
    quantity_sold: Mapped[int] = mapped_column(Integer, nullable=False)  # [cite: 202]
    revenue_generated: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 205]
    sale_date: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    product = relationship("Product", back_populates="sales_orders")
    customer = relationship("Customer", back_populates="sales_orders")

class ReturnRecords(Base):
    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    return_reason: Mapped[str] = mapped_column(String(100), nullable=False)  # Damaged, Poor Quality, Fraud, Wrong Size [cite: 217-220]
    refund_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    ai_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # Calculated by Return XGBoost
    is_human_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_justification: Mapped[str] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    product = relationship("Product", back_populates="returns")
    customer = relationship("Customer", back_populates="returns")

class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # [cite: 237]
    review_text: Mapped[str] = mapped_column(Text, nullable=True)  # [cite: 238]
    sentiment_polarity: Mapped[float] = mapped_column(Float, default=0.0)  # Derived via VADER/DistilBERT Task
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class KpiDefinition(Base):
    """Dynamic context mapping engine used to eliminate UI hardcoding."""
    __tablename__ = "kpi_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kpi_key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    formula_text: Mapped[str] = mapped_column(String(255), nullable=False)
    description_summary: Mapped[str] = mapped_column(Text, nullable=False)
    critical_threshold: Mapped[float] = mapped_column(Float, nullable=True)