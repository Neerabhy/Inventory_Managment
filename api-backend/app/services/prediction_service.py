"""
Central ML prediction persistence and batch refresh logic.

Forecasts run only when sales_forecasts is empty or when refresh=True (UI button).
All scores are written to dedicated tables before APIs serve them.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..ml.demand_forecast import DemandForecaster
from ..ml.return_classifier import ReturnClassifier
from ..ml.vendor_ranker import VendorRanker
from ..models.analytics import Sale
from ..models.inventory import Inventory, Product, ProductSupplier
from ..models.predictions import (
    InventoryReorderPlan,
    ReturnRiskPrediction,
    SalesFeature,
    SalesForecast,
    VendorRecommendation,
)
from ..models.procurement import PurchaseOrder, Supplier

FORECAST_HORIZON_DAYS = 120
SAFETY_BUFFER_DAYS = 7


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _non_negative_quantity(value: Any, *, minimum: float = 0.0) -> float:
    try:
        qty = float(value)
    except (TypeError, ValueError):
        return minimum
    if not math.isfinite(qty):
        return minimum
    return max(qty, minimum)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


async def forecasts_are_empty(db: AsyncSession) -> bool:
    count = await db.scalar(select(func.count(SalesForecast.id)))
    return (count or 0) == 0


async def save_return_risk_prediction(
    db: AsyncSession,
    *,
    return_id: int,
    product_id: int,
    customer_id: Optional[int],
    risk: Dict[str, Any],
) -> ReturnRiskPrediction:
    existing = await db.scalar(
        select(ReturnRiskPrediction).where(ReturnRiskPrediction.return_id == return_id)
    )
    if existing:
        row = existing
    else:
        row = ReturnRiskPrediction(return_id=return_id, product_id=product_id)
        db.add(row)

    row.customer_id = customer_id
    row.fraud_score = float(risk.get("fraud_score") or 0)
    row.return_probability = float(risk.get("return_probability") or 0)
    row.return_ratio = float(risk.get("return_ratio") or 0)
    row.risk_label = risk.get("risk_label")
    row.anomaly_flag = 1 if risk.get("anomaly_flag") else 0
    row.model_version = ReturnClassifier.model_version
    return row


async def score_return_risk(
    *,
    product_id: int,
    customer_id: Optional[str],
    reason_code: Optional[str],
    refund_amount: float,
) -> Dict[str, Any]:
    classifier = ReturnClassifier()
    return classifier.score(
        product_id=product_id,
        customer_id=customer_id,
        reason_code=reason_code,
        refund_amount=refund_amount,
    )


async def _product_sales_history(
    db: AsyncSession, product_id: int
) -> tuple[List[str], List[float]]:
    res = await db.execute(
        select(
            func.substr(Sale.sale_date, 1, 10).label("day"),
            func.sum(Sale.quantity).label("qty"),
        )
        .where(Sale.product_id == product_id)
        .group_by(func.substr(Sale.sale_date, 1, 10))
        .order_by(func.substr(Sale.sale_date, 1, 10))
    )
    rows = res.all()
    if not rows:
        return [], []
    return [r.day for r in rows], [float(r.qty or 0) for r in rows]


async def upsert_sales_features(
    db: AsyncSession,
    product: Product,
    inventory: Optional[Inventory],
) -> SalesFeature:
    dates, quantities = await _product_sales_history(db, product.id)

    total_qty_30d = sum(quantities[-30:]) if quantities else 0.0
    total_rev_res = await db.execute(
        select(func.coalesce(func.sum(Sale.final_amount), 0))
        .where(Sale.product_id == product.id)
    )
    total_revenue_30d = float(total_rev_res.scalar_one() or 0)

    days_with_sales = max(len(quantities), 1)
    avg_30d = total_qty_30d / min(30, days_with_sales) if quantities else 0.0
    avg_7d = sum(quantities[-7:]) / min(7, len(quantities[-7:])) if quantities else 0.0

    # -------------------------------------------------------------
    # OPTION A: Delete the old features row before inserting a new one
    # -------------------------------------------------------------
    await db.execute(
        delete(SalesFeature).where(SalesFeature.product_id == product.id)
    )

    # -------------------------------------------------------------
    # Build and insert the fresh calculations
    # -------------------------------------------------------------
    row = SalesFeature(
        product_id=product.id,
        category=product.category,
        brand=product.brand,
        avg_daily_sales_7d=round(avg_7d, 4),
        avg_daily_sales_30d=round(avg_30d, 4),
        total_qty_30d=round(total_qty_30d, 2),
        total_revenue_30d=round(total_revenue_30d, 2),
        current_stock=int(inventory.current_stock) if inventory else 0,
        safety_stock=int(inventory.safety_stock) if inventory else 0,
        inventory_turnover=float(inventory.inventory_turnover) if inventory else 2.5,
        selling_price=float(product.selling_price or 0),
        manufacturing_cost=float(product.manufacturing_cost or 0),
        computed_at=_utc_now()
    )
    
    db.add(row)
    
    # Flush immediately so the DB transaction registers this row 
    # right away, preventing UNIQUE constraint crashes from async overlap
    await db.flush()

    return row

def _demand_aware_vendor_scores(
    suppliers: List[Dict[str, Any]],
    avg_daily_demand: float,
    current_stock: int,
) -> List[Dict[str, Any]]:
    """Rank vendors using price, lead time, and days current stock lasts vs demand."""
    ranker = VendorRanker()
    base = ranker.rank(suppliers)
    if not base:
        return []

    days_cover = current_stock / max(avg_daily_demand, 0.01)
    supplier_lookup = {s["supplier_id"]: s for s in suppliers}
    prices = [
        float(s.get("supplier_price") or s.get("avg_cost_index") or 0)
        for s in suppliers
    ]
    min_p, max_p = min(prices), max(prices)

    for s in base:
        lead = float(s.get("avg_lead_time_days") or 7)
        raw_supplier = supplier_lookup.get(s["supplier_id"], {})
        price = float(raw_supplier.get("supplier_price") or s.get("avg_cost_index") or 0)
        stock_fit = 1.0 if lead <= days_cover else _clamp(days_cover / lead, 0.15, 1.0)
        if max_p > min_p:
            price_fit = _clamp(1.0 - (price - min_p) / (max_p - min_p))
        else:
            price_fit = 1.0

        s["days_stock_covers"] = round(days_cover, 2)
        s["avg_daily_demand"] = round(avg_daily_demand, 4)
        s["supplier_price"] = price
        s["lead_time_days"] = int(lead)
        s["adjusted_score"] = round(
            _clamp(s["composite_score"]) * 0.45 + stock_fit * 0.35 + price_fit * 0.20,
            4,
        )

    base.sort(key=lambda x: x["adjusted_score"], reverse=True)
    min_lead = min(float(x.get("avg_lead_time_days") or 99) for x in base)
    for i, s in enumerate(base):
        s["rank_position"] = i + 1
        lead = float(s.get("avg_lead_time_days") or 7)
        price = float(s.get("supplier_price") or 0)
        if s.get("supplier_risk_label") == "HIGH":
            s["recommendation"] = "HIGH RISK"
        elif i == 0:
            s["recommendation"] = "BEST CHOICE"
        elif lead <= min_lead + 0.01:
            s["recommendation"] = "FASTEST DELIVERY"
        elif price <= min(prices) + 0.01:
            s["recommendation"] = "LOWEST COST"
        else:
            s["recommendation"] = "RECOMMENDED"
    return base


async def _supplier_rows_for_product(db: AsyncSession, product_id: int) -> List[tuple]:
    res = await db.execute(
        select(ProductSupplier, Supplier)
        .join(Supplier, ProductSupplier.supplier_id == Supplier.id)
        .where(ProductSupplier.product_id == product_id)
    )
    return list(res.all())


async def refresh_vendor_recommendations(
    db: AsyncSession,
    product_id: int,
    avg_daily_demand: float,
    current_stock: int,
) -> List[VendorRecommendation]:
    await db.execute(
        delete(VendorRecommendation).where(
            VendorRecommendation.product_id == product_id,
            VendorRecommendation.status == "ACTIVE",
        )
    )

    rows = await _supplier_rows_for_product(db, product_id)
    if not rows:
        return []
    supplier_rows: Dict[int, tuple] = {}
    for ps, supplier in rows:
        existing = supplier_rows.get(ps.supplier_id)
        if existing is None:
            supplier_rows[ps.supplier_id] = (ps, supplier)
            continue
        existing_ps, _ = existing
        existing_price = float(existing_ps.supplier_price or math.inf)
        current_price = float(ps.supplier_price or math.inf)
        existing_preferred = int(existing_ps.preferred_supplier_flag or 0)
        current_preferred = int(ps.preferred_supplier_flag or 0)
        if (current_preferred, -current_price) > (existing_preferred, -existing_price):
            supplier_rows[ps.supplier_id] = (ps, supplier)

    po_stats_res = await db.execute(
        select(
            PurchaseOrder.supplier_id,
            func.count(PurchaseOrder.id).label("total_pos"),
            func.coalesce(func.sum(PurchaseOrder.quantity), 0).label("total_units"),
            func.coalesce(func.avg(PurchaseOrder.unit_cost), 0).label("avg_unit_cost"),
        ).group_by(PurchaseOrder.supplier_id)
    )
    po_stats = {r.supplier_id: r for r in po_stats_res.all()}

    suppliers_data = [
        {
            "supplier_id": ps.supplier_id,
            "supplier_name": s.name,
            "reliability_score": float(s.reliability_score or 50),
            "avg_lead_time_days": float(ps.lead_time_days or s.avg_lead_time_days or 7),
            "defect_rate": float(s.defect_rate or 0.05),
            "avg_cost_index": float(s.avg_cost_index or 1.0),
            "supplier_price": float(ps.supplier_price or 0),
            "city": s.city or "Unknown",
            "on_time_delivery_rate": float(s.on_time_delivery_rate or 0.85),
            "minimum_order_qty": float(ps.minimum_order_qty or s.minimum_order_qty or 10),
            "total_purchase_orders": float(po_stats[ps.supplier_id].total_pos if ps.supplier_id in po_stats else 0),
            "total_units_ordered": float(po_stats[ps.supplier_id].total_units if ps.supplier_id in po_stats else 0),
            "avg_unit_cost": float(po_stats[ps.supplier_id].avg_unit_cost if ps.supplier_id in po_stats else 0),
            "cancelled_orders": 0.0,
            "delayed_orders": 0.0,
        }
        for ps, s in supplier_rows.values()
    ]

    ranked = _demand_aware_vendor_scores(suppliers_data, avg_daily_demand, current_stock)
    saved: List[VendorRecommendation] = []
    for r in ranked:
        rec = VendorRecommendation(
            product_id=product_id,
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
            composite_score=r["composite_score"],
            adjusted_score=r["adjusted_score"],
            supplier_price=r.get("supplier_price"),
            lead_time_days=r.get("lead_time_days"),
            days_stock_covers=r.get("days_stock_covers"),
            avg_daily_demand=r.get("avg_daily_demand"),
            recommendation=r.get("recommendation"),
            supplier_risk_label=r.get("supplier_risk_label"),
            rank_position=r.get("rank_position"),
            status="ACTIVE",
        )
        db.add(rec)
        saved.append(rec)
    return saved


def _compute_reorder_point(avg_daily: float, max_lead_days: int, safety_days: int = SAFETY_BUFFER_DAYS) -> int:
    """Reorder point = demand during lead time + safety buffer (monthly planning horizon)."""
    daily = max(avg_daily, 0.01)
    monthly_units = daily * 30
    coverage_days = max_lead_days + safety_days
    point = math.ceil(daily * coverage_days)
    return max(point, int(monthly_units / 30 * 3))


async def upsert_reorder_plan(
    db: AsyncSession,
    product_id: int,
    warehouse_id: int,
    avg_daily_demand: float,
    max_lead_time_days: int,
    inventory: Optional[Inventory],
) -> InventoryReorderPlan:
    monthly = avg_daily_demand * 30
    recommended = _compute_reorder_point(avg_daily_demand, max_lead_time_days)

    plan = await db.scalar(
        select(InventoryReorderPlan).where(
            InventoryReorderPlan.product_id == product_id,
            InventoryReorderPlan.warehouse_id == warehouse_id,
        )
    )
    if not plan:
        plan = InventoryReorderPlan(product_id=product_id, warehouse_id=warehouse_id)
        db.add(plan)

    plan.monthly_demand_units = round(monthly, 2)
    plan.avg_daily_demand = round(avg_daily_demand, 4)
    plan.max_lead_time_days = max_lead_time_days
    plan.recommended_reorder_point = recommended
    plan.safety_buffer_days = SAFETY_BUFFER_DAYS
    plan.coverage_days = max_lead_time_days + SAFETY_BUFFER_DAYS
    plan.computed_at = _utc_now()

    if inventory is not None:
        inventory.reorder_point = recommended

    return plan


async def run_product_forecast(
    db: AsyncSession,
    product: Product,
    inventory: Optional[Inventory],
    batch_id: str,
) -> SalesFeature:
    features = await upsert_sales_features(db, product, inventory)
    dates, quantities = await _product_sales_history(db, product.id)

    forecaster = DemandForecaster()
    forecast_start_date = dates[-1] if dates else None
    pred = forecaster.predict(
        dates=dates if len(dates) >= 10 else None,
        quantities=quantities if len(dates) >= 10 else None,
        current_stock=int(features.current_stock),
        forecast_days=FORECAST_HORIZON_DAYS,
        product_id=product.id,
        category=product.category or "Unknown",
        brand=product.brand or "Unknown",
        city="Delhi",
        selling_price=float(features.selling_price or 0),
        manufacturing_cost=float(features.manufacturing_cost or 0),
        safety_stock=float(features.safety_stock),
        inventory_turnover=float(features.inventory_turnover),
        start_date=forecast_start_date,
    )

    avg_daily = _non_negative_quantity(
        pred.get("avg_daily_demand") or features.avg_daily_sales_30d,
        minimum=0.01,
    )
    stockout_days = pred.get("stockout_in_days")

    await db.execute(
        delete(SalesForecast).where(
            SalesForecast.product_id == product.id,
            SalesForecast.batch_id == batch_id,
        )
    )

    for point in pred.get("forecast") or []:
        fdate = point.get("date") or str(point.get("ds", ""))[:10]
        if not fdate:
            continue
        predicted_qty = _non_negative_quantity(
            point.get("predicted") or point.get("yhat"),
            minimum=0.0,
        )
        lower_qty = _non_negative_quantity(
            point.get("lower") or point.get("yhat_lower"),
            minimum=0.0,
        )
        upper_qty = _non_negative_quantity(
            point.get("upper") or point.get("yhat_upper"),
            minimum=0.0,
        )
        upper_qty = max(upper_qty, predicted_qty, lower_qty)
        lower_qty = min(lower_qty, predicted_qty)
        db.add(
            SalesForecast(
                product_id=product.id,
                forecast_date=fdate,
                predicted_qty=predicted_qty,
                lower_qty=lower_qty,
                upper_qty=upper_qty,
                avg_daily_demand=avg_daily,
                stockout_in_days=stockout_days,
                model_used=pred.get("model_used"),
                batch_id=batch_id,
            )
        )

    rows = await _supplier_rows_for_product(db, product.id)
    max_lead = max(
        (int(ps.lead_time_days or s.avg_lead_time_days or 7) for ps, s in rows),
        default=7,
    )
    wh_id = inventory.warehouse_id if inventory else 1
    await upsert_reorder_plan(db, product.id, wh_id, avg_daily, max_lead, inventory)
    await refresh_vendor_recommendations(
        db, product.id, avg_daily, int(features.current_stock)
    )
    return features


async def refresh_all_forecasts(db: AsyncSession, *, force: bool = False) -> Dict[str, Any]:
    if not force and not await forecasts_are_empty(db):
        return {"ran": False, "reason": "Forecasts already exist. Pass refresh=true to recompute."}

    batch_id = f"batch-{uuid.uuid4().hex[:12]}"
    if force:
        await db.execute(delete(SalesForecast))

    products_res = await db.execute(
        select(Product, Inventory)
        .outerjoin(Inventory, Inventory.product_id == Product.id)
    )
    rows = products_res.all()
    count = 0
    for product, inventory in rows:
        try:
            await run_product_forecast(db, product, inventory, batch_id)
            count += 1
        except Exception as exc:
            logger.warning(f"Forecast failed for product {product.id}: {exc}")

    await db.flush()
    return {"ran": True, "products_processed": count, "batch_id": batch_id}


async def consume_vendor_recommendations(db: AsyncSession, product_id: int) -> None:
    """Remove active vendor recommendations after a purchase order is placed."""
    await db.execute(
        delete(VendorRecommendation).where(
            VendorRecommendation.product_id == product_id,
            VendorRecommendation.status == "ACTIVE",
        )
    )


async def get_forecast_series_from_db(
    db: AsyncSession,
    *,
    product_id: Optional[int] = None,
    product_ids: Optional[List[int]] = None,
    warehouse_id: Optional[int] = None,
    period: str = "weeks",
) -> List[Dict[str, Any]]:
    """Build chart series from persisted sales_forecasts + historical sales."""
    hist_q = select(
        func.substr(Sale.sale_date, 1, 10).label("day"),
        func.sum(Sale.quantity).label("actual"),
        func.sum(Sale.final_amount).label("actual_revenue"),
    )
    if product_id:
        hist_q = hist_q.where(Sale.product_id == product_id)
    if product_ids is not None:
        if not product_ids:
            return []
        hist_q = hist_q.where(Sale.product_id.in_(product_ids))
    if warehouse_id:
        hist_q = hist_q.where(Sale.warehouse_id == warehouse_id)
    hist_q = hist_q.group_by(func.substr(Sale.sale_date, 1, 10)).order_by(
        func.substr(Sale.sale_date, 1, 10)
    )
    hist_res = await db.execute(hist_q)
    hist_rows = hist_res.all()

    fc_q = (
        select(SalesForecast, Product.selling_price)
        .join(Product, Product.id == SalesForecast.product_id)
        .order_by(SalesForecast.forecast_date)
    )
    if product_id:
        fc_q = fc_q.where(SalesForecast.product_id == product_id)
    if product_ids is not None:
        if not product_ids:
            return []
        fc_q = fc_q.where(SalesForecast.product_id.in_(product_ids))
    fc_res = await db.execute(fc_q)
    fc_rows = fc_res.all()
    product_scope = [r.product_id for r, _selling_price in fc_rows]

    forecast_date_shift = timedelta(days=0)
    if hist_rows and fc_rows:
        try:
            latest_sale_date = max(datetime.fromisoformat(str(r.day)[:10]).date() for r in hist_rows)
            first_forecast_date = min(
                datetime.fromisoformat(str(r.forecast_date)[:10]).date()
                for r, _selling_price in fc_rows
            )
            expected_first_forecast = latest_sale_date + timedelta(days=1)
            if first_forecast_date != expected_first_forecast:
                forecast_date_shift = expected_first_forecast - first_forecast_date
        except ValueError:
            forecast_date_shift = timedelta(days=0)

    warehouse_share: Dict[int, float] = {}
    warehouse_dow_share: Dict[tuple[int, str], float] = {}
    if warehouse_id and product_scope:
        total_sales_q = (
            select(Sale.product_id, func.sum(Sale.quantity).label("qty"))
            .where(Sale.product_id.in_(product_scope))
            .group_by(Sale.product_id)
        )
        warehouse_sales_q = (
            select(Sale.product_id, func.sum(Sale.quantity).label("qty"))
            .where(Sale.product_id.in_(product_scope), Sale.warehouse_id == warehouse_id)
            .group_by(Sale.product_id)
        )
        total_stock_q = (
            select(Inventory.product_id, func.sum(Inventory.current_stock).label("stock"))
            .where(Inventory.product_id.in_(product_scope))
            .group_by(Inventory.product_id)
        )
        warehouse_stock_q = (
            select(Inventory.product_id, func.sum(Inventory.current_stock).label("stock"))
            .where(Inventory.product_id.in_(product_scope), Inventory.warehouse_id == warehouse_id)
            .group_by(Inventory.product_id)
        )

        total_sales = {
            product_id: float(qty or 0)
            for product_id, qty in (await db.execute(total_sales_q)).all()
        }
        warehouse_sales = {
            product_id: float(qty or 0)
            for product_id, qty in (await db.execute(warehouse_sales_q)).all()
        }
        total_stock = {
            product_id: float(stock or 0)
            for product_id, stock in (await db.execute(total_stock_q)).all()
        }
        warehouse_stock = {
            product_id: float(stock or 0)
            for product_id, stock in (await db.execute(warehouse_stock_q)).all()
        }

        for scoped_product_id in set(product_scope):
            total_qty = total_sales.get(scoped_product_id, 0.0)
            if total_qty > 0:
                warehouse_share[scoped_product_id] = warehouse_sales.get(scoped_product_id, 0.0) / total_qty
                continue
            total_qty = total_stock.get(scoped_product_id, 0.0)
            warehouse_share[scoped_product_id] = (
                warehouse_stock.get(scoped_product_id, 0.0) / total_qty if total_qty > 0 else 0.0
            )

        total_dow_q = (
            select(
                Sale.product_id,
                func.strftime("%w", Sale.sale_date).label("dow"),
                func.sum(Sale.quantity).label("qty"),
            )
            .where(Sale.product_id.in_(product_scope))
            .group_by(Sale.product_id, func.strftime("%w", Sale.sale_date))
        )
        warehouse_dow_q = (
            select(
                Sale.product_id,
                func.strftime("%w", Sale.sale_date).label("dow"),
                func.sum(Sale.quantity).label("qty"),
            )
            .where(Sale.product_id.in_(product_scope), Sale.warehouse_id == warehouse_id)
            .group_by(Sale.product_id, func.strftime("%w", Sale.sale_date))
        )
        total_dow_sales = {
            (product_id, str(dow)): float(qty or 0)
            for product_id, dow, qty in (await db.execute(total_dow_q)).all()
        }
        warehouse_dow_sales = {
            (product_id, str(dow)): float(qty or 0)
            for product_id, dow, qty in (await db.execute(warehouse_dow_q)).all()
        }
        for key, total_qty in total_dow_sales.items():
            if total_qty > 0:
                warehouse_dow_share[key] = warehouse_dow_sales.get(key, 0.0) / total_qty

    def _bucket(day: str) -> str:
        parsed = datetime.fromisoformat(day[:10])
        if period == "days":
            return parsed.date().isoformat()
        if period == "months":
            return parsed.strftime("%Y-%m")
        iso_year, iso_week, _ = parsed.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    hist_map: Dict[str, Dict[str, float]] = {}
    for r in hist_rows:
        b = _bucket(r.day)
        if b not in hist_map:
            hist_map[b] = {"actual": 0.0, "actual_revenue": 0.0}
        hist_map[b]["actual"] += float(r.actual or 0)
        hist_map[b]["actual_revenue"] += float(r.actual_revenue or 0)

    forecast_window_days = {"days": 10, "weeks": 112, "months": 120}.get(period, 112)
    daily_fc_map: Dict[str, Dict[str, float]] = {}
    for r, selling_price in fc_rows:
        forecast_day = datetime.fromisoformat(r.forecast_date[:10]) + forecast_date_shift
        day_key = str((forecast_day.weekday() + 1) % 7)
        share = (
            warehouse_dow_share.get((r.product_id, day_key), warehouse_share.get(r.product_id, 1.0))
            if warehouse_id
            else 1.0
        )
        day_label = forecast_day.date().isoformat()
        if day_label not in daily_fc_map:
            daily_fc_map[day_label] = {
                "predicted": 0.0,
                "lower": 0.0,
                "upper": 0.0,
                "forecast_revenue": 0.0,
                "lower_revenue": 0.0,
                "upper_revenue": 0.0,
            }
        unit_price = float(selling_price or 0)
        daily_fc_map[day_label]["predicted"] += float(r.predicted_qty or 0) * share
        daily_fc_map[day_label]["lower"] += float(r.lower_qty or 0) * share
        daily_fc_map[day_label]["upper"] += float(r.upper_qty or 0) * share
        daily_fc_map[day_label]["forecast_revenue"] += float(r.predicted_qty or 0) * unit_price * share
        daily_fc_map[day_label]["lower_revenue"] += float(r.lower_qty or 0) * unit_price * share
        daily_fc_map[day_label]["upper_revenue"] += float(r.upper_qty or 0) * unit_price * share

    if daily_fc_map:
        sorted_days = sorted(daily_fc_map)
        first_day = datetime.fromisoformat(sorted_days[0]).date()
        last_day = datetime.fromisoformat(sorted_days[-1]).date()
        desired_last_day = first_day + timedelta(days=forecast_window_days - 1)
        recent_days = sorted_days[-min(14, len(sorted_days)):]
        avg_daily = {
            key: sum(daily_fc_map[day][key] for day in recent_days) / max(len(recent_days), 1)
            for key in [
                "predicted",
                "lower",
                "upper",
                "forecast_revenue",
                "lower_revenue",
                "upper_revenue",
            ]
        }
        cursor = last_day + timedelta(days=1)
        while cursor <= desired_last_day:
            daily_fc_map[cursor.isoformat()] = dict(avg_daily)
            cursor += timedelta(days=1)

    fc_map: Dict[str, Dict[str, float]] = {}
    for day_label in sorted(daily_fc_map)[:forecast_window_days]:
        b = _bucket(day_label)
        if b not in fc_map:
            fc_map[b] = {
                "predicted": 0.0,
                "lower": 0.0,
                "upper": 0.0,
                "forecast_revenue": 0.0,
                "lower_revenue": 0.0,
                "upper_revenue": 0.0,
            }
        for key, value in daily_fc_map[day_label].items():
            fc_map[b][key] += value

    series: List[Dict[str, Any]] = []
    for period_key in sorted(hist_map.keys()):
        hist = hist_map[period_key]
        series.append({
            "date": period_key,
            "actual": int(hist["actual"]),
            "actualRevenue": round(hist["actual_revenue"], 2),
            "forecast": None,
            "lower": None,
            "upper": None,
            "forecastRevenue": None,
            "lowerRevenue": None,
            "upperRevenue": None,
        })

    if series and fc_map:
        last = series[-1]
        last["forecast"] = last["actual"]
        last["lower"] = last["actual"]
        last["upper"] = last["actual"]
        last["forecastRevenue"] = last["actualRevenue"]
        last["lowerRevenue"] = last["actualRevenue"]
        last["upperRevenue"] = last["actualRevenue"]

    for period_key in sorted(fc_map.keys()):
        fc = fc_map[period_key]
        series.append({
            "date": f"{period_key} (Forecast)",
            "actual": None,
            "forecast": int(fc["predicted"]),
            "lower": int(fc["lower"]),
            "upper": int(fc["upper"]),
            "actualRevenue": None,
            "forecastRevenue": round(fc["forecast_revenue"], 2),
            "lowerRevenue": round(fc["lower_revenue"], 2),
            "upperRevenue": round(fc["upper_revenue"], 2),
        })

    return series
