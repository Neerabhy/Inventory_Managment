"""
ml/return_classifier.py — Models 5 & 6: Return Risk Classification + Fraud Detection.

TWO trained XGBoost models are used:
  1. universal_fraud_detection_model.pkl    → fraud_score (0.0–1.0)
     Features: product_id, customer_id, category, brand, city, selling_price,
               quantity, final_amount, shipping_cost, transportation_mode,
               delayed_flag, refund_amount, refund_without_pickup,
               month, weekday, is_weekend
     (Matches train_fraud_model.py exactly)

  2. universal_return_prediction_model.pkl  → return_probability (0.0–1.0)
     Features: product_id, customer_id, category, brand, city, selling_price,
               manufacturing_cost, quantity, final_amount, transportation_mode,
               shipping_cost, month, weekday, is_weekend
     (Matches train_return_model.py exactly)

  3. isolation_forest.pkl                  → anomaly_flag (bool)

Falls back to rule-based heuristics when ML artifacts are unavailable.
"""
from __future__ import annotations
import os
import datetime
import sqlite3
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import joblib
from loguru import logger

from .base import BaseMLModel

# Rule-based thresholds
HIGH_FRAUD_THRESHOLD = 0.65
MEDIUM_FRAUD_THRESHOLD = 0.35
HIGH_RISK_REASON_CODES = {"CHANGED_MIND", "NO_REASON"}
MEDIUM_RISK_REASON_CODES = {"OTHER"}

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def _resolve_db_path() -> Optional[str]:
    """Resolve the SQLite database path from several candidate locations."""
    candidates = [
        "inventory-database/electronics_inventory_v3.db",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "inventory-database", "electronics_inventory_v3.db")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "inventory-database", "electronics_inventory_v3.db")),
        "C:/Users/NeerajKumarKhandelwa/Downloads/data_clean/inventory-database/electronics_inventory_v3.db",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


class ReturnClassifier(BaseMLModel):
    """
    Combined XGBoost Classifier + Isolation Forest pipeline for return risk assessment.

    Outputs:
      - fraud_score:          float 0.0–1.0  — ML-estimated fraud probability (from fraud model).
      - return_probability:   float 0.0–1.0  — Probability this sale will be returned (from return model).
      - return_ratio:         float 0.0–1.0  — Customer's historical return-to-purchase ratio.
      - risk_label:           str            — LOW | MEDIUM | HIGH (derived from fraud_score).
      - anomaly_flag:         bool           — True if Isolation Forest marks as outlier.
    """

    model_name = "ReturnClassifier"
    model_version = "2.0.0"

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
            Dict with fraud_score, return_probability, return_ratio, risk_label, anomaly_flag.
        """
        try:
            return self._ml_score(product_id, customer_id, reason_code, refund_amount)
        except Exception as exc:
            logger.warning(f"ML return classifier failed: {exc}. Using heuristic fallback.")
            return self._heuristic_score(reason_code, refund_amount)

    def _ml_score(
        self,
        product_id: int,
        customer_id: Optional[str],
        reason_code: Optional[str],
        refund_amount: float,
    ) -> Dict[str, Any]:
        """
        Dual-model inference:
          - Fraud model:  universal_fraud_detection_model.pkl + metadata
          - Return model: universal_return_prediction_model.pkl + metadata
          - Anomaly:      isolation_forest.pkl (optional)
        Feature sets match the corresponding train_*.py scripts exactly.
        """
        fraud_model_path = os.path.join(_ARTIFACTS_DIR, "universal_fraud_detection_model.pkl")
        fraud_meta_path  = os.path.join(_ARTIFACTS_DIR, "universal_fraud_detection_metadata.pkl")
        ret_model_path   = os.path.join(_ARTIFACTS_DIR, "universal_return_prediction_model.pkl")
        ret_meta_path    = os.path.join(_ARTIFACTS_DIR, "universal_return_prediction_metadata.pkl")

        if not os.path.exists(fraud_model_path) or not os.path.exists(fraud_meta_path):
            raise FileNotFoundError("Fraud detection model artifact not found.")
        if not os.path.exists(ret_model_path) or not os.path.exists(ret_meta_path):
            raise FileNotFoundError("Return prediction model artifact not found.")

        db_path = _resolve_db_path()
        if not db_path:
            raise FileNotFoundError("Database file not found at expected paths.")

        # ── Load models & metadata ────────────────────────────────────────────
        fraud_model    = joblib.load(fraud_model_path)
        fraud_meta     = joblib.load(fraud_meta_path)
        fraud_encoders = fraud_meta["encoders"]
        fraud_features = fraud_meta["features"]

        ret_model    = joblib.load(ret_model_path)
        ret_meta     = joblib.load(ret_meta_path)
        ret_encoders = ret_meta["encoders"]
        ret_features = ret_meta["features"]

        # ── Fetch context from DB ─────────────────────────────────────────────
        cust_int = int(customer_id) if customer_id and str(customer_id).isdigit() else 1
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Product details
        cursor.execute(
            "SELECT category, brand, selling_price, manufacturing_cost FROM products WHERE product_id = ?",
            (product_id,),
        )
        prod_row = cursor.fetchone()
        if prod_row:
            category, brand, selling_price, manufacturing_cost = prod_row
        else:
            category, brand, selling_price, manufacturing_cost = "Unknown", "Unknown", 0.0, 0.0

        # Customer city
        cursor.execute("SELECT city FROM customers WHERE customer_id = ?", (cust_int,))
        cust_row = cursor.fetchone()
        city = cust_row[0] if cust_row else "Unknown"

        # Last sale/shipment for this customer+product
        cursor.execute(
            """
            SELECT s.quantity, s.final_amount, sh.transportation_mode,
                   sh.shipping_cost, sh.delayed_flag, s.sale_date
            FROM sales s
            LEFT JOIN shipments sh ON s.shipment_id = sh.shipment_id
            WHERE s.product_id = ? AND s.customer_id = ?
            ORDER BY s.sale_date DESC LIMIT 1
            """,
            (product_id, cust_int),
        )
        sale_row = cursor.fetchone()
        if sale_row:
            quantity, final_amount, trans_mode, ship_cost, delayed_flag, sale_date = sale_row
            trans_mode   = trans_mode or "Road"
            ship_cost    = float(ship_cost or 0.0)
            delayed_flag = int(delayed_flag or 0)
        else:
            quantity, final_amount, trans_mode, ship_cost, delayed_flag, sale_date = (
                1, refund_amount, "Road", 0.0, 0, datetime.datetime.now().isoformat()
            )

        # Customer return history
        cursor.execute("SELECT COUNT(*) FROM returns WHERE customer_id = ?", (cust_int,))
        ret_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sales WHERE customer_id = ?", (cust_int,))
        sales_count = max(cursor.fetchone()[0], 1)
        conn.close()

        # ── Date features ─────────────────────────────────────────────────────
        try:
            sale_dt  = pd.to_datetime(sale_date)
            month    = int(sale_dt.month)
            weekday  = int(sale_dt.weekday())
            is_weekend = int(weekday in [5, 6])
        except Exception:
            now = datetime.datetime.now()
            month, weekday = now.month, now.weekday()
            is_weekend = int(weekday in [5, 6])

        # refund_without_pickup flag (matches fraud training logic)
        refund_without_pickup = 1 if (
            reason_code in ["DAMAGED", "DAMAGED_IN_TRANSIT"] and refund_amount > 10000
        ) else 0

        # ── Build shared raw values ───────────────────────────────────────────
        base = {
            "product_id":           product_id,
            "customer_id":          cust_int,
            "category":             str(category),
            "brand":                str(brand),
            "city":                 str(city),
            "selling_price":        float(selling_price),
            "quantity":             int(quantity),
            "final_amount":         float(final_amount),
            "shipping_cost":        float(ship_cost),
            "transportation_mode":  str(trans_mode),
            "delayed_flag":         int(delayed_flag),
            "refund_amount":        float(refund_amount),
            "refund_without_pickup": int(refund_without_pickup),
            "month":                int(month),
            "weekday":              int(weekday),
            "is_weekend":           int(is_weekend),
            "manufacturing_cost":   float(manufacturing_cost),
        }

        # ── FRAUD MODEL inference ─────────────────────────────────────────────
        # FEATURES (train_fraud_model.py):
        # product_id, customer_id, category, brand, city, selling_price, quantity,
        # final_amount, shipping_cost, transportation_mode, delayed_flag,
        # refund_amount, refund_without_pickup, month, weekday, is_weekend
        fraud_dict = {k: base[k] for k in fraud_features if k in base}
        for col in ["category", "brand", "city", "transportation_mode"]:
            if col in fraud_encoders and col in fraud_dict:
                le = fraud_encoders[col]
                val = str(fraud_dict[col])
                fraud_dict[col] = int(le.transform([val])[0]) if val in le.classes_ else 0
        fraud_df    = pd.DataFrame([fraud_dict])[fraud_features]
        fraud_score = float(fraud_model.predict_proba(fraud_df)[0][1])

        # ── RETURN MODEL inference ────────────────────────────────────────────
        # FEATURES (train_return_model.py):
        # product_id, customer_id, category, brand, city, selling_price,
        # manufacturing_cost, quantity, final_amount, transportation_mode,
        # shipping_cost, month, weekday, is_weekend
        ret_dict = {k: base[k] for k in ret_features if k in base}
        for col in ["category", "brand", "city", "transportation_mode"]:
            if col in ret_encoders and col in ret_dict:
                le = ret_encoders[col]
                val = str(ret_dict[col])
                ret_dict[col] = int(le.transform([val])[0]) if val in le.classes_ else 0
        ret_df             = pd.DataFrame([ret_dict])[ret_features]
        return_probability = float(ret_model.predict_proba(ret_df)[0][1])

        # ── Customer return ratio ─────────────────────────────────────────────
        return_ratio = float(ret_count / sales_count)

        # ── Isolation Forest anomaly detection ───────────────────────────────
        anomaly_flag = fraud_score > 0.80
        iso_path = os.path.join(_ARTIFACTS_DIR, "isolation_forest.pkl")
        if os.path.exists(iso_path):
            try:
                iso_model = joblib.load(iso_path)
                reason_risk = {
                    "CHANGED_MIND": 0.8, "NO_REASON": 0.9, "OTHER": 0.5,
                    "DEFECTIVE": 0.2, "WRONG_ITEM": 0.1, "DAMAGED_IN_TRANSIT": 0.15,
                }
                reason_score       = reason_risk.get(reason_code or "", 0.4)
                normalized_refund  = min(refund_amount / 50000, 1.0)
                features_if        = np.array([[reason_score, normalized_refund, product_id % 100]])
                anomaly_flag       = iso_model.predict(features_if)[0] == -1
            except Exception as e:
                logger.warning(f"Isolation forest inference failed: {e}")

        return self._build_result(fraud_score, return_probability, return_ratio, anomaly_flag)

    def _heuristic_score(self, reason_code: Optional[str], refund_amount: float) -> Dict[str, Any]:
        """Rule-based fallback when ML model artifacts are unavailable."""
        fraud_score = 0.2
        if reason_code in HIGH_RISK_REASON_CODES:
            fraud_score = 0.72
        elif reason_code in MEDIUM_RISK_REASON_CODES:
            fraud_score = 0.45
        if refund_amount > 25000:
            fraud_score = min(fraud_score + 0.15, 0.95)
        anomaly_flag = fraud_score > 0.80
        return self._build_result(fraud_score, 0.18, 0.18, anomaly_flag)

    def _build_result(
        self,
        fraud_score: float,
        return_probability: float,
        return_ratio: float,
        anomaly_flag: bool,
    ) -> Dict[str, Any]:
        """Construct the standardised output payload."""
        if fraud_score >= HIGH_FRAUD_THRESHOLD:
            risk_label = "HIGH"
        elif fraud_score >= MEDIUM_FRAUD_THRESHOLD:
            risk_label = "MEDIUM"
        else:
            risk_label = "LOW"

        return {
            "fraud_score":        round(fraud_score, 4),
            "return_probability": round(return_probability, 4),
            "return_ratio":       round(return_ratio, 4),
            "risk_label":         risk_label,
            "anomaly_flag":       anomaly_flag,
        }
