"""
ml/dynamic_pricing.py — Dynamic Pricing Optimization using dynamic_pricing_model.pkl (XGBRegressor).

Trained artifact: dynamic_pricing_model.pkl + dynamic_pricing_metadata.pkl
Features (match train_dynamic_pricing_model.py exactly):
  category, brand, manufacturing_cost, current_stock,
  safety_stock, inventory_turnover, total_units_sold, total_orders

Target: selling_price  (predicted optimal price in INR)
"""
from __future__ import annotations
import os
from typing import Any, Dict

import pandas as pd
import joblib
from loguru import logger

from .base import BaseMLModel

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


class DynamicPricingModel(BaseMLModel):
    """
    XGBoost Regressor that recommends an optimised selling price based on
    inventory levels, demand velocity, and product attributes.

    Outputs:
      - recommended_price:  float — Predicted optimal selling price (INR).
      - current_price:      float — Current selling price passed in.
      - price_delta:        float — Difference (recommended − current).
      - price_delta_pct:    float — Percentage change.
      - model_used:         str   — "xgboost" | "margin_rule"
    """

    model_name    = "DynamicPricingModel"
    model_version = "1.0.0"

    def predict(
        self,
        category: str = "Unknown",
        brand: str = "Unknown",
        manufacturing_cost: float = 0.0,
        current_price: float = 0.0,
        current_stock: float = 0.0,
        safety_stock: float = 0.0,
        inventory_turnover: float = 0.0,
        total_units_sold: float = 0.0,
        total_orders: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            return self._xgboost_predict(
                category, brand, manufacturing_cost, current_price,
                current_stock, safety_stock, inventory_turnover,
                total_units_sold, total_orders,
            )
        except Exception as exc:
            logger.warning(f"DynamicPricingModel XGBoost failed: {exc}. Using margin rule.")
            return self._margin_rule(manufacturing_cost, current_price)

    def _xgboost_predict(
        self,
        category: str,
        brand: str,
        manufacturing_cost: float,
        current_price: float,
        current_stock: float,
        safety_stock: float,
        inventory_turnover: float,
        total_units_sold: float,
        total_orders: float,
    ) -> Dict[str, Any]:
        model_path = os.path.join(_ARTIFACTS_DIR, "dynamic_pricing_model.pkl")
        meta_path  = os.path.join(_ARTIFACTS_DIR, "dynamic_pricing_metadata.pkl")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            raise FileNotFoundError("Dynamic pricing model artifact not found.")

        model    = joblib.load(model_path)
        meta     = joblib.load(meta_path)
        encoders = meta["encoders"]
        features = meta["features"]

        row = {
            "category":            str(category),
            "brand":               str(brand),
            "manufacturing_cost":  float(manufacturing_cost),
            "current_stock":       float(current_stock),
            "safety_stock":        float(safety_stock),
            "inventory_turnover":  float(inventory_turnover),
            "total_units_sold":    float(total_units_sold),
            "total_orders":        float(total_orders),
        }

        for col in ["category", "brand"]:
            if col in encoders:
                le  = encoders[col]
                val = str(row[col])
                row[col] = int(le.transform([val])[0]) if val in le.classes_ else 0

        df_row            = pd.DataFrame([row])[features]
        recommended_price = float(model.predict(df_row)[0])
        recommended_price = max(recommended_price, manufacturing_cost * 1.05)

        delta     = recommended_price - current_price
        delta_pct = (delta / current_price * 100) if current_price > 0 else 0.0

        return {
            "recommended_price": round(recommended_price, 2),
            "current_price":     round(current_price, 2),
            "price_delta":       round(delta, 2),
            "price_delta_pct":   round(delta_pct, 2),
            "model_used":        "xgboost",
        }

    def _margin_rule(self, manufacturing_cost: float, current_price: float) -> Dict[str, Any]:
        """Fallback: recommend 40% margin over manufacturing cost."""
        recommended = manufacturing_cost * 1.40 if manufacturing_cost > 0 else current_price
        delta       = recommended - current_price
        delta_pct   = (delta / current_price * 100) if current_price > 0 else 0.0
        return {
            "recommended_price": round(recommended, 2),
            "current_price":     round(current_price, 2),
            "price_delta":       round(delta, 2),
            "price_delta_pct":   round(delta_pct, 2),
            "model_used":        "margin_rule",
        }
