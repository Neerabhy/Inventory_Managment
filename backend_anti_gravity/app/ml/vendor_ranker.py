"""
ml/vendor_ranker.py — Model 4: Multi-Criteria Vendor Recommendation System.
Weighted scoring matrix ranking suppliers as BEST CHOICE | LOWEST COST | FASTEST DELIVERY.
"""
from __future__ import annotations
from typing import Any, Dict, List
from backend_anti_gravity.app.ml.base import BaseMLModel

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "reliability_score": 0.35,   # Higher is better — normalized 0-100
    "avg_lead_time_days": 0.25,  # Lower is better
    "defect_rate": 0.25,         # Lower is better
    "avg_cost_index": 0.15,      # Lower is better
}


class VendorRanker(BaseMLModel):
    """
    Algorithmic multi-criteria decision ranking engine for supplier selection.
    Applies a Weighted Normalized Score Matrix across four performance dimensions.

    Recommendation labels:
      - BEST CHOICE:      Highest composite weighted score overall.
      - LOWEST COST:      Lowest avg_cost_index among active suppliers.
      - FASTEST DELIVERY: Lowest avg_lead_time_days among active suppliers.
      - RECOMMENDED:      Top scorer but not uniquely best in any single dimension.
    """

    model_name = "VendorRanker"
    model_version = "2.0.0"

    def predict(self, **kwargs: Any) -> Dict[str, Any]:
        """Adapter for BaseMLModel interface. Use rank() directly."""
        suppliers = kwargs.get("suppliers", [])
        return {"ranked": self.rank(suppliers)}

    def rank(self, suppliers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank a list of supplier dictionaries by composite weighted score.

        Args:
            suppliers: List of dicts with keys:
                supplier_id, supplier_name, reliability_score,
                avg_lead_time_days, defect_rate, avg_cost_index

        Returns:
            Sorted list (descending score) with composite_score and recommendation label.
        """
        if not suppliers:
            return []

        # ── Min-Max Normalization ────────────────────────────────────
        def _safe_min(key: str) -> float:
            return min(float(s.get(key, 0) or 0) for s in suppliers)

        def _safe_max(key: str) -> float:
            return max(float(s.get(key, 0) or 0) for s in suppliers)

        ranges = {
            k: (_safe_min(k), _safe_max(k))
            for k in ["reliability_score", "avg_lead_time_days", "defect_rate", "avg_cost_index"]
        }

        def _normalize(value: float, key: str, higher_is_better: bool) -> float:
            lo, hi = ranges[key]
            if hi == lo:
                return 1.0
            normalized = (value - lo) / (hi - lo)
            return normalized if higher_is_better else (1.0 - normalized)

        scored = []
        for s in suppliers:
            rel = float(s.get("reliability_score") or 50)
            lead = float(s.get("avg_lead_time_days") or 7)
            defect = float(s.get("defect_rate") or 0.05)
            cost = float(s.get("avg_cost_index") or 1.0)

            composite = (
                WEIGHTS["reliability_score"] * _normalize(rel, "reliability_score", True)
                + WEIGHTS["avg_lead_time_days"] * _normalize(lead, "avg_lead_time_days", False)
                + WEIGHTS["defect_rate"] * _normalize(defect, "defect_rate", False)
                + WEIGHTS["avg_cost_index"] * _normalize(cost, "avg_cost_index", False)
            )

            scored.append({
                "supplier_id": s["supplier_id"],
                "supplier_name": s["supplier_name"],
                "composite_score": round(composite, 4),
                "reliability_score": rel,
                "avg_lead_time_days": lead,
                "defect_rate": defect,
                "avg_cost_index": cost,
                "recommendation": "",  # Filled below
            })

        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # ── Assign Recommendation Labels ─────────────────────────────
        best_lead = min(scored, key=lambda x: x["avg_lead_time_days"])
        best_cost = min(scored, key=lambda x: x["avg_cost_index"])

        for i, s in enumerate(scored):
            if i == 0:
                s["recommendation"] = "BEST CHOICE"
            elif s["supplier_id"] == best_cost["supplier_id"]:
                s["recommendation"] = "LOWEST COST"
            elif s["supplier_id"] == best_lead["supplier_id"]:
                s["recommendation"] = "FASTEST DELIVERY"
            else:
                s["recommendation"] = "RECOMMENDED"

        return scored
