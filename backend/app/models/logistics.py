from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, func, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    warehouse_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    location_city: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # [cite: 120]
    storage_capacity: Mapped[int] = mapped_column(Integer, nullable=False)  # [cite: 121]
    operating_cost: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 122]

    stocks = relationship("Inventory", back_populates="warehouse")

class ServiceableCity(Base):
    """Enforces strict systemic limits for logistics validation mappings."""
    __tablename__ = "serviceable_cities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    city_name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    # Enforces explicit field verification constraints directly inside the engine layer
    __table_args__ = (
        CheckConstraint(
            "city_name IN ('Delhi', 'Mumbai', 'Bangalore', 'Jaipur', 'Kolkata')",
            name="check_authorized_cities"
        ),
    )

class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tracking_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    shipment_type: Mapped[str] = mapped_column(String(20), nullable=False)  # INBOUND, OUTBOUND [cite: 184, 185]
    origin_location: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_location: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(30), default="IN_TRANSIT", nullable=False)  # [cite: 187]
    shipping_cost: Mapped[float] = mapped_column(Float, nullable=False)  # [cite: 188]
    transportation_mode: Mapped[str] = mapped_column(String(30), nullable=False)  # Road, Air, Rail [cite: 189]
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    fragile_flag: Mapped[bool] = mapped_column(default=False)
    weather_delay_flag: Mapped[bool] = mapped_column(default=False)  # [cite: 191]
    delay_probability: Mapped[float] = mapped_column(Float, default=0.0)  # Calculated by XGBoost
    estimated_delivery: Mapped[datetime] = mapped_column(DateTime, nullable=False)