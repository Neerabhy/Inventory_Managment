"""
ml/demand_forecast.py — Model 1: Sales Demand Forecasting & Stockout Prediction via Prophet.
Falls back to exponential moving average when data is insufficient for Prophet training.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from loguru import logger
from backend_anti_gravity.app.ml.base import BaseMLModel


class DemandForecaster(BaseMLModel):
    """
    Wraps Meta's Prophet to forecast future sales demand.
    Also computes an estimated stockout date by projecting current stock
    against predicted daily demand velocity.

    Prophet is instantiated lazily to avoid import overhead at startup.
    Falls back to EMA-based rules when fewer than 10 historical data points exist.
    """

    model_name = "DemandForecaster"
    model_version = "1.2.0"

    def predict(
        self,
        dates: Optional[List[str]] = None,
        quantities: Optional[List[float]] = None,
        current_stock: int = 0,
        forecast_days: int = 30,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Forecast demand for the next `forecast_days` days.

        Args:
            dates:          List of ISO date strings (historical sale dates).
            quantities:     Corresponding units sold per date.
            current_stock:  Current quantity on hand.
            forecast_days:  Horizon to predict in days.

        Returns:
            Dict containing:
              - forecast: List of {ds, yhat, yhat_lower, yhat_upper}
              - avg_daily_demand: float
              - stockout_in_days: int | None
              - model_used: "prophet" | "ema_fallback"
        """
        if not dates or not quantities or len(dates) < 10:
            return self._ema_fallback(quantities or [], current_stock, forecast_days)

        try:
            from prophet import Prophet  # type: ignore
            import pandas as pd

            df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": quantities})
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=True,
                interval_width=0.80,
            )
            model.fit(df)
            future = model.make_future_dataframe(periods=forecast_days)
            forecast = model.predict(future)

            tail = forecast.tail(forecast_days)
            avg_daily = float(tail["yhat"].mean())
            avg_daily = max(avg_daily, 0.01)

            stockout_in_days: Optional[int] = None
            if current_stock > 0:
                stockout_in_days = int(current_stock / avg_daily)

            return {
                "model_used": "prophet",
                "forecast": tail[["ds", "yhat", "yhat_lower", "yhat_upper"]]
                .rename(columns={"ds": "date", "yhat": "predicted", "yhat_lower": "lower", "yhat_upper": "upper"})
                .assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d"))
                .to_dict(orient="records"),
                "avg_daily_demand": round(avg_daily, 2),
                "stockout_in_days": stockout_in_days,
                "current_stock": current_stock,
                "fallback": False,
            }

        except Exception as exc:
            logger.warning(f"Prophet forecast failed: {exc}. Falling back to EMA.")
            return self._ema_fallback(quantities or [], current_stock, forecast_days)

    def _ema_fallback(
        self,
        quantities: List[float],
        current_stock: int,
        forecast_days: int,
        alpha: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Exponential Moving Average fallback when Prophet cannot be trained.
        Applies alpha-smoothing to the available sales history.
        """
        if not quantities:
            return {**self._fallback_response("No historical sales data available"),
                    "model_used": "ema_fallback", "avg_daily_demand": 0, "stockout_in_days": None}

        ema = quantities[0]
        for q in quantities[1:]:
            ema = alpha * q + (1 - alpha) * ema

        avg_daily = max(ema, 0.01)
        stockout_in_days = int(current_stock / avg_daily) if current_stock > 0 else None

        return {
            "model_used": "ema_fallback",
            "forecast": [{"date": f"day_{i + 1}", "predicted": round(avg_daily, 2)} for i in range(min(forecast_days, 7))],
            "avg_daily_demand": round(avg_daily, 2),
            "stockout_in_days": stockout_in_days,
            "current_stock": current_stock,
            "fallback": True,
            "reason": "Insufficient data for Prophet — using EMA approximation",
        }
