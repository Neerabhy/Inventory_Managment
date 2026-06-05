"""
api/logistics.py — Logistics routes sourced from the shipments table.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_current_user, get_db, require_procurement
from ..core.config import settings
from ..ml.cost_prediction import CostPredictor
from ..models.analytics import Sale
from ..models.auth import User
from ..models.inventory import Product
from ..models.logistics import ServiceableCity, Shipment
from ..models.procurement import PurchaseOrder, Supplier

router = APIRouter(prefix="/logistics", tags=["Logistics"])


class ShipmentOut(BaseModel):
    id: int
    shipment_code: Optional[str] = None
    direction: str
    carrier: Optional[str] = None
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
    expected_delivery_days: Optional[int] = None
    actual_delivery_days: Optional[int] = None
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


class InboundOrderOut(BaseModel):
    id: int
    po_code: Optional[str] = None
    supplier_id: int
    supplier_name: str
    product_id: int
    product_name: str
    sku: Optional[str] = None
    warehouse_id: int
    warehouse_city: Optional[str] = None
    quantity: int
    unit_cost: float
    total_amount: float
    status: Optional[str] = None
    order_date: str
    expected_delivery: Optional[str] = None
    actual_delivery: Optional[str] = None
    shipment_id: Optional[int] = None
    shipment_code: Optional[str] = None
    shipment_status: Optional[str] = None
    delivery_partner: Optional[str] = None
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    shipping_cost: Optional[float] = None
    delay_days: Optional[int] = None
    has_shipment: bool = False


class LogisticsSummaryOut(BaseModel):
    orders_placed: int
    inbound_orders: int
    outbound_orders: int
    total_orders: int
    delayed_shipments: int
    delay_rate_pct: float


WAREHOUSE_CITIES = {1: "Delhi", 2: "Mumbai", 3: "Bangalore", 4: "Jaipur", 5: "Kolkata"}
OPEN_INBOUND_STATUSES = {
    "draft",
    "pending",
    "ordered",
    "confirmed",
    "approved",
    "in transit",
    "shipped",
}


@router.get("/cities", response_model=List[ServiceableCityOut])
async def list_serviceable_cities(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ServiceableCity).where(ServiceableCity.is_active == True))
    return result.scalars().all()


@router.get("/inbound-orders", response_model=List[InboundOrderOut])
async def list_inbound_orders(
    status: Optional[str] = Query(None),
    include_closed: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Unified inbound view for Logistics.

    Purchase orders are the source of truth for inventory reorders. Shipments are
    joined when available, so newly created orders appear before logistics creates
    a shipment record.
    """
    q = (
        select(PurchaseOrder, Product, Supplier, Shipment)
        .join(Product, PurchaseOrder.product_id == Product.id)
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .outerjoin(Shipment, PurchaseOrder.shipment_id == Shipment.id)
        .order_by(PurchaseOrder.id.desc())
        .limit(limit)
    )
    if status:
        q = q.where(func.lower(PurchaseOrder.status) == status.lower())

    rows = (await db.execute(q)).all()
    inbound_orders: List[InboundOrderOut] = []
    for order, product, supplier, shipment in rows:
        order_status = order.status or "Draft"
        if not include_closed and order_status.lower() not in OPEN_INBOUND_STATUSES:
            continue

        delay_days = None
        if shipment and shipment.actual_delivery_days and shipment.expected_delivery_days:
            delay_days = max(shipment.actual_delivery_days - shipment.expected_delivery_days, 0)

        inbound_orders.append(
            InboundOrderOut(
                id=order.id,
                po_code=order.po_code,
                supplier_id=order.supplier_id,
                supplier_name=supplier.supplier_name,
                product_id=order.product_id,
                product_name=product.product_name,
                sku=product.sku,
                warehouse_id=order.warehouse_id,
                warehouse_city=WAREHOUSE_CITIES.get(order.warehouse_id),
                quantity=order.quantity,
                unit_cost=float(order.unit_cost or 0),
                total_amount=float(order.total_amount or 0),
                status=order_status,
                order_date=order.order_date,
                expected_delivery=order.expected_delivery,
                actual_delivery=order.actual_delivery,
                shipment_id=shipment.id if shipment else None,
                shipment_code=shipment.shipment_code if shipment else None,
                shipment_status=shipment.shipment_status if shipment else None,
                delivery_partner=shipment.logistics_provider if shipment else None,
                origin_city=shipment.source_city if shipment else supplier.city,
                destination_city=shipment.destination_city if shipment else WAREHOUSE_CITIES.get(order.warehouse_id),
                shipping_cost=float(shipment.shipping_cost) if shipment and shipment.shipping_cost is not None else None,
                delay_days=delay_days,
                has_shipment=shipment is not None,
            )
        )

    return inbound_orders


@router.get("/summary", response_model=LogisticsSummaryOut)
async def logistics_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """DB-backed counts for the logistics dashboard KPIs."""
    open_statuses = ["draft", "pending", "ordered", "confirmed", "approved", "in transit", "shipped"]
    open_po_filter = func.lower(func.coalesce(PurchaseOrder.status, "draft")).in_(open_statuses)

    orders_placed = await db.scalar(
        select(func.count(PurchaseOrder.id)).where(
            open_po_filter,
            PurchaseOrder.shipment_id.is_(None),
        )
    ) or 0
    inbound_orders = await db.scalar(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.shipment_id.is_not(None))
    ) or 0
    outbound_orders = await db.scalar(
        select(func.count(Shipment.id)).where(
            func.upper(func.coalesce(Shipment.shipment_type, "")).in_(["OUTBOUND", "FORWARD"])
        )
    ) or 0
    total_shipments = await db.scalar(select(func.count(Shipment.id))) or 0
    delayed_shipments = await db.scalar(
        select(func.count(Shipment.id)).where(
            (Shipment.delayed_flag == 1)
            | (
                Shipment.actual_delivery_days.is_not(None)
                & Shipment.expected_delivery_days.is_not(None)
                & (Shipment.actual_delivery_days > Shipment.expected_delivery_days)
            )
        )
    ) or 0
    delay_rate = round((int(delayed_shipments) / int(total_shipments) * 100), 2) if total_shipments else 0.0

    return LogisticsSummaryOut(
        orders_placed=int(orders_placed),
        inbound_orders=int(inbound_orders),
        outbound_orders=int(outbound_orders),
        total_orders=int(orders_placed) + int(inbound_orders) + int(outbound_orders),
        delayed_shipments=int(delayed_shipments),
        delay_rate_pct=delay_rate,
    )


@router.get("/shipments", response_model=List[ShipmentOut])
async def list_shipments(
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List shipments from the shipments table only."""
    q = select(Shipment).order_by(Shipment.id.desc())
    if direction:
        q = q.where(Shipment.shipment_type == direction)
    if status:
        q = q.where(Shipment.shipment_status == status)
    result = await db.execute(q.offset(skip).limit(limit))
    shipments = result.scalars().all()

    for s in shipments:
        stype = (s.shipment_type or "").upper()
        if stype in ("OUTBOUND", "FORWARD", "RETURN", "REVERSE"):
            val = await db.scalar(
                select(func.sum(Sale.final_amount)).where(Sale.shipment_id == s.id)
            )
        else:
            val = await db.scalar(
                select(func.sum(PurchaseOrder.quantity * PurchaseOrder.unit_cost)).where(
                    PurchaseOrder.shipment_id == s.id
                )
            )
            if val is None:
                val = await db.scalar(
                    select(func.sum(PurchaseOrder.landed_cost)).where(
                        PurchaseOrder.shipment_id == s.id
                    )
                )
        if val is not None:
            s._total_product_value = float(val)

    return shipments


@router.post("/shipments", response_model=ShipmentOut, status_code=201)
async def create_shipment(
    payload: ShipmentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    if payload.direction == "OUTBOUND" and payload.destination_city not in settings.serviceable_cities:
        raise HTTPException(status_code=400, detail=f"'{payload.destination_city}' is not a serviceable city.")

    shipment = Shipment(
        shipment_type=payload.direction,
        source_city=payload.origin_city,
        destination_city=payload.destination_city,
        logistics_provider=payload.carrier,
        distance_km=float(payload.distance_km) if payload.distance_km else None,
        shipment_status="PENDING",
        shipment_code=f"SHP-{str(uuid.uuid4())[:8].upper()}",
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
async def get_shipment(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
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
    predictor = CostPredictor()
    result = predictor.predict(
        distance_km=payload.distance_km,
        weight_kg=payload.weight_kg,
        fragile_flag=payload.fragile_flag,
        weather_delay_flag=payload.weather_delay_flag,
    )
    return CostEstimateResponse(**result)


@router.get("/delay-analysis", response_model=DelayAnalysis)
async def get_delay_analysis(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Delay metrics from shipments table only."""
    result = await db.execute(select(Shipment))
    shipments = result.scalars().all()
    total = len(shipments)

    if total == 0:
        return DelayAnalysis(
            total_shipments=0,
            delayed_count=0,
            delay_rate_pct=0.0,
            avg_delay_days=0.0,
            weather_delayed=0,
            damage_reported=0,
        )

    delayed = [s for s in shipments if s.delay_days and s.delay_days > 0]
    avg_delay = sum(s.delay_days for s in delayed if s.delay_days) / max(len(delayed), 1)

    return DelayAnalysis(
        total_shipments=total,
        delayed_count=len(delayed),
        delay_rate_pct=round(len(delayed) / total * 100, 2),
        avg_delay_days=round(avg_delay, 1),
        weather_delayed=sum(1 for s in shipments if s.weather_delay_flag),
        damage_reported=sum(1 for s in shipments if s.damage_reported),
    )
