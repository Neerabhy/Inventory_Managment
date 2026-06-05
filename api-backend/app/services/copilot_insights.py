"""
Reusable Copilot insight builders for page-level AI cards.

These functions collect compact, numeric evidence from the database and return
stable, frontend-friendly insight strings.

Dashboard insight format:
"Title — Description"

The frontend dashboard splits each insight into:
- title before "—"
- description after "—"
"""

from __future__ import annotations

import json
from asyncio import Lock
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.exc import OperationalError
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analytics import AiInsightCache, Return, Sale
from ..models.inventory import Inventory, Product
from ..models.logistics import Shipment
from ..models.predictions import SalesFeature, SalesForecast, VendorRecommendation
from .copilot_agent import _call_llm

INSIGHT_CACHE_TTL = timedelta(days=1)
_cache_write_locks: Dict[str, Lock] = {}


def _cache_lock(cache_key: str) -> Lock:
    lock = _cache_write_locks.get(cache_key)
    if lock is None:
        lock = Lock()
        _cache_write_locks[cache_key] = lock
    return lock


def _fallback_lines(*lines: str) -> List[str]:
    return [line for line in lines if line][:3]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_cache_part(value: Optional[object]) -> str:
    if value is None or value == "":
        return "all"
    return str(value)


def _parse_cache_time(value: str) -> Optional[datetime]:
    if not value:
        return None

    raw = value.strip()
    candidates = [raw]
    if raw.endswith("Z"):
        candidates.append(raw[:-1] + "+00:00")
    if " " in raw and "T" not in raw:
        candidates.append(raw.replace(" ", "T"))

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


async def _get_fresh_cached_insights(db: AsyncSession, cache_key: str) -> Optional[List[str]]:
    cached = await db.scalar(select(AiInsightCache).where(AiInsightCache.cache_key == cache_key))
    if not cached:
        return None

    generated_at = _parse_cache_time(cached.generated_at)
    if not generated_at or _utc_now() - generated_at >= INSIGHT_CACHE_TTL:
        return None

    try:
        payload = json.loads(cached.payload_json)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, list) and all(isinstance(item, str) for item in payload):
        return payload
    return None


async def _store_cached_insights(
    db: AsyncSession,
    *,
    cache_key: str,
    insight_type: str,
    insights: List[str],
) -> None:
    now = _utc_now().isoformat()
    payload_json = json.dumps(insights, separators=(",", ":"))
    cached = await db.scalar(select(AiInsightCache).where(AiInsightCache.cache_key == cache_key))

    if cached:
        cached.payload_json = payload_json
        cached.generated_at = now
        cached.insight_type = insight_type
    else:
        db.add(
            AiInsightCache(
                cache_key=cache_key,
                insight_type=insight_type,
                payload_json=payload_json,
                generated_at=now,
            )
        )

    await db.flush()


async def _cached_insights(
    db: AsyncSession,
    *,
    cache_key: str,
    insight_type: str,
    builder,
) -> List[str]:
    cached = await _get_fresh_cached_insights(db, cache_key)
    if cached is not None:
        return cached

    insights = await builder()
    async with _cache_lock(cache_key):
        try:
            await _store_cached_insights(
                db,
                cache_key=cache_key,
                insight_type=insight_type,
                insights=insights,
            )
        except OperationalError as exc:
            await db.rollback()
            logger.warning(f"Insight cache write skipped for {cache_key}: {exc}")
    return insights


def _split_insights(narrative: str, fallback: List[str]) -> List[str]:
    """
    Convert LLM output into clean insight lines.

    Handles bad model outputs like:
    Insight 1:
    Total revenue is ...
    Insight 2:
    Low stock is ...

    Also removes bullet markers and empty labels.
    """
    raw_lines = [
        line.strip(" -•*\t")
        for line in narrative.splitlines()
        if line.strip(" -•*\t")
    ]

    cleaned: List[str] = []

    skip_labels = {
        "insight",
        "insights",
        "recommendation",
        "recommendations",
        "action",
        "actions",
    }

    for line in raw_lines:
        normalized = line.strip().lower().rstrip(":")
        compact = normalized.replace(" ", "")

        # Skip useless headings like "Insight 1", "Insight 2:", etc.
        if normalized in skip_labels:
            continue
        if compact.startswith("insight") and compact.replace("insight", "").isdigit():
            continue
        if compact.startswith("recommendation") and compact.replace("recommendation", "").isdigit():
            continue

        # Remove numbering like "1. ", "2) ", "- 1. "
        line = line.strip()
        for prefix in ("1. ", "2. ", "3. ", "1) ", "2) ", "3) "):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()

        if line:
            cleaned.append(line)

    if not cleaned and narrative.strip():
        cleaned = [part.strip() for part in narrative.split(". ") if part.strip()]

    return (cleaned or fallback)[:3]


def _money_million(value: float) -> str:
    if value >= 10_000_000:
        return f"INR {value / 10_000_000:.2f} crore"
    if value >= 1_000_000:
        return f"INR {value / 1_000_000:.2f} million"
    return f"INR {round(value):,}"


async def build_dashboard_insights(db: AsyncSession) -> List[str]:
    return await _cached_insights(
        db,
        cache_key="dashboard",
        insight_type="dashboard",
        builder=lambda: _build_dashboard_insights_uncached(db),
    )


async def _build_dashboard_insights_uncached(db: AsyncSession) -> List[str]:
    """
    Stable dashboard insights.

    Important:
    Do not return labels like "Insight 1".
    The frontend expects strings in this format:
    "Title — Description"
    """
    revenue = float(
        (await db.scalar(select(func.coalesce(func.sum(Sale.final_amount), 0)))) or 0
    )

    sales_orders = int(
        (await db.scalar(select(func.count(Sale.id)))) or 0
    )

    units_sold = int(
        (await db.scalar(select(func.coalesce(func.sum(Sale.quantity), 0)))) or 0
    )

    returns = int(
        (await db.scalar(select(func.count(Return.id)))) or 0
    )

    delayed = int(
        (
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
        )
        or 0
    )

    total_shipments = int(
        (await db.scalar(select(func.count(Shipment.id)))) or 0
    )

    low_stock = int(
        (
            await db.scalar(
                select(func.count(Inventory.id)).where(
                    Inventory.current_stock <= Inventory.reorder_point
                )
            )
        )
        or 0
    )

    top_category_row = (
        await db.execute(
            select(Product.category, func.sum(Sale.final_amount).label("revenue"))
            .join(Sale, Sale.product_id == Product.id)
            .group_by(Product.category)
            .order_by(desc(func.sum(Sale.final_amount)))
            .limit(1)
        )
    ).first()

    top_category = top_category_row.category if top_category_row else None
    top_category_revenue = float(top_category_row.revenue or 0) if top_category_row else 0.0

    return_rate = round((returns / sales_orders * 100), 1) if sales_orders else 0.0
    delay_rate = round((delayed / total_shipments * 100), 1) if total_shipments else 0.0

    insights: List[str] = []

    if revenue > 0:
        if top_category:
            insights.append(
                f"Revenue concentration — Total revenue is {_money_million(revenue)}, with {top_category} contributing {_money_million(top_category_revenue)}. Focus promotions and stock planning around the strongest category."
            )
        else:
            insights.append(
                f"Revenue performance — Total revenue is {_money_million(revenue)} across {sales_orders} sales orders and {units_sold} sold units. Keep monitoring category-level demand."
            )

    if low_stock > 0:
        insights.append(
            f"Inventory action needed — {low_stock} inventory positions are at or below reorder point. Review replenishment before stockouts affect sales."
        )
    else:
        insights.append(
            "Inventory position healthy — No inventory rows are currently below reorder point. Continue monitoring fast-moving products."
        )

    if delayed > 0:
        insights.append(
            f"Logistics risk — {delayed} shipments are delayed, giving a delay rate of {delay_rate}%. Prioritize delayed orders and check supplier or route issues."
        )
    else:
        insights.append(
            "Logistics stable — No delayed shipments are currently flagged. Maintain current delivery performance."
        )

    if returns > 0:
        insights.append(
            f"Returns watch — {returns} returns are recorded, with an overall return rate of {return_rate}%. Check high-return products for quality or expectation mismatch."
        )

    return insights[:3]


async def build_product_recommendations(
    db: AsyncSession,
    sku: str,
    warehouse_id: Optional[int] = None,
) -> List[str]:
    cache_key = (
        f"product_recommendations:"
        f"sku:{_normalize_cache_part(sku)}:"
        f"warehouse:{_normalize_cache_part(warehouse_id)}"
    )
    return await _cached_insights(
        db,
        cache_key=cache_key,
        insight_type="product_recommendations",
        builder=lambda: _build_product_recommendations_uncached(db, sku, warehouse_id),
    )


async def _build_product_recommendations_uncached(
    db: AsyncSession,
    sku: str,
    warehouse_id: Optional[int] = None,
) -> List[str]:
    product = await db.scalar(select(Product).where(Product.sku == sku))
    if not product:
        return ["Product not found."]

    inventory_query = select(Inventory).where(Inventory.product_id == product.id)
    if warehouse_id is not None:
        inventory_query = inventory_query.where(Inventory.warehouse_id == warehouse_id)

    inventory = await db.scalar(inventory_query)

    warehouse_city = None
    if warehouse_id is not None:
        warehouse_row = (
            await db.execute(
                text("SELECT city FROM warehouses WHERE warehouse_id = :warehouse_id"),
                {"warehouse_id": warehouse_id},
            )
        ).mappings().first()
        warehouse_city = warehouse_row.get("city") if warehouse_row else None

    feature = await db.scalar(select(SalesFeature).where(SalesFeature.product_id == product.id))

    vendor_rows = (
        await db.execute(
            select(VendorRecommendation)
            .where(
                VendorRecommendation.product_id == product.id,
                VendorRecommendation.status == "ACTIVE",
            )
            .order_by(VendorRecommendation.rank_position)
            .limit(3)
        )
    ).scalars().all()

    evidence = {
        "page": "product_detail",
        "warehouse": {"warehouse_id": warehouse_id, "warehouse_city": warehouse_city},
        "product": {
            "sku": product.sku,
            "name": product.product_name,
            "category": product.category,
            "brand": product.brand,
            "selling_price": product.selling_price,
            "return_rate": product.return_rate,
            "defect_rate": product.defect_rate,
        },
        "inventory": {
            "current_stock": inventory.current_stock if inventory else None,
            "safety_stock": inventory.safety_stock if inventory else None,
            "reorder_point": inventory.reorder_point if inventory else None,
            "inventory_turnover": inventory.inventory_turnover if inventory else None,
        },
        "forecast": {
            "avg_daily_demand": feature.avg_daily_sales_30d if feature else None,
            "current_stock": feature.current_stock if feature else None,
        },
        "vendors": [
            {
                "supplier": row.supplier_name,
                "recommendation": row.recommendation,
                "score": row.adjusted_score or row.composite_score,
                "unit_cost": row.supplier_price,
                "lead_time_days": row.lead_time_days,
                "risk": row.supplier_risk_label,
            }
            for row in vendor_rows
        ],
    }

    fallback = _fallback_lines(
        f"Review safety stock for {product.product_name} against current demand.",
        "Use the highest-ranked supplier when lead time and cost are both acceptable.",
        "Monitor defect and return rates before expanding procurement volume.",
    )

    narrative = await _call_llm(
        "Generate exactly 3 short product recommendations for a catalog detail page.",
        evidence,
    )

    return _split_insights(narrative, fallback)


async def build_forecast_commentary(
    db: AsyncSession,
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
) -> List[str]:
    cache_key = (
        "forecast_commentary:"
        f"warehouse:{_normalize_cache_part(warehouse)}:"
        f"category:{_normalize_cache_part(category)}:"
        f"period:{_normalize_cache_part(period)}"
    )
    return await _cached_insights(
        db,
        cache_key=cache_key,
        insight_type="forecast_commentary",
        builder=lambda: _build_forecast_commentary_uncached(db, warehouse, category, period),
    )


async def _build_forecast_commentary_uncached(
    db: AsyncSession,
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
) -> List[str]:
    query = (
        select(
            Product.category,
            func.sum(SalesForecast.predicted_qty).label("forecast_qty"),
            func.avg(SalesForecast.avg_daily_demand).label("avg_daily"),
            func.min(SalesForecast.stockout_in_days).label("min_stockout_days"),
        )
        .join(Product, Product.id == SalesForecast.product_id)
    )

    if category and category != "all":
        query = query.where(Product.category == category)

    rows = (
        await db.execute(
            query.group_by(Product.category)
            .order_by(desc(func.sum(SalesForecast.predicted_qty)))
            .limit(5)
        )
    ).all()

    evidence = {
        "page": "demand_forecasting",
        "filters": {"warehouse": warehouse, "category": category, "period": period},
        "category_forecasts": [
            {
                "category": r.category or "Unknown",
                "forecast_qty": round(float(r.forecast_qty or 0), 2),
                "avg_daily_demand": round(float(r.avg_daily or 0), 2),
                "min_stockout_days": r.min_stockout_days,
            }
            for r in rows
        ],
    }

    fallback = _fallback_lines(
        "Prioritize procurement for the categories with the highest forecast quantity.",
        "Review low stockout-day products before approving new campaigns.",
        "Use forecast confidence bands to avoid over-ordering slow-moving categories.",
    )

    narrative = await _call_llm(
        "Generate exactly 3 short demand forecast commentary bullets with actions.",
        evidence,
    )

    return _split_insights(narrative, fallback)


def compact_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, default=str, separators=(",", ":"))
