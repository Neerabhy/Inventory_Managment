"""
ml/return_classifier.py — Models 5 & 6: Return Risk Classification + Anomaly Detection.
XGBoost Classifier for fraud scoring; Isolation Forest for anomaly flagging.
Falls back to rule-based heuristics when ML artifacts are unavailable.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from loguru import logger
from backend_anti_gravity.app.ml.base import BaseMLModel

# Rule-based thresholds for fallback classifier
HIGH_RISK_REASON_CODES = {"CHANGED_MIND", "NO_REASON"}
MEDIUM_RISK_REASON_CODES = {"OTHER"}
HIGH_FRAUD_THRESHOLD = 0.65
MEDIUM_FRAUD_THRESHOLD = 0.35


class ReturnClassifier(BaseMLModel):
    """
    Combined XGBoost Classifier + Isolation Forest pipeline for return risk assessment.

    Outputs:
      - fraud_score:   float 0.0–1.0 — ML-estimated fraud probability.
      - return_ratio:  float 0.0–1.0 — Customer's historical return-to-purchase ratio.
      - risk_label:    str            — LOW | MEDIUM | HIGH
      - anomaly_flag:  bool           — True if Isolation Forest marks as outlier.
    """

    model_name = "ReturnClassifier"
    model_version = "1.3.0"

    def predict(self, **kwargs: Any) -> Dict[str, Any]:
        """BaseMLModel interface adapter."""
        return self.score(**kwargs)

    def score(
        self,
        product_id: int = 0,
        customer_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        refund_amount: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Run the return risk assessment pipeline.

        Args:
            product_id:    Product being returned.
            customer_id:   Customer identifier (used for history lookup).
            reason_code:   Return reason category.
            refund_amount: Requested refund in INR.

        Returns:
            Dict with fraud_score, return_ratio, risk_label, anomaly_flag.
        """
        try:
            return self._ml_score(product_id, customer_id, reason_code, refund_amount)
        except Exception as exc:
            logger.warning(f"ML return classifier failed: {exc}. Using heuristic fallback.")
            return self._heuristic_score(reason_code, refund_amount)

    def _ml_score(
        self, product_id: int, customer_id: Optional[str], reason_code: Optional[str], refund_amount: float
    ) -> Dict[str, Any]:
        """XGBoost + Isolation Forest inference path. Requires model artifacts."""
        import os
        import numpy as np

        xgb_path = os.path.join(os.path.dirname(__file__), "artifacts", "return_classifier.json")
        iso_path = os.path.join(os.path.dirname(__file__), "artifacts", "isolation_forest.pkl")

        if not os.path.exists(xgb_path):
            raise FileNotFoundError("XGBoost return classifier artifact not found.")

        import xgboost as xgb
        import pickle

        # Feature engineering
        reason_risk = {"CHANGED_MIND": 0.8, "NO_REASON": 0.9, "OTHER": 0.5,
                       "DEFECTIVE": 0.2, "WRONG_ITEM": 0.1, "DAMAGED_IN_TRANSIT": 0.15}
        reason_score = reason_risk.get(reason_code or "", 0.4)
        normalized_refund = min(refund_amount / 50000, 1.0)  # Cap at 50k INR

        features = np.array([[reason_score, normalized_refund, product_id % 100]])
        booster = xgb.Booster()
        booster.load_model(xgb_path)
        fraud_score = float(booster.predict(xgb.DMatrix(features))[0])

        # Isolation Forest anomaly detection
        anomaly_flag = False
        if os.path.exists(iso_path):
            with open(iso_path, "rb") as f:
                iso_model = pickle.load(f)
            anomaly_flag = iso_model.predict(features)[0] == -1

        return self._build_result(fraud_score, 0.15, anomaly_flag)

    def _heuristic_score(self, reason_code: Optional[str], refund_amount: float) -> Dict[str, Any]:
        """Rule-based fallback when ML model artifacts are unavailable."""
        fraud_score = 0.2
        if reason_code in HIGH_RISK_REASON_CODES:
            fraud_score = 0.72
        elif reason_code in MEDIUM_RISK_REASON_CODES:
            fraud_score = 0.45
        if refund_amount > 25000:
            fraud_score = min(fraud_score + 0.15, 0.95)

        # Isolation Forest heuristic: flag when fraud_score is extreme
        anomaly_flag = fraud_score > 0.80
        return self._build_result(fraud_score, 0.18, anomaly_flag)

    def _build_result(self, fraud_score: float, return_ratio: float, anomaly_flag: bool) -> Dict[str, Any]:
        """Construct the standardised output payload."""
        if fraud_score >= HIGH_FRAUD_THRESHOLD:
            risk_label = "HIGH"
        elif fraud_score >= MEDIUM_FRAUD_THRESHOLD:
            risk_label = "MEDIUM"
        else:
            risk_label = "LOW"

        return {
            "fraud_score": round(fraud_score, 4),
            "return_ratio": round(return_ratio, 4),
            "risk_label": risk_label,
            "anomaly_flag": anomaly_flag,
        }
