"""
ml/cost_prediction.py — Logistics Cost, Delay Probability & Delivery ETA.

TWO trained XGBoost models used (matching model-training scripts exactly):
  1. shipment_delay_model.pkl   — XGBClassifier → delay_probability
     Features: logistics_provider, source_city, destination_city, transportation_mode,
               distance_km, expected_delivery_days, weather_delay_flag, remote_area_flag,
               shipping_cost
  2. delivery_eta_model.pkl     — XGBRegressor  → predicted_delivery_days
     Features: source_city, destination_city, transportation_mode, logistics_provider,
               distance_km, expected_delivery_days, weather_delay_flag, remote_area_flag,
               shipping_cost

Shipping cost is always calculated via the calibrated rule engine (no separate ML for cost).
"""
from __future__ import annotations
import os
from typing import Any, Dict

import pandas as pd
import joblib
from loguru import logger

from .base import BaseMLModel

BASE_COST_PER_KM       = 4.5
WEIGHT_COST_FACTOR     = 12.0
FRAGILE_SURCHARGE      = 150.0
WEATHER_DELAY_SURCHARGE = 80.0
BASE_DELAY_PROB        = 0.08
WEATHER_DELAY_BOOST    = 0.35
FRAGILE_DELAY_BOOST    = 0.05

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


class CostPredictor(BaseMLModel):
    model_name    = "CostPredictor"
    model_version = "2.0.0"

    def predict(
        self,
        distance_km: float,
        weight_kg: float,
        fragile_flag: bool = False,
        weather_delay_flag: bool = False,
        source_city: str = "Delhi",
        destination_city: str = "Mumbai",
        carrier: str = "Logistics_A",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            return self._xgboost_predict(
                distance_km, weight_kg, fragile_flag, weather_delay_flag,
                source_city, destination_city, carrier
            )
        except Exception as exc:
            logger.warning(f"XGBoost prediction failed: {exc}. Using rule engine.")
            return self._rule_engine(distance_km, weight_kg, fragile_flag, weather_delay_flag)

    def _xgboost_predict(
        self,
        distance_km: float,
        weight_kg: float,
        fragile_flag: bool,
        weather_delay_flag: bool,
        source_city: str,
        destination_city: str,
        carrier: str,
    ) -> Dict[str, Any]:
        delay_model_path = os.path.join(_ARTIFACTS_DIR, "shipment_delay_model.pkl")
        delay_meta_path  = os.path.join(_ARTIFACTS_DIR, "shipment_delay_metadata.pkl")
        eta_model_path   = os.path.join(_ARTIFACTS_DIR, "delivery_eta_model.pkl")
        eta_meta_path    = os.path.join(_ARTIFACTS_DIR, "delivery_eta_metadata.pkl")

        if not os.path.exists(delay_model_path):
            raise FileNotFoundError("Shipment delay model artifact not found.")
        if not os.path.exists(eta_model_path):
            raise FileNotFoundError("Delivery ETA model artifact not found.")

        delay_model    = joblib.load(delay_model_path)
        delay_meta     = joblib.load(delay_meta_path)
        delay_encoders = delay_meta["encoders"]
        delay_features = delay_meta["features"]

        eta_model    = joblib.load(eta_model_path)
        eta_meta     = joblib.load(eta_meta_path)
        eta_encoders = eta_meta["encoders"]
        eta_features = eta_meta["features"]

        # Cost always from rule engine
        estimated_cost = (
            distance_km * BASE_COST_PER_KM
            + weight_kg * WEIGHT_COST_FACTOR
            + (FRAGILE_SURCHARGE if fragile_flag else 0)
            + (WEATHER_DELAY_SURCHARGE if weather_delay_flag else 0)
        )
        expected_days = max(1, int(distance_km / 250))
        remote_flag   = 1 if distance_km > 750 else 0

        base = {
            "logistics_provider":     str(carrier),
            "source_city":            str(source_city),
            "destination_city":       str(destination_city),
            "transportation_mode":    "Road",
            "distance_km":            float(distance_km),
            "expected_delivery_days": float(expected_days),
            "weather_delay_flag":     int(1 if weather_delay_flag else 0),
            "remote_area_flag":       int(remote_flag),
            "shipping_cost":          float(estimated_cost),
        }

        # ── DELAY MODEL (train_delay_model.py features) ───────────────────────
        delay_dict = {k: base[k] for k in delay_features if k in base}
        for col in ["logistics_provider", "source_city", "destination_city",
                    "transportation_mode", "shipment_status"]:
            if col in delay_encoders and col in delay_dict:
                le = delay_encoders[col]
                val = str(delay_dict[col])
                delay_dict[col] = int(le.transform([val])[0]) if val in le.classes_ else 0
        delay_df   = pd.DataFrame([delay_dict])[delay_features]
        delay_prob = float(delay_model.predict_proba(delay_df)[0][1])

        # ── ETA MODEL (train_delivery_pred_model.py features) ────────────────
        eta_dict = {k: base[k] for k in eta_features if k in base}
        for col in ["source_city", "destination_city", "transportation_mode", "logistics_provider"]:
            if col in eta_encoders and col in eta_dict:
                le = eta_encoders[col]
                val = str(eta_dict[col])
                eta_dict[col] = int(le.transform([val])[0]) if val in le.classes_ else 0
        eta_df           = pd.DataFrame([eta_dict])[eta_features]
        predicted_eta    = float(eta_model.predict(eta_df)[0])

        return {
            "estimated_cost_inr":      round(max(estimated_cost, 0), 2),
            "delay_probability":       round(min(delay_prob, 1.0), 4),
            "predicted_delivery_days": round(max(predicted_eta, 1.0), 1),
            "confidence":              0.89,
            "model_used":              "xgboost",
        }

    def _rule_engine(
        self, distance_km: float, weight_kg: float,
        fragile_flag: bool, weather_delay_flag: bool,
    ) -> Dict[str, Any]:
        cost = (
            distance_km * BASE_COST_PER_KM
            + weight_kg * WEIGHT_COST_FACTOR
            + (FRAGILE_SURCHARGE if fragile_flag else 0)
            + (WEATHER_DELAY_SURCHARGE if weather_delay_flag else 0)
        )
        delay_prob = BASE_DELAY_PROB
        if weather_delay_flag:
            delay_prob += WEATHER_DELAY_BOOST
        if fragile_flag:
            delay_prob += FRAGILE_DELAY_BOOST
        return {
            "estimated_cost_inr":      round(cost, 2),
            "delay_probability":       round(min(delay_prob, 1.0), 4),
            "predicted_delivery_days": float(max(1, int(distance_km / 250))),
            "confidence":              0.72,
            "model_used":              "rule_engine",
        }
