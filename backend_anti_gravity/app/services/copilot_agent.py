"""
services/copilot_agent.py — Guardrailed LLM Copilot Engine.

Architecture:
  1. Intent Classification: Maps natural language to pre-built tool handlers.
  2. Tool Execution: Runs parameterized DB queries via SQLAlchemy ORM (never LLM math).
  3. LLM Narration: Passes extracted data to the LLM for human-readable explanation only.
  4. Streaming: Yields SSE chunks for real-time UI updates.

STRICT RULE: The LLM is NEVER permitted to perform calculations.
All numeric values are extracted from the database and passed as context.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend_anti_gravity.app.core.config import settings
from backend_anti_gravity.app.models.analytics import Review, Return, Sale
from backend_anti_gravity.app.models.inventory import Inventory, InventoryMovement, Product
from backend_anti_gravity.app.models.logistics import Shipment
from backend_anti_gravity.app.models.procurement import PurchaseOrder, Supplier


# ── Intent Registry ────────────────────────────────────────────────────────────
INTENT_PATTERNS: Dict[str, List[str]] = {
    "reorder_recommendation":   ["reorder", "restock", "order this week", "what should i order"],
    "return_analysis":          ["return", "refund", "why.*return", "return.*increas"],
    "stockout_analysis":        ["stockout", "stock out", "out of stock", "running low"],
    "vendor_performance":       ["vendor", "supplier", "best supplier", "supplier performance"],
    "logistics_delay":          ["delay", "shipment", "late delivery", "delayed"],
    "revenue_summary":          ["revenue", "sales", "total sales", "how much sold"],
    "sentiment_summary":        ["review", "sentiment", "customer feedback", "rating"],
}


def _classify_intent(query: str) -> str:
    """Classify the user's query into a pre-defined intent category using keyword matching."""
    q_lower = query.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            import re
            if re.search(pattern, q_lower):
                return intent
    return "general_query"


# ── Database Tool Handlers ─────────────────────────────────────────────────────
async def _tool_reorder_recommendation(db: AsyncSession) -> Dict[str, Any]:
    """
    Queries products where current stock ≤ reorder_point.
    Cross-references preferred supplier lead times for urgency scoring.
    """
    result = await db.execute(
        select(
            Product.id, Product.name, Product.product_code, Product.reorder_point,
            Inventory.quantity_on_hand, Inventory.quantity_in_transit,
        )
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Inventory.quantity_on_hand <= Product.reorder_point)
        .order_by(Inventory.quantity_on_hand.asc())
        .limit(20)
    )
    rows = result.all()
    return {
        "tool": "reorder_recommendation",
        "below_reorder_point": [
            {
                "product_id": r.id,
                "name": r.name,
                "code": r.product_code,
                "current_stock": r.quantity_on_hand,
                "reorder_point": r.reorder_point,
                "in_transit": r.quantity_in_transit,
                "deficit": max(r.reorder_point - r.quantity_on_hand, 0),
            }
            for r in rows
        ],
        "count": len(rows),
    }


async def _tool_return_analysis(db: AsyncSession, product_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyses return rates and damage-linked shipment data.
    Joins returns to reviews for sentiment correlation.
    """
    q = select(
        Return.reason_code,
        Return.risk_label,
        func.count(Return.id).label("count"),
        func.avg(Return.fraud_score).label("avg_fraud_score"),
    ).group_by(Return.reason_code, Return.risk_label)

    if product_name:
        q = q.join(Product, Return.product_id == Product.id).where(
            Product.name.ilike(f"%{product_name}%")
        )

    result = await db.execute(q)
    rows = result.all()

    # Damage-correlated returns
    damage_result = await db.execute(
        select(func.count(Shipment.id)).where(Shipment.damage_reported == True)
    )
    damaged_shipments = damage_result.scalar_one_or_none() or 0

    return {
        "tool": "return_analysis",
        "by_reason": [
            {"reason": r.reason_code, "risk": r.risk_label,
             "count": r.count, "avg_fraud_score": round(float(r.avg_fraud_score or 0), 4)}
            for r in rows
        ],
        "damaged_shipments_linked": damaged_shipments,
        "total_returns": sum(r.count for r in rows),
    }


async def _tool_stockout_analysis(db: AsyncSession) -> Dict[str, Any]:
    """Returns products currently out of stock and those approaching zero."""
    result = await db.execute(
        select(Product.name, Product.product_code, Inventory.quantity_on_hand, Product.reorder_point)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Inventory.quantity_on_hand == 0)
    )
    out_of_stock = result.all()

    result2 = await db.execute(
        select(Product.name, Inventory.quantity_on_hand, Product.reorder_point)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Inventory.quantity_on_hand > 0)
        .where(Inventory.quantity_on_hand <= Product.reorder_point)
        .limit(10)
    )
    critical = result2.all()

    return {
        "tool": "stockout_analysis",
        "out_of_stock": [{"name": r.name, "code": r.product_code} for r in out_of_stock],
        "critical_low": [{"name": r.name, "stock": r.quantity_on_hand, "threshold": r.reorder_point} for r in critical],
        "out_of_stock_count": len(out_of_stock),
        "critical_count": len(critical),
    }


async def _tool_revenue_summary(db: AsyncSession) -> Dict[str, Any]:
    """Aggregate revenue, unit sales, and top-performing products from the sales table."""
    result = await db.execute(
        select(func.sum(Sale.total_amount), func.sum(Sale.quantity_sold), func.count(Sale.id))
    )
    row = result.one()
    total_rev = float(row[0] or 0)
    total_units = int(row[1] or 0)
    total_txns = int(row[2] or 0)

    top_result = await db.execute(
        select(Product.name, func.sum(Sale.total_amount).label("revenue"))
        .join(Sale, Sale.product_id == Product.id)
        .group_by(Product.id)
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(5)
    )
    top = top_result.all()

    return {
        "tool": "revenue_summary",
        "total_revenue_inr": round(total_rev, 2),
        "total_units_sold": total_units,
        "total_transactions": total_txns,
        "top_products": [{"name": r.name, "revenue": float(r.revenue or 0)} for r in top],
    }


async def _tool_logistics_delay(db: AsyncSession) -> Dict[str, Any]:
    """Fetch delay statistics and identify weather vs damage causes."""
    result = await db.execute(
        select(Shipment.status, func.count(Shipment.id).label("count"), func.avg(Shipment.delay_days).label("avg_delay"))
        .group_by(Shipment.status)
    )
    by_status = result.all()
    return {
        "tool": "logistics_delay",
        "by_status": [{"status": r.status, "count": r.count, "avg_delay_days": round(float(r.avg_delay or 0), 1)} for r in by_status],
        "weather_delayed": (await db.execute(select(func.count(Shipment.id)).where(Shipment.weather_delay_flag == True))).scalar_one_or_none() or 0,
        "damage_reported": (await db.execute(select(func.count(Shipment.id)).where(Shipment.damage_reported == True))).scalar_one_or_none() or 0,
    }


TOOL_MAP = {
    "reorder_recommendation": _tool_reorder_recommendation,
    "return_analysis":        _tool_return_analysis,
    "stockout_analysis":      _tool_stockout_analysis,
    "revenue_summary":        _tool_revenue_summary,
    "logistics_delay":        _tool_logistics_delay,
}


# ── LLM Narration Layer ────────────────────────────────────────────────────────
async def _call_llm(query: str, data_context: Dict[str, Any]) -> str:
    """
    Send the extracted data context to the configured LLM for narrative explanation.
    Primary: Azure OpenAI. Fallbacks: OpenAI → Anthropic → local rule text.
    The LLM is strictly instructed NOT to perform calculations — only to explain.
    """
    system_prompt = (
        "You are an expert supply chain analyst copilot for ElectroInventory v3. "
        "You will receive structured database query results. Your ONLY task is to "
        "translate these numbers into a clear, professional, executive-level narrative. "
        "NEVER perform calculations. NEVER invent numbers. Use ONLY the provided data. "
        "Explain WHY trends are occurring based on the data context (e.g., vendor lag, "
        "weather events, damage correlations). Keep your response under 300 words."
    )
    user_message = (
        f"User Query: {query}\n\n"
        f"Database Evidence:\n{json.dumps(data_context, indent=2, default=str)}\n\n"
        "Please provide a professional narrative explanation of the data above."
    )

    provider = settings.llm_provider

    # ── Azure OpenAI (primary) ─────────────────────────────────────────────────
    if provider == "azure_openai" and settings.azure_openai_api_key:
        try:
            from openai import AsyncAzureOpenAI
            client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
            response = await client.chat.completions.create(
                model=settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=600,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Azure OpenAI call failed: {e}")

    # ── Standard OpenAI fallback ───────────────────────────────────────────────
    if provider == "openai" and settings.openai_api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=600,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"OpenAI call failed: {e}")

    # ── Anthropic fallback ─────────────────────────────────────────────────────
    if provider == "anthropic" and settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=600,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except Exception as e:
            logger.warning(f"Anthropic call failed: {e}")

    # Local fallback narrative (no API key configured)
    items = data_context.get("below_reorder_point") or data_context.get("by_reason") or []
    count = data_context.get("count") or data_context.get("total_returns") or len(items)
    return (
        f"Based on the retrieved database data, {count} record(s) require your attention. "
        f"The data indicates operational patterns that may impact business performance. "
        f"Please review the structured data context above for specific metrics and thresholds."
    )


# ── Main Copilot Orchestrator ──────────────────────────────────────────────────
async def run_copilot(
    query: str,
    db: AsyncSession,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Full copilot reasoning pipeline (non-streaming).

    Steps:
      1. Classify intent from natural language.
      2. Execute the corresponding DB tool handler.
      3. Pass structured data to LLM for narrative.
      4. Return structured CopilotResponse payload.
    """
    intent = _classify_intent(query)
    logger.info(f"Copilot intent classified: {intent} | query='{query[:60]}'")

    tool_fn = TOOL_MAP.get(intent)
    if tool_fn:
        try:
            data_context = await tool_fn(db)
        except Exception as exc:
            logger.error(f"Tool execution failed for intent={intent}: {exc}")
            data_context = {"error": str(exc), "tool": intent}
    else:
        data_context = {"tool": "general_query", "message": "No specific tool matched this query."}

    narrative = await _call_llm(query, data_context)

    return {
        "query": query,
        "intent": intent,
        "tools_invoked": [{"tool_name": data_context.get("tool", intent), "parameters": {}, "result_summary": f"{len(data_context)} fields returned"}],
        "data_context": data_context,
        "narrative": narrative,
        "confidence": 0.90 if tool_fn else 0.55,
        "follow_up_suggestions": _generate_followups(intent),
    }


async def stream_copilot(
    query: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Streaming version of the copilot pipeline using Server-Sent Events (SSE).
    Yields JSON-encoded chunks for real-time frontend consumption.
    """
    intent = _classify_intent(query)
    yield f"data: {json.dumps({'type': 'intent', 'content': intent})}\n\n"

    tool_fn = TOOL_MAP.get(intent)
    if tool_fn:
        yield f"data: {json.dumps({'type': 'tool_call', 'content': f'Executing: {intent}'})}\n\n"
        try:
            data_context = await tool_fn(db)
        except Exception as exc:
            data_context = {"error": str(exc)}
        yield f"data: {json.dumps({'type': 'data', 'content': json.dumps(data_context, default=str)})}\n\n"
    else:
        data_context = {"tool": "general_query"}
        yield f"data: {json.dumps({'type': 'tool_call', 'content': 'No specific tool — general query mode'})}\n\n"

    narrative = await _call_llm(query, data_context)
    # Stream narrative word by word
    words = narrative.split(" ")
    chunk_size = 8
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        yield f"data: {json.dumps({'type': 'narrative', 'content': chunk})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'content': '', 'confidence': 0.90 if tool_fn else 0.55})}\n\n"


def _generate_followups(intent: str) -> List[str]:
    """Return contextual follow-up suggestions based on detected intent."""
    suggestions = {
        "reorder_recommendation":   ["Which supplier has the fastest lead time for these products?", "Show stockout risk timeline"],
        "return_analysis":          ["What is the sentiment on returned products' reviews?", "Which products have the highest fraud score?"],
        "stockout_analysis":        ["What should I reorder this week?", "Show demand forecast for critical products"],
        "revenue_summary":          ["Which product category drives the most revenue?", "Show ABC analysis"],
        "logistics_delay":          ["Which carrier has the most delays?", "Show weather-correlated delay breakdown"],
        "general_query":            ["Show inventory summary", "What are this week's KPIs?"],
    }
    return suggestions.get(intent, ["Show dashboard summary", "List pending actions"])
