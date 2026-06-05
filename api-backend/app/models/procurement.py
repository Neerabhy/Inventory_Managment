"""
models/procurement.py — Supplier, PurchaseOrder, ProcurementDecision ORM models.
Mapped to the actual inventory-database schema.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column("supplier_id", Integer, primary_key=True, autoincrement=True)
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    avg_lead_time_days: Mapped[float] = mapped_column(Float, nullable=False)
    reliability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    defect_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    on_time_delivery_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_cost_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    minimum_order_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    supplier_specialization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supplier_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    product_suppliers: Mapped[List["ProductSupplier"]] = relationship("ProductSupplier", back_populates="supplier")  # type: ignore
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="supplier")

    # Frontend compatibility
    @property
    def name(self) -> str:
        return self.supplier_name

    @property
    def is_active(self) -> bool:
        return True

    @property
    def contact_person(self) -> Optional[str]:
        return None

    @property
    def email(self) -> Optional[str]:
        return None

    @property
    def phone(self) -> Optional[str]:
        return None

    @property
    def created_at(self) -> Optional[str]:
        return None


class PurchaseOrder(Base):
    """Purchase order — flat structure with product_id directly (no line items table in DB)."""
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column("po_id", Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    shipment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    order_date: Mapped[str] = mapped_column(Text, nullable=False)
    expected_delivery: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_delivery: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    logistics_cost: Mapped[Optional[float]] = mapped_column(Float, default=0, nullable=True)
    landed_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    ai_recommendation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    po_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="purchase_orders")

    # Frontend compatibility
    @property
    def order_number(self) -> Optional[str]:
        return self.po_code

    @property
    def total_amount(self) -> Optional[float]:
        return round(self.quantity * self.unit_cost, 2) if self.unit_cost else None

    @property
    def delivery_city(self) -> Optional[str]:
        return None

    @property
    def expected_delivery_date(self) -> Optional[str]:
        return self.expected_delivery

    @property
    def actual_delivery_date(self) -> Optional[str]:
        return self.actual_delivery

    @property
    def notes(self) -> Optional[str]:
        return None

    @property
    def created_by(self) -> Optional[str]:
        return None

    @property
    def created_at(self) -> str:
        return self.order_date

    @property
    def items(self) -> list:
        """Synthesize a single-item list for frontend compatibility."""
        return [{
            "id": self.id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": str(self.unit_cost) if self.unit_cost else None,
            "total_price": str(round(self.quantity * self.unit_cost, 2)) if self.unit_cost else None,
        }]


class ProcurementDecision(Base):
    __tablename__ = "procurement_decisions"

    id: Mapped[int] = mapped_column("decision_id", Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchase_orders.po_id"), unique=True, nullable=False, index=True)
    recommended_supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    selected_supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    ai_recommendation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    override_flag: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_savings: Mapped[Optional[float]] = mapped_column(Float, default=0, nullable=True)
    actual_savings: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decision_taken_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    decision_date: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())

    # Frontend compatibility
    @property
    def order_id(self) -> int:
        return self.po_id

    @property
    def decided_by(self) -> Optional[int]:
        return self.decision_taken_by

    @property
    def decision(self) -> str:
        return "OVERRIDE" if self.override_flag else "APPROVED"

    @property
    def decided_at(self) -> str:
        return self.decision_date

    @property
    def system_recommendation(self) -> Optional[str]:
        return f"Score: {self.ai_recommendation_score}" if self.ai_recommendation_score else None

    @property
    def notification_sent(self) -> bool:
        return True
