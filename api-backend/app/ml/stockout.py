"""
ml/stockout.py — Stockout Risk Prediction using stockout_model.pkl (XGBClassifier).

Trained artifact: stockout_model.pkl + stockout_model_metadata.pkl
Features (match train_stockout_model.py exactly):
  product_id, current_stock, safety_stock, inventory_turnover,
  category, brand, selling_price, warehouse_city, total_sales

Target: stockout_risk  (1 = at/below safety_stock, 0 = safe)
"""
from __future__ import annotations
import os
from typing import Any, Dict

import pandas as pd
import joblib
from loguru import logger

from .base import BaseMLModel

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


class StockoutPredictor(BaseMLModel):
    """
    XGBoost classifier that predicts whether a product is at high stockout risk.

    Outputs:
      - stockout_risk:       int   — 1 (high risk) | 0 (safe)
      - stockout_probability: float — P(stockout) 0.0–1.0
      - risk_label:          str   — HIGH | LOW
      - model_used:          str   — "xgboost" | "rule_based"
    """

    model_name    = "StockoutPredictor"
    model_version = "1.0.0"

    def predict(
        self,
        product_id: int = 0,
        current_stock: float = 0.0,
        safety_stock: float = 0.0,
        inventory_turnover: float = 0.0,
        category: str = "Unknown",
        brand: str = "Unknown",
        selling_price: float = 0.0,
        warehouse_city: str = "Unknown",
        total_sales: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            return self._xgboost_predict(
                product_id, current_stock, safety_stock, inventory_turnover,
                category, brand, selling_price, warehouse_city, total_sales,
            )
        except Exception as exc:
            logger.warning(f"StockoutPredictor XGBoost failed: {exc}. Using rule-based fallback.")
            return self._rule_based(current_stock, safety_stock)

    def _xgboost_predict(
        self,
        product_id: int,
        current_stock: float,
        safety_stock: float,
        inventory_turnover: float,
        category: str,
        brand: str,
        selling_price: float,
        warehouse_city: str,
        total_sales: float,
    ) -> Dict[str, Any]:
        model_path = os.path.join(_ARTIFACTS_DIR, "stockout_model.pkl")
        meta_path  = os.path.join(_ARTIFACTS_DIR, "stockout_model_metadata.pkl")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            raise FileNotFoundError("Stockout model artifact not found.")

        model    = joblib.load(model_path)
        meta     = joblib.load(meta_path)
        encoders = meta["encoders"]
        features = meta["features"]

        row = {
            "product_id":          int(product_id),
            "current_stock":       float(current_stock),
            "safety_stock":        float(safety_stock),
            "inventory_turnover":  float(inventory_turnover),
            "category":            str(category),
            "brand":               str(brand),
            "selling_price":       float(selling_price),
            "warehouse_city":      str(warehouse_city),
            "total_sales":         float(total_sales),
        }

        # Encode categorical columns using training LabelEncoders
        for col in ["category", "brand", "warehouse_city"]:
            if col in encoders:
                le  = encoders[col]
                val = str(row[col])
                row[col] = int(le.transform([val])[0]) if val in le.classes_ else 0

        df_row = pd.DataFrame([row])[features]
        prob   = float(model.predict_proba(df_row)[0][1])
        risk   = int(model.predict(df_row)[0])

        return {
            "stockout_risk":        risk,
            "stockout_probability": round(prob, 4),
            "risk_label":           "HIGH" if risk == 1 else "LOW",
            "model_used":           "xgboost",
            "current_stock":        current_stock,
            "safety_stock":         safety_stock,
        }

    def _rule_based(self, current_stock: float, safety_stock: float) -> Dict[str, Any]:
        risk = 1 if current_stock <= safety_stock else 0
        return {
            "stockout_risk":        risk,
            "stockout_probability": 0.85 if risk else 0.10,
            "risk_label":           "HIGH" if risk else "LOW",
            "model_used":           "rule_based",
            "current_stock":        current_stock,
            "safety_stock":         safety_stock,
        }
