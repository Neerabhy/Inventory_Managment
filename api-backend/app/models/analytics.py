"""
models/analytics.py — Sale, Return, Review, KpiDefinition ORM models.
Mapped to the actual inventory-database schema.
"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column("sale_id", Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    shipment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sale_date: Mapped[str] = mapped_column(Text, nullable=False)
    order_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    delivery_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_amount: Mapped[float] = mapped_column(Float, nullable=False)
    shipping_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delivery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    order_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    order_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="sales")  # type: ignore

    # Frontend compatibility
    @property
    def quantity_sold(self) -> int:
        return self.quantity

    @property
    def unit_price(self) -> float:
        return self.selling_price

    @property
    def total_amount(self) -> float:
        return self.final_amount

    @property
    def sale_channel(self) -> Optional[str]:
        return self.payment_method

    @property
    def customer_city(self) -> Optional[str]:
        return self.delivery_city


class Return(Base):
    __tablename__ = "returns"

    id: Mapped[int] = mapped_column("return_id", Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales.sale_id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    return_date: Mapped[str] = mapped_column(Text, nullable=False)
    return_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    return_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    days_after_delivery: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    refund_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reverse_logistics_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fraud_risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    approval_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    refund_without_pickup: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resellable_flag: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    return_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="returns")  # type: ignore
    sale: Mapped[Optional["Sale"]] = relationship("Sale")

    # Frontend compatibility
    @property
    def reason_code(self) -> Optional[str]:
        return self.return_reason

    @property
    def fraud_score(self) -> Optional[float]:
        return self.fraud_risk_score

    @property
    def status(self) -> str:
        if self.approval_status == "Manual Review":
            return "PENDING"
        elif self.approval_status in ["Approved", "Auto Approved"]:
            return "APPROVED"
        elif self.approval_status == "Rejected":
            return "DECLINED"
        return self.approval_status or "PENDING"

    @property
    def risk_label(self) -> Optional[str]:
        if self.fraud_risk_score is None:
            return "LOW"
        if self.fraud_risk_score >= 0.65:
            return "HIGH"
        if self.fraud_risk_score >= 0.35:
            return "MEDIUM"
        return "LOW"

    @property
    def anomaly_flag(self) -> bool:
        return (self.fraud_risk_score or 0) > 0.80

    @property
    def return_ratio(self) -> Optional[float]:
        return None

    @property
    def approved_by(self) -> Optional[str]:
        return None

    @property
    def override_note(self) -> Optional[str]:
        return None

    @property
    def decided_at(self) -> Optional[str]:
        return None

    @property
    def created_at(self) -> str:
        return self.return_date


class ReturnHistory(Base):
    __tablename__ = "return_history"

    id: Mapped[int] = mapped_column("history_id", Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(Integer, ForeignKey("returns.return_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    override_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())

    return_record: Mapped["Return"] = relationship("Return")


class Review(Base):
    """Customer review. Table is 'reviews' in DB (not 'product_reviews')."""
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column("review_id", Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    review_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="reviews")  # type: ignore

    @property
    def sentiment_label(self) -> Optional[str]:
        if self.sentiment_score is None:
            return "NEUTRAL"
        if self.sentiment_score >= 0.05:
            return "POSITIVE"
        if self.sentiment_score <= -0.05:
            return "NEGATIVE"
        return "NEUTRAL"

    @property
    def created_at(self) -> Optional[str]:
        return self.review_date


class KpiDefinition(Base):
    __tablename__ = "kpi_definitions"

    id: Mapped[int] = mapped_column("kpi_id", Integer, primary_key=True, autoincrement=True)
    kpi_code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    kpi_name: Mapped[str] = mapped_column(String(150), nullable=False)
    kpi_category: Mapped[str] = mapped_column(String(60), nullable=False)
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    warning_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    critical_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    higher_is_better: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    dashboard_module: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())

    # Frontend compatibility
    @property
    def display_name(self) -> str:
        return self.kpi_name

    @property
    def category(self) -> str:
        return self.kpi_category


class AiInsightCache(Base):
    __tablename__ = "ai_insight_cache"

    id: Mapped[int] = mapped_column("cache_id", Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    insight_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())
