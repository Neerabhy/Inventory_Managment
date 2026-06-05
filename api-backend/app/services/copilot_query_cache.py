"""
Curated Copilot query memory.

This is not a static-answer cache. It stores common business questions and the
tables they usually need so the UI can show useful examples and the backend can
use them as table-selection hints without bypassing live SQL execution.
"""
from __future__ import annotations

from typing import Dict, List


COMMON_QUERY_MEMORY: List[Dict[str, object]] = [
    {
        "query": "How are sales going this month?",
        "category": "sales",
        "tables": ["sales", "products"],
        "description": "Revenue, order count, units sold, and top products from live sales rows.",
    },
    {
        "query": "Tell me about laptop and headphone sales",
        "category": "sales",
        "tables": ["sales", "products"],
        "description": "Category-level sales comparison with revenue and units.",
    },
    {
        "query": "Forecast headphone demand next month",
        "category": "demand",
        "tables": ["products", "sales_forecasts"],
        "description": "Forecasted units and date range for a product category.",
    },
    {
        "query": "How much stock of Bose QuietComfort 45 at Delhi warehouse?",
        "category": "inventory",
        "tables": ["products", "inventory", "warehouses"],
        "description": "Warehouse-specific stock, available units, reservations, and incoming stock.",
    },
    {
        "query": "Which supplier is best for laptops?",
        "category": "supplier",
        "tables": ["v_product_supplier_matrix"],
        "description": "Supplier comparison using score, cost, delivery time, reliability, and defect rate.",
    },
    {
        "query": "Why are monitor returns increasing?",
        "category": "returns",
        "tables": ["products", "returns", "return_risk_predictions"],
        "description": "Return count, reasons, refund impact, fraud risk, and affected products.",
    },
]


def example_queries() -> List[str]:
    return [str(item["query"]) for item in COMMON_QUERY_MEMORY]


def cached_table_hints(query: str) -> List[str]:
    """Return table hints for very similar common questions."""
    normalized = " ".join(query.lower().split())
    hints: List[str] = []
    for item in COMMON_QUERY_MEMORY:
        cached = " ".join(str(item["query"]).lower().split())
        if cached == normalized:
            hints.extend(str(table) for table in item.get("tables", []))
            continue
        cached_terms = {term for term in cached.split() if len(term) > 3}
        query_terms = {term for term in normalized.split() if len(term) > 3}
        if cached_terms and len(cached_terms.intersection(query_terms)) >= min(3, len(cached_terms)):
            hints.extend(str(table) for table in item.get("tables", []))
    return list(dict.fromkeys(hints))
