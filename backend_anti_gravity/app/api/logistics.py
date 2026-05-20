"""
api/logistics.py — Logistics routes: shipment tracking, delay analysis, city validation.
"""
from __future__ import annotations
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend_anti_gravity.app.api.deps import get_current_user, get_db, require_procurement
from backend_anti_gravity.app.core.config import settings
from backend_anti_gravity.app.ml.cost_prediction import CostPredictor
from backend_anti_gravity.app.models.auth import User
from backend_anti_gravity.app.models.logistics import ServiceableCity, Shipment

router = APIRouter(prefix="/logistics", tags=["Logistics"])


class ShipmentOut(BaseModel):
    id: int
    shipment_code: Optional[str] = None
    direction: str
    order_id: Optional[int] = None
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    status: str
    distance_km: Optional[Decimal] = None
    total_weight_kg: Optional[Decimal] = None
    fragile_items: bool
    weather_delay_flag: bool
    estimated_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    delay_days: Optional[int] = None
    damage_reported: bool
    model_config = {"from_attributes": True}


class ShipmentCreate(BaseModel):
    direction: str
    order_id: Optional[int] = None
    origin_city: Optional[str] = None
    destination_city: str
    carrier: Optional[str] = None
    distance_km: Optional[Decimal] = None
    total_weight_kg: Optional[Decimal] = None
    fragile_items: bool = False
    weather_delay_flag: bool = False


class CostEstimateRequest(BaseModel):
    distance_km: float
    weight_kg: float
    fragile_flag: bool = False
    weather_delay_flag: bool = False


class CostEstimateResponse(BaseModel):
    estimated_cost_inr: float
    delay_probability: float
    confidence: float
    model_used: str


class DelayAnalysis(BaseModel):
    total_shipments: int
    delayed_count: int
    delay_rate_pct: float
    avg_delay_days: float
    weather_delayed: int
    damage_reported: int


class ServiceableCityOut(BaseModel):
    id: int
    city_name: str
    state: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


@router.get("/cities", response_model=List[ServiceableCityOut])
async def list_serviceable_cities(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Return all active serviceable delivery cities."""
    result = await db.execute(select(ServiceableCity).where(ServiceableCity.is_active == True))
    return result.scalars().all()


@router.get("/shipments", response_model=List[ShipmentOut])
async def list_shipments(
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List shipments with optional direction/status filters."""
    q = select(Shipment).order_by(Shipment.id.desc())
    if direction:
        q = q.where(Shipment.shipment_type == direction)
    if status:
        q = q.where(Shipment.shipment_status == status)
    result = await db.execute(q.offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/shipments", response_model=ShipmentOut, status_code=201)
async def create_shipment(
    payload: ShipmentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    """Create shipment. Validates OUTBOUND city; auto-runs ML cost prediction."""
    if payload.direction == "OUTBOUND" and payload.destination_city not in settings.serviceable_cities:
        raise HTTPException(status_code=400, detail=f"'{payload.destination_city}' is not a serviceable city.")

    import uuid
    shipment = Shipment(
        shipment_type=payload.direction,
        source_city=payload.origin_city,
        destination_city=payload.destination_city,
        logistics_provider=payload.carrier,
        distance_km=float(payload.distance_km) if payload.distance_km else None,
        shipment_status="PENDING",
        shipment_code=f"SHP-{str(uuid.uuid4())[:8].upper()}"
    )
    if payload.distance_km and payload.total_weight_kg:
        predictor = CostPredictor()
        pred = predictor.predict(
            distance_km=float(payload.distance_km),
            weight_kg=float(payload.total_weight_kg),
            fragile_flag=payload.fragile_items,
            weather_delay_flag=payload.weather_delay_flag,
        )
        shipment.shipping_cost = pred["estimated_cost_inr"]

    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)
    return shipment


@router.get("/shipments/{shipment_id}", response_model=ShipmentOut)
async def get_shipment(shipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    s = await db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    return s


@router.patch("/shipments/{shipment_id}/status")
async def update_shipment_status(
    shipment_id: int,
    new_status: str = Query(...),
    delay_days: Optional[int] = Query(None),
    damage_reported: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    """Update shipment tracking status."""
    s = await db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    s.shipment_status = new_status
    if delay_days is not None:
        s.actual_delivery_days = (s.expected_delivery_days or 0) + delay_days
    await db.commit()
    return {"message": f"Shipment {shipment_id} updated to {new_status}"}


@router.post("/cost-estimate", response_model=CostEstimateResponse)
async def estimate_logistics_cost(payload: CostEstimateRequest, _: User = Depends(get_current_user)):
    """Run ML cost prediction model. Returns estimated cost (INR) and delay probability."""
    predictor = CostPredictor()
    result = predictor.predict(
        distance_km=payload.distance_km,
        weight_kg=payload.weight_kg,
        fragile_flag=payload.fragile_flag,
        weather_delay_flag=payload.weather_delay_flag,
    )
    return CostEstimateResponse(**result)


@router.get("/delay-analysis", response_model=DelayAnalysis)
async def get_delay_analysis(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Aggregate delay metrics across all shipments."""
    result = await db.execute(select(Shipment))
    shipments = result.scalars().all()
    total = len(shipments)
    if total == 0:
        return DelayAnalysis(total_shipments=0, delayed_count=0, delay_rate_pct=0.0,
                             avg_delay_days=0.0, weather_delayed=0, damage_reported=0)
    delayed = [s for s in shipments if s.delay_days and s.delay_days > 0]
    avg_delay = sum(s.delay_days for s in delayed if s.delay_days) / max(len(delayed), 1)
    return DelayAnalysis(
        total_shipments=total, delayed_count=len(delayed),
        delay_rate_pct=round(len(delayed) / total * 100, 2),
        avg_delay_days=round(avg_delay, 1),
        weather_delayed=sum(1 for s in shipments if s.weather_delay_flag),
        damage_reported=sum(1 for s in shipments if s.damage_reported),
    )
