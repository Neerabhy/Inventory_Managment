from __future__ import annotations
import os
import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import joblib
from loguru import logger

from .base import BaseMLModel

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


class DemandForecaster(BaseMLModel):
    """
    Wraps two demand-prediction strategies:
      - XGBoost Regressor (universal_demand_model) for per-product point estimates (Primary).
      - Exponential Moving Average (EMA) as final fallback.
    """

    model_name    = "DemandForecaster"
    model_version = "2.0.0"

    def predict(
        self,
        dates: Optional[List[str]] = None,
        quantities: Optional[List[float]] = None,
        current_stock: int = 0,
        forecast_days: int = 30,
        # XGBoost path inputs (product context)
        product_id: int = 0,
        category: str = "Unknown",
        brand: str = "Unknown",
        city: str = "Unknown",
        selling_price: float = 0.0,
        manufacturing_cost: float = 0.0,
        safety_stock: float = 0.0,
        inventory_turnover: float = 0.0,
        start_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Forecast demand for the next `forecast_days` days.

        Returns:
            forecast:          List of {date, predicted, lower, upper}
            avg_daily_demand:  float
            stockout_in_days:  int | None
            model_used:        "xgboost" | "ema_fallback"
        """
        # Path 1: XGBoost demand model (Primary)
        if product_id > 0:
            try:
                return self._xgboost_forecast(
                    product_id, category, brand, city,
                    selling_price, manufacturing_cost,
                    current_stock, safety_stock, inventory_turnover,
                    forecast_days,
                    start_date,
                )
            except Exception as exc:
                logger.warning(f"XGBoost demand model failed: {exc}. Using EMA fallback.")

        # Path 2: EMA Fallback (triggered if product_id <= 0 or XGBoost fails)
        return self._ema_fallback(quantities or [], current_stock, forecast_days, start_date=start_date)

    # ── XGBoost demand model ──────────────────────────────────────────────────

    def _xgboost_forecast(
        self,
        product_id: int,
        category: str,
        brand: str,
        city: str,
        selling_price: float,
        manufacturing_cost: float,
        current_stock: int,
        safety_stock: float,
        inventory_turnover: float,
        forecast_days: int,
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Uses universal_demand_model.pkl to predict daily quantity.
        Features match train_demand_model.py exactly:
          product_id, category, brand, city, selling_price, manufacturing_cost,
          current_stock, safety_stock, inventory_turnover, month, day, weekday, is_weekend
        """
        model_path = os.path.join(_ARTIFACTS_DIR, "universal_demand_model.pkl")
        meta_path  = os.path.join(_ARTIFACTS_DIR, "universal_demand_metadata.pkl")
        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            raise FileNotFoundError("universal_demand_model.pkl artifact not found.")

        model    = joblib.load(model_path)
        meta     = joblib.load(meta_path)
        encoders = meta["encoders"]
        features = meta["features"]

        base_date = self._resolve_start_date(start_date)
        forecasted = []
        daily_preds = []

        for i in range(1, forecast_days + 1):
            future_date = base_date + datetime.timedelta(days=i)
            row = {
                "product_id":          product_id,
                "category":            str(category),
                "brand":               str(brand),
                "city":                str(city),
                "selling_price":       float(selling_price),
                "manufacturing_cost":  float(manufacturing_cost),
                "current_stock":       float(current_stock),
                "safety_stock":        float(safety_stock),
                "inventory_turnover":  float(inventory_turnover),
                "month":               int(future_date.month),
                "day":                 int(future_date.day),
                "weekday":             int(future_date.weekday()),
                "is_weekend":          int(future_date.weekday() in [5, 6]),
            }
            
            # Encode categoricals
            for col in ["category", "brand", "city"]:
                if col in encoders:
                    le  = encoders[col]
                    val = str(row[col])
                    row[col] = int(le.transform([val])[0]) if val in le.classes_ else 0

            df_row = pd.DataFrame([row])[features]
            pred   = float(model.predict(df_row)[0])
            
            # Safety guard: Prevent negative predictions from the model
            pred   = max(pred, 0.01)
            daily_preds.append(pred)
            
            forecasted.append({
                "date":      future_date.strftime("%Y-%m-%d"),
                "predicted": round(pred, 2),
                "lower":     round(pred * 0.80, 2),
                "upper":     round(pred * 1.20, 2),
            })

        avg_daily        = sum(daily_preds) / len(daily_preds)
        stockout_in_days = int(current_stock / avg_daily) if current_stock > 0 else None

        return {
            "model_used":       "xgboost",
            "forecast":         forecasted,
            "avg_daily_demand": round(avg_daily, 2),
            "stockout_in_days": stockout_in_days,
            "current_stock":    current_stock,
            "fallback":         False,
        }

    @staticmethod
    def _resolve_start_date(value: Optional[str]) -> datetime.date:
        if value:
            try:
                return datetime.date.fromisoformat(value[:10])
            except ValueError:
                pass
        return datetime.date.today()

    # ── EMA fallback ─────────────────────────────────────────────────────────

    def _ema_fallback(
        self,
        quantities: List[float],
        current_stock: int,
        forecast_days: int,
        alpha: float = 0.3,
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not quantities:
            return {
                **self._fallback_response("No historical sales data available"),
                "model_used": "ema_fallback",
                "avg_daily_demand": 0,
                "stockout_in_days": None,
                "forecast": [],
            }

        ema = quantities[0]
        for q in quantities[1:]:
            ema = alpha * q + (1 - alpha) * ema

        avg_daily        = max(ema, 0.01)
        stockout_in_days = int(current_stock / avg_daily) if current_stock > 0 else None
        base_date        = self._resolve_start_date(start_date)
        forecast_dates   = [
            (base_date + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(1, forecast_days + 1)
        ]

        return {
            "model_used":       "ema_fallback",
            "forecast": [
                {"date": d, "predicted": round(avg_daily, 2),
                 "lower": round(avg_daily * 0.8, 2), "upper": round(avg_daily * 1.2, 2)}
                for d in forecast_dates
            ],
            "avg_daily_demand": round(avg_daily, 2),
            "stockout_in_days": stockout_in_days,
            "current_stock":    current_stock,
            "fallback":         True,
            "reason":           "XGBoost bypassed or failed — using EMA approximation",
        }
