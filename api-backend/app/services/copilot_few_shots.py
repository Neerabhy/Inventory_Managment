"""Few-shot SQL patterns for the Copilot SQL generator.

Examples are deliberately schema-specific but not answer-specific. They teach
aggregation, grouping, and table/view choice for common business query shapes.
"""
from __future__ import annotations

from typing import Dict, List


FEW_SHOT_SQL_EXAMPLES: List[Dict[str, object]] = [
    {
        "tags": ["vendor", "supplier", "lowest", "price", "cost", "category"],
        "question": "List top vendors for laptops that offer the lowest price.",
        "tables": ["v_product_supplier_matrix"],
        "sql": """
SELECT supplier_name,
       supplier_code,
       COUNT(DISTINCT product_name) AS laptop_skus_covered,
       ROUND(AVG(supplier_price), 2) AS avg_supplier_price,
       MIN(supplier_price) AS lowest_supplier_price,
       MAX(supplier_price) AS highest_supplier_price,
       ROUND(AVG(lead_time_days), 1) AS avg_lead_time_days,
       ROUND(AVG(reliability_score), 3) AS avg_reliability_score,
       ROUND(AVG(defect_rate), 3) AS avg_defect_rate,
       ROUND(AVG(on_time_delivery_rate), 3) AS avg_on_time_delivery_rate,
       ROUND(AVG(composite_ai_score), 3) AS avg_composite_ai_score
FROM v_product_supplier_matrix
WHERE LOWER(category) LIKE LOWER('%Laptops%')
GROUP BY supplier_name, supplier_code
ORDER BY avg_supplier_price ASC, laptop_skus_covered DESC, avg_reliability_score DESC
LIMIT 10
""".strip(),
        "notes": "Rank suppliers, not product-supplier rows. Aggregate prices across category SKUs to avoid duplicate vendors.",
    },
    {
        "tags": ["vendor", "supplier", "fastest", "delivery", "category"],
        "question": "Which suppliers can deliver headphones fastest?",
        "tables": ["v_product_supplier_matrix"],
        "sql": """
SELECT supplier_name,
       supplier_code,
       COUNT(DISTINCT product_name) AS headphone_skus_covered,
       ROUND(AVG(lead_time_days), 1) AS avg_lead_time_days,
       MIN(lead_time_days) AS fastest_lead_time_days,
       ROUND(AVG(supplier_price), 2) AS avg_supplier_price,
       ROUND(AVG(reliability_score), 3) AS avg_reliability_score,
       ROUND(AVG(defect_rate), 3) AS avg_defect_rate
FROM v_product_supplier_matrix
WHERE LOWER(category) LIKE LOWER('%Headphones%')
GROUP BY supplier_name, supplier_code
ORDER BY avg_lead_time_days ASC, avg_reliability_score DESC, avg_supplier_price ASC
LIMIT 10
""".strip(),
        "notes": "For category-level vendor ranking, group by supplier and aggregate product-level rows.",
    },
    {
        "tags": ["stock", "inventory", "coverage", "forecast", "warehouse"],
        "question": "Show products likely to run out in Delhi warehouse next week.",
        "tables": ["products", "inventory", "warehouses", "sales_forecasts"],
        "sql": """
SELECT p.product_name,
       p.sku,
       w.warehouse_name,
       w.city AS warehouse_city,
       SUM(i.current_stock - i.reserved_stock) AS available_stock,
       SUM(i.incoming_stock) AS incoming_stock,
       ROUND(AVG(sf.avg_daily_demand), 2) AS avg_daily_demand,
       MIN(sf.stockout_in_days) AS stockout_in_days,
       ROUND(CASE
           WHEN AVG(sf.avg_daily_demand) > 0
           THEN SUM(i.current_stock - i.reserved_stock) / AVG(sf.avg_daily_demand)
           ELSE NULL
       END, 1) AS estimated_days_until_stockout
FROM inventory i
JOIN products p ON p.product_id = i.product_id
JOIN warehouses w ON w.warehouse_id = i.warehouse_id
LEFT JOIN sales_forecasts sf ON sf.product_id = p.product_id
WHERE LOWER(w.city) LIKE LOWER('%Delhi%')
GROUP BY p.product_id, w.warehouse_id
HAVING estimated_days_until_stockout <= 7 OR stockout_in_days <= 7
ORDER BY estimated_days_until_stockout ASC, available_stock ASC
LIMIT 10
""".strip(),
        "notes": "Use inventory plus forecasts for coverage; do not anchor forecast questions only to date('now').",
    },
]


def matching_few_shots(query: str, selected_tables: List[str], *, limit: int = 2) -> List[Dict[str, object]]:
    normalized = " ".join(query.lower().split())
    tokens = {token for token in normalized.split() if len(token) > 3}
    selected = set(selected_tables)
    scored = []
    for example in FEW_SHOT_SQL_EXAMPLES:
        tags = set(str(tag).lower() for tag in example.get("tags", []))
        tables = set(str(table) for table in example.get("tables", []))
        score = len(tokens.intersection(tags)) * 2 + len(selected.intersection(tables))
        if score > 0:
            scored.append((score, example))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [example for _score, example in scored[:limit]]
