"""
api/analytics.py — Dashboard charts, demand forecasting (persisted), landing stats.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_current_user, get_db
from ..models.analytics import Return, Sale
from ..models.auth import User
from ..models.inventory import Inventory, Product
from ..models.logistics import Shipment
from ..models.predictions import InventoryReorderPlan, SalesForecast, SalesFeature
from ..models.procurement import PurchaseOrder
from ..services.copilot_insights import build_dashboard_insights
from ..services.prediction_service import (
    forecasts_are_empty,
    get_forecast_series_from_db,
    refresh_all_forecasts,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class ForecastStatusOut(BaseModel):
    forecasts_empty: bool
    forecast_rows: int
    products_with_features: int


class ForecastRunOut(BaseModel):
    ran: bool
    products_processed: Optional[int] = None
    batch_id: Optional[str] = None
    reason: Optional[str] = None


class ProductSalesPoint(BaseModel):
    day: str
    revenue: float
    units: int


class DashboardSummaryOut(BaseModel):
    total_revenue: float
    sales_orders: int
    units_sold: int
    return_rate_pct: float
    inventory_health_pct: float
    total_shipments: int
    delayed_shipments: int
    delay_rate_pct: float
    procurement_spend: float
    open_purchase_orders: int
    fraud_risk_returns: int
    forecasted_demand_units: int
    deltas: dict[str, float]


def _pct_delta(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 1)


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Canonical dashboard KPI source.

    Values are all-time operational totals unless the name says "open" or "rate".
    Deltas compare the latest 30 sale-date days with the previous 30 sale-date days.
    """
    max_sale_day = await db.scalar(select(func.max(func.substr(Sale.sale_date, 1, 10))))

    total_revenue = float(await db.scalar(select(func.coalesce(func.sum(Sale.final_amount), 0))) or 0)
    sales_orders = int(await db.scalar(select(func.count(Sale.id))) or 0)
    units_sold = int(await db.scalar(select(func.coalesce(func.sum(Sale.quantity), 0))) or 0)
    returns_count = int(await db.scalar(select(func.count(Return.id))) or 0)
    return_rate_pct = round((returns_count / sales_orders * 100), 2) if sales_orders else 0.0

    total_inventory_rows = int(await db.scalar(select(func.count(Inventory.id))) or 0)
    healthy_inventory_rows = int(
        await db.scalar(
            select(func.count(Inventory.id)).where(Inventory.current_stock >= Inventory.safety_stock)
        )
        or 0
    )
    inventory_health_pct = (
        round((healthy_inventory_rows / total_inventory_rows * 100), 2)
        if total_inventory_rows
        else 0.0
    )

    total_shipments = int(await db.scalar(select(func.count(Shipment.id))) or 0)
    delayed_shipments = int(
        await db.scalar(
            select(func.count(Shipment.id)).where(
                (Shipment.delayed_flag == 1)
                | (
                    Shipment.actual_delivery_days.is_not(None)
                    & Shipment.expected_delivery_days.is_not(None)
                    & (Shipment.actual_delivery_days > Shipment.expected_delivery_days)
                )
            )
        )
        or 0
    )
    delay_rate_pct = round((delayed_shipments / total_shipments * 100), 2) if total_shipments else 0.0

    procurement_spend = float(
        await db.scalar(
            select(func.coalesce(func.sum(PurchaseOrder.quantity * PurchaseOrder.unit_cost), 0))
        )
        or 0
    )
    open_statuses = ["draft", "pending", "ordered", "confirmed", "approved", "in transit", "shipped"]
    open_purchase_orders = int(
        await db.scalar(
            select(func.count(PurchaseOrder.id)).where(
                func.lower(func.coalesce(PurchaseOrder.status, "draft")).in_(open_statuses)
            )
        )
        or 0
    )
    fraud_risk_returns = int(
        await db.scalar(select(func.count(Return.id)).where(Return.fraud_risk_score >= 0.65))
        or 0
    )
    forecasted_demand_units = int(
        await db.scalar(select(func.coalesce(func.sum(SalesForecast.predicted_qty), 0))) or 0
    )

    deltas: dict[str, float] = {
        "total_revenue": 0.0,
        "sales_orders": 0.0,
        "units_sold": 0.0,
        "return_rate_pct": 0.0,
        "total_shipments": 0.0,
        "procurement_spend": 0.0,
        "forecasted_demand_units": 0.0,
    }
    if max_sale_day:
        current_start = await db.scalar(select(func.date(max_sale_day, "-29 days")))
        previous_start = await db.scalar(select(func.date(max_sale_day, "-59 days")))

        cur_rev = float(
            await db.scalar(
                select(func.coalesce(func.sum(Sale.final_amount), 0)).where(
                    func.substr(Sale.sale_date, 1, 10) >= current_start
                )
            )
            or 0
        )
        prev_rev = float(
            await db.scalar(
                select(func.coalesce(func.sum(Sale.final_amount), 0)).where(
                    func.substr(Sale.sale_date, 1, 10) >= previous_start,
                    func.substr(Sale.sale_date, 1, 10) < current_start,
                )
            )
            or 0
        )
        cur_orders = int(
            await db.scalar(
                select(func.count(Sale.id)).where(func.substr(Sale.sale_date, 1, 10) >= current_start)
            )
            or 0
        )
        prev_orders = int(
            await db.scalar(
                select(func.count(Sale.id)).where(
                    func.substr(Sale.sale_date, 1, 10) >= previous_start,
                    func.substr(Sale.sale_date, 1, 10) < current_start,
                )
            )
            or 0
        )
        cur_units = int(
            await db.scalar(
                select(func.coalesce(func.sum(Sale.quantity), 0)).where(
                    func.substr(Sale.sale_date, 1, 10) >= current_start
                )
            )
            or 0
        )
        prev_units = int(
            await db.scalar(
                select(func.coalesce(func.sum(Sale.quantity), 0)).where(
                    func.substr(Sale.sale_date, 1, 10) >= previous_start,
                    func.substr(Sale.sale_date, 1, 10) < current_start,
                )
            )
            or 0
        )
        deltas["total_revenue"] = _pct_delta(cur_rev, prev_rev)
        deltas["sales_orders"] = _pct_delta(cur_orders, prev_orders)
        deltas["units_sold"] = _pct_delta(cur_units, prev_units)

    return DashboardSummaryOut(
        total_revenue=round(total_revenue, 2),
        sales_orders=sales_orders,
        units_sold=units_sold,
        return_rate_pct=return_rate_pct,
        inventory_health_pct=inventory_health_pct,
        total_shipments=total_shipments,
        delayed_shipments=delayed_shipments,
        delay_rate_pct=delay_rate_pct,
        procurement_spend=round(procurement_spend, 2),
        open_purchase_orders=open_purchase_orders,
        fraud_risk_returns=fraud_risk_returns,
        forecasted_demand_units=forecasted_demand_units,
        deltas=deltas,
    )


@router.get("/dashboard")
async def dashboard_charts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Dashboard chart data — logistics delays sourced from shipments only."""
    rev_query = (
        select(
            func.substr(Sale.sale_date, 1, 10).label("day"),
            func.sum(Sale.final_amount).label("revenue"),
            func.count(Sale.id).label("orders"),
            func.sum(Sale.quantity).label("units"),
        )
        .group_by(func.substr(Sale.sale_date, 1, 10))
        .order_by(desc(func.substr(Sale.sale_date, 1, 10)))
        .limit(30)
    )
    rev_res = await db.execute(rev_query)
    rev_data = [
        {
            "day": r.day,
            "revenue": float(r.revenue or 0),
            "orders": int(r.orders or 0),
            "units": int(r.units or 0),
        }
        for r in rev_res.all()
    ]
    rev_data.reverse()

    cat_query = (
        select(Product.category, func.sum(Sale.final_amount).label("revenue"))
        .join(Sale, Sale.product_id == Product.id)
        .group_by(Product.category)
        .order_by(desc(func.sum(Sale.final_amount)))
        .limit(5)
    )
    cat_res = await db.execute(cat_query)
    cat_data = [{"category": r.category or "Unknown", "revenue": float(r.revenue or 0)} for r in cat_res.all()]

    ret_query = (
        select(Return.return_reason, func.count(Return.id).label("count"))
        .group_by(Return.return_reason)
        .order_by(desc(func.count(Return.id)))
        .limit(5)
    )
    ret_res = await db.execute(ret_query)
    ret_data = [{"reason": r.return_reason or "Unknown", "count": r.count} for r in ret_res.all()]

    total_shipments = int(await db.scalar(select(func.count(Shipment.id))) or 0)
    delayed_shipments = int(
        await db.scalar(
            select(func.count(Shipment.id)).where(
                (Shipment.delayed_flag == 1)
                | (
                    Shipment.actual_delivery_days.is_not(None)
                    & Shipment.expected_delivery_days.is_not(None)
                    & (Shipment.actual_delivery_days > Shipment.expected_delivery_days)
                )
            )
        )
        or 0
    )
    delay_buckets = [
        {"bucket": "On Time", "value": max(total_shipments - delayed_shipments, 0)},
        {"bucket": "Delayed", "value": delayed_shipments},
    ]

    return {
        "revenueTrend": rev_data,
        "categoryPerf": cat_data,
        "returnReasons": ret_data,
        "shipmentDelayBuckets": delay_buckets,
    }


@router.get("/forecast/status", response_model=ForecastStatusOut)
async def forecast_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Check whether demand forecasts need to be generated."""
    empty = await forecasts_are_empty(db)
    fc_count = await db.scalar(select(func.count(SalesForecast.id))) or 0
    feat_count = await db.scalar(select(func.count(SalesFeature.id))) or 0
    return ForecastStatusOut(
        forecasts_empty=empty,
        forecast_rows=int(fc_count),
        products_with_features=int(feat_count),
    )


@router.post("/forecast/run", response_model=ForecastRunOut)
async def run_forecast_batch(
    force: bool = Query(False, description="Recompute even if forecasts exist"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run ML demand forecasts for all products (forecast page button)."""
    result = await refresh_all_forecasts(db, force=force)
    await db.commit()
    return ForecastRunOut(**result)


@router.get("/forecast")
async def forecasting_data(
    product_id: Optional[int] = Query(None),
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    period: str = Query("weeks"),
    refresh: bool = Query(False, description="Force ML recompute (forecast button)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Demand forecasting page data.

    ML runs only when sales_forecasts is empty or refresh=true.
    Otherwise serves persisted forecasts from sales_forecasts table.
    """
    product_ids: Optional[List[int]] = None
    warehouse_id: Optional[int] = None
    if warehouse and warehouse not in ("undefined", "all"):
        try:
            warehouse_id = int(warehouse)
        except ValueError:
            warehouse_id = None

    if not product_id:
        product_query = select(Product.id)
        if category and category not in ("undefined", "all"):
            product_query = product_query.where(Product.category == category)
        if warehouse_id:
            product_query = product_query.join(Inventory, Inventory.product_id == Product.id).where(
                Inventory.warehouse_id == warehouse_id
            )
        if category and category not in ("undefined", "all") or warehouse_id:
            product_ids = [row[0] for row in (await db.execute(product_query)).all()]

    if refresh or await forecasts_are_empty(db):
        await refresh_all_forecasts(db, force=refresh)
        await db.commit()

    series = await get_forecast_series_from_db(
        db,
        product_id=product_id,
        product_ids=product_ids,
        warehouse_id=warehouse_id,
        period=period,
    )
    return series


@router.get("/product-sales", response_model=List[ProductSalesPoint])
async def product_sales_trend(
    product_id: int = Query(...),
    warehouse_id: Optional[int] = Query(None),
    limit: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Daily sales trend for a product, optionally scoped to one warehouse."""
    q = (
        select(
            func.substr(Sale.sale_date, 1, 10).label("day"),
            func.sum(Sale.final_amount).label("revenue"),
            func.sum(Sale.quantity).label("units"),
        )
        .where(Sale.product_id == product_id)
        .group_by(func.substr(Sale.sale_date, 1, 10))
        .order_by(desc(func.substr(Sale.sale_date, 1, 10)))
        .limit(limit)
    )
    if warehouse_id:
        q = q.where(Sale.warehouse_id == warehouse_id)

    rows = (await db.execute(q)).all()
    out = [
        ProductSalesPoint(
            day=r.day,
            revenue=float(r.revenue or 0),
            units=int(r.units or 0),
        )
        for r in rows
    ]
    out.reverse()
    return out


@router.get("/forecast/products")
async def list_product_forecasts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Per-product forecast summary from persisted tables."""
    res = await db.execute(
        select(
            SalesForecast.product_id,
            func.count(SalesForecast.id).label("points"),
            func.avg(SalesForecast.avg_daily_demand).label("avg_daily"),
            func.min(SalesForecast.stockout_in_days).label("stockout_days"),
            func.max(SalesForecast.model_used).label("model"),
        ).group_by(SalesForecast.product_id)
    )
    rows = res.all()
    out = []
    for r in rows:
        feat = await db.scalar(select(SalesFeature).where(SalesFeature.product_id == r.product_id))
        prod = await db.get(Product, r.product_id)
        out.append({
            "product_id": r.product_id,
            "product_name": prod.product_name if prod else None,
            "forecast_points": r.points,
            "avg_daily_demand": round(float(r.avg_daily or 0), 2),
            "stockout_in_days": r.stockout_days,
            "model_used": r.model,
            "current_stock": feat.current_stock if feat else None,
            "recommended_reorder": None,
        })
        plan_res = await db.execute(
            select(func.max(InventoryReorderPlan.recommended_reorder_point)).where(
                InventoryReorderPlan.product_id == r.product_id
            )
        )
        rop = plan_res.scalar_one_or_none()
        if rop:
            out[-1]["recommended_reorder"] = int(rop)
    return out


@router.get("/landing")
async def landing_stats(db: AsyncSession = Depends(get_db)):
    """Landing page metrics — shipment delays from shipments table."""
    total_rev = (await db.execute(select(func.sum(Sale.final_amount)))).scalar_one_or_none() or 4820000
    delayed = (
        await db.execute(select(func.count(Shipment.id)).where(Shipment.delayed_flag == 1))
    ).scalar_one_or_none() or 0
    returns = (await db.execute(select(func.count(Return.id)))).scalar_one_or_none() or 0

    data_context = {
        "revenue": float(total_rev),
        "delayed_shipments": int(delayed),
        "returns": int(returns),
    }

    insights = await build_dashboard_insights(db)

    return {
        "totalRevenue": float(total_rev),
        "delayedShipments": int(delayed),
        "totalReturns": int(returns),
        "insights": insights,
    }
