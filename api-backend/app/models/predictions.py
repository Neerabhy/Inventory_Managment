"""
ORM models for persisted ML predictions and forecasts.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class ReturnRiskPrediction(Base):
    __tablename__ = "return_risk_predictions"

    id: Mapped[int] = mapped_column("prediction_id", Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(Integer, ForeignKey("returns.return_id", ondelete="CASCADE"), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fraud_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    anomaly_flag: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())


class SalesFeature(Base):
    __tablename__ = "sales_features"

    id: Mapped[int] = mapped_column("feature_id", Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id", ondelete="CASCADE"), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avg_daily_sales_7d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_daily_sales_30d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_qty_30d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_revenue_30d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safety_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inventory_turnover: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    selling_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manufacturing_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    computed_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())


class SalesForecast(Base):
    __tablename__ = "sales_forecasts"
    __table_args__ = (UniqueConstraint("product_id", "forecast_date", "batch_id", name="uq_sales_forecast_row"),)

    id: Mapped[int] = mapped_column("forecast_id", Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_date: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_qty: Mapped[float] = mapped_column(Float, nullable=False)
    lower_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    upper_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_daily_demand: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stockout_in_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    batch_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())


class VendorRecommendation(Base):
    __tablename__ = "vendor_recommendations"

    id: Mapped[int] = mapped_column("recommendation_id", Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    composite_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adjusted_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    supplier_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    days_stock_covers: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_daily_demand: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier_risk_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rank_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())


class InventoryReorderPlan(Base):
    __tablename__ = "inventory_reorder_plans"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id", name="uq_reorder_plan"),)

    id: Mapped[int] = mapped_column("plan_id", Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_demand_units: Mapped[float] = mapped_column(Float, nullable=False)
    avg_daily_demand: Mapped[float] = mapped_column(Float, nullable=False)
    max_lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_reorder_point: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_buffer_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    coverage_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    computed_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())
