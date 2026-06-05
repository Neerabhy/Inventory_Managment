"""
models/logistics.py — Shipment and ServiceableCity ORM models.
Mapped to the actual electronics_inventory_v3_full database schema.
"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend_anti_gravity.app.core.database import Base


class ServiceableCity(Base):
    __tablename__ = "serviceable_cities"

    id: Mapped[int] = mapped_column("city_id", Integer, primary_key=True, autoincrement=True)
    city_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column("shipment_id", Integer, primary_key=True, autoincrement=True)
    shipment_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    logistics_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    destination_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transportation_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shipping_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_delivery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_delivery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delayed_flag: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    weather_delay_flag: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    remote_area_flag: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    shipment_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    shipment_code: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)

    # Frontend compatibility properties
    @property
    def direction(self) -> str:
        return self.shipment_type or "UNKNOWN"

    @property
    def carrier(self) -> Optional[str]:
        return self.logistics_provider

    @property
    def origin_city(self) -> Optional[str]:
        return self.source_city

    @property
    def status(self) -> str:
        return self.shipment_status or "UNKNOWN"

    @property
    def order_id(self) -> Optional[int]:
        return None

    @property
    def tracking_number(self) -> Optional[str]:
        return self.shipment_code

    @property
    def total_weight_kg(self) -> Optional[float]:
        return None

    @property
    def fragile_items(self) -> bool:
        return False

    @property
    def estimated_cost(self) -> Optional[float]:
        return self.shipping_cost

    @property
    def actual_cost(self) -> Optional[float]:
        return self.shipping_cost

    @property
    def delay_days(self) -> Optional[int]:
        if self.actual_delivery_days and self.expected_delivery_days:
            diff = self.actual_delivery_days - self.expected_delivery_days
            return diff if diff > 0 else 0
        return None

    @property
    def damage_reported(self) -> bool:
        return False
