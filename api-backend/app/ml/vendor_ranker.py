"""
ml/vendor_ranker.py — Model 4: Multi-Criteria Vendor Recommendation + Supplier Risk Scoring.

Weighted scoring matrix ranks suppliers as BEST CHOICE | LOWEST COST | FASTEST DELIVERY.
Also integrates supplier_risk_model.pkl (XGBClassifier) to flag HIGH-RISK vendors.

Supplier risk artifact: supplier_risk_model.pkl + supplier_risk_metadata.pkl
Features (match train_supplier_risk_model.py exactly):
  city, reliability_score, defect_rate, on_time_delivery_rate,
  avg_lead_time_days, avg_cost_index, minimum_order_qty,
  total_purchase_orders, total_units_ordered, avg_unit_cost,
  cancelled_orders, delayed_orders
"""
from __future__ import annotations
import os
from typing import Any, Dict, List
import pandas as pd
import joblib
from loguru import logger
from .base import BaseMLModel

# Composite scoring weights (must sum to 1.0)
WEIGHTS = {
    "reliability_score":  0.35,  # Higher is better
    "avg_lead_time_days": 0.25,  # Lower is better
    "defect_rate":        0.25,  # Lower is better
    "avg_cost_index":     0.15,  # Lower is better
}

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


class VendorRanker(BaseMLModel):
    """
    Algorithmic multi-criteria decision ranking engine for supplier selection,
    augmented with XGBoost supplier risk classification.

    Recommendation labels:
      - BEST CHOICE:      Highest composite weighted score overall.
      - LOWEST COST:      Lowest avg_cost_index among active suppliers.
      - FASTEST DELIVERY: Lowest avg_lead_time_days among active suppliers.
      - HIGH RISK:        Supplier flagged HIGH-RISK by XGBoost model.
      - RECOMMENDED:      Top scorer but not uniquely best in any single dimension.
    """

    model_name    = "VendorRanker"
    model_version = "3.0.0"

    def predict(self, **kwargs: Any) -> Dict[str, Any]:
        """Adapter for BaseMLModel interface. Use rank() directly."""
        suppliers = kwargs.get("suppliers", [])
        return {"ranked": self.rank(suppliers)}

    def rank(self, suppliers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank suppliers by composite weighted score, then overlay XGBoost risk flags.

        Args:
            suppliers: List of dicts with keys:
                supplier_id, supplier_name, reliability_score,
                avg_lead_time_days, defect_rate, avg_cost_index,
                and optionally: city, on_time_delivery_rate, minimum_order_qty,
                total_purchase_orders, total_units_ordered, avg_unit_cost,
                cancelled_orders, delayed_orders

        Returns:
            Sorted list (descending score) with composite_score,
            supplier_risk_label, and recommendation label.
        """
        if not suppliers:
            return []

        # ── Min-Max Normalization ─────────────────────────────────────────────
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

        # ── Score each supplier ───────────────────────────────────────────────
        scored = []
        for s in suppliers:
            rel    = float(s.get("reliability_score")   or 50)
            lead   = float(s.get("avg_lead_time_days")  or 7)
            defect = float(s.get("defect_rate")         or 0.05)
            cost   = float(s.get("avg_cost_index")      or 1.0)

            composite = (
                WEIGHTS["reliability_score"]  * _normalize(rel,    "reliability_score",  True)
                + WEIGHTS["avg_lead_time_days"] * _normalize(lead,   "avg_lead_time_days", False)
                + WEIGHTS["defect_rate"]        * _normalize(defect, "defect_rate",        False)
                + WEIGHTS["avg_cost_index"]     * _normalize(cost,   "avg_cost_index",     False)
            )

            scored.append({
                "supplier_id":          s["supplier_id"],
                "supplier_name":        s["supplier_name"],
                "composite_score":      round(composite, 4),
                "reliability_score":    rel,
                "avg_lead_time_days":   lead,
                "defect_rate":          defect,
                "avg_cost_index":       cost,
                "supplier_risk_label":  "UNKNOWN",   # filled by risk model below
                "recommendation":       "",           # filled below
                # Pass-through context for risk model
                "_raw": s,
            })

        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # ── Supplier risk scoring via XGBoost ─────────────────────────────────
        risk_scores = self._batch_risk_score(scored)
        for i, s in enumerate(scored):
            s["supplier_risk_label"] = risk_scores.get(s["supplier_id"], "UNKNOWN")

        # ── Assign recommendation labels ──────────────────────────────────────
        best_lead = min(scored, key=lambda x: x["avg_lead_time_days"])
        best_cost = min(scored, key=lambda x: x["avg_cost_index"])

        for i, s in enumerate(scored):
            if s["supplier_risk_label"] == "HIGH":
                s["recommendation"] = "HIGH RISK"
            elif i == 0:
                s["recommendation"] = "BEST CHOICE"
            elif s["supplier_id"] == best_cost["supplier_id"]:
                s["recommendation"] = "LOWEST COST"
            elif s["supplier_id"] == best_lead["supplier_id"]:
                s["recommendation"] = "FASTEST DELIVERY"
            else:
                s["recommendation"] = "RECOMMENDED"

            # Remove internal raw key
            s.pop("_raw", None)

        return scored

    def _batch_risk_score(self, scored: List[Dict[str, Any]]) -> Dict[int, str]:
        """
        Run supplier_risk_model.pkl on all suppliers in one batch.
        Returns a dict: {supplier_id: "HIGH" | "LOW"}
        """
        model_path = os.path.join(_ARTIFACTS_DIR, "supplier_risk_model.pkl")
        meta_path  = os.path.join(_ARTIFACTS_DIR, "supplier_risk_metadata.pkl")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            logger.warning("Supplier risk model artifact not found. Skipping risk scoring.")
            return {}

        try:
            model    = joblib.load(model_path)
            meta     = joblib.load(meta_path)
            encoders = meta["encoders"]
            features = meta["features"]

            rows = []
            supplier_ids = []
            for s in scored:
                raw = s.get("_raw", s)
                row = {
                    "city":                   str(raw.get("city", "Unknown")),
                    "reliability_score":       float(raw.get("reliability_score") or 50),
                    "defect_rate":             float(raw.get("defect_rate") or 0.05),
                    "on_time_delivery_rate":   float(raw.get("on_time_delivery_rate") or 0.85),
                    "avg_lead_time_days":      float(raw.get("avg_lead_time_days") or 7),
                    "avg_cost_index":          float(raw.get("avg_cost_index") or 1.0),
                    "minimum_order_qty":       float(raw.get("minimum_order_qty") or 10),
                    "total_purchase_orders":   float(raw.get("total_purchase_orders") or 0),
                    "total_units_ordered":     float(raw.get("total_units_ordered") or 0),
                    "avg_unit_cost":           float(raw.get("avg_unit_cost") or 0),
                    "cancelled_orders":        float(raw.get("cancelled_orders") or 0),
                    "delayed_orders":          float(raw.get("delayed_orders") or 0),
                }
                # Encode categorical
                if "city" in encoders:
                    le  = encoders["city"]
                    val = str(row["city"])
                    row["city"] = int(le.transform([val])[0]) if val in le.classes_ else 0

                rows.append(row)
                supplier_ids.append(s["supplier_id"])

            df         = pd.DataFrame(rows)[features]
            predictions = model.predict(df)

            return {
                sid: ("HIGH" if pred == 1 else "LOW")
                for sid, pred in zip(supplier_ids, predictions)
            }

        except Exception as exc:
            logger.warning(f"Supplier risk batch scoring failed: {exc}")
            return {}
