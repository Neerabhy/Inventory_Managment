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
        """Inference path using the actual universal_fraud_detection_model.pkl and database features."""
        import os
        import pickle
        import sqlite3
        import datetime
        import numpy as np
        import pandas as pd
        import joblib

        model_path = os.path.join(os.path.dirname(__file__), "artifacts", "universal_fraud_detection_model.pkl")
        meta_path = os.path.join(os.path.dirname(__file__), "artifacts", "universal_fraud_detection_metadata.pkl")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            raise FileNotFoundError("Actual universal fraud model or metadata artifact not found.")

        # Resolve database path robustly
        db_path = "electronics_inventory_v3_full/electronics_inventory_v3.db"
        if not os.path.exists(db_path):
            possible_paths = [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "electronics_inventory_v3_full", "electronics_inventory_v3.db")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "electronics_inventory_v3_full", "electronics_inventory_v3.db")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "electronics_inventory_v3_full", "electronics_inventory_v3.db")),
                "C:/Users/NeerajKumarKhandelwa/Downloads/data_clean/electronics_inventory_v3_full/electronics_inventory_v3.db"
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    db_path = p
                    break

        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at expected paths.")

        # Load model and metadata
        model = joblib.load(model_path)
        metadata = joblib.load(meta_path)
        encoders = metadata["encoders"]
        features_list = metadata["features"]

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Product details
        cursor.execute("SELECT category, brand, selling_price FROM products WHERE product_id = ?", (product_id,))
        prod_row = cursor.fetchone()
        if prod_row:
            category, brand, selling_price = prod_row
        else:
            category, brand, selling_price = "Unknown", "Unknown", 0.0

        # 2. Customer details
        cust_int = int(customer_id) if customer_id and str(customer_id).isdigit() else 1
        cursor.execute("SELECT city FROM customers WHERE customer_id = ?", (cust_int,))
        cust_row = cursor.fetchone()
        city = cust_row[0] if cust_row else "Unknown"

        # 3. Last sale & shipment details for this customer and product to populate features
        cursor.execute("""
            SELECT s.quantity, s.final_amount, sh.transportation_mode, sh.shipping_cost, sh.delayed_flag, s.sale_date
            FROM sales s
            LEFT JOIN shipments sh ON s.shipment_id = sh.shipment_id
            WHERE s.product_id = ? AND s.customer_id = ?
            ORDER BY s.sale_date DESC LIMIT 1
        """, (product_id, cust_int))
        sale_row = cursor.fetchone()
        if sale_row:
            quantity, final_amount, trans_mode, ship_cost, delayed_flag, sale_date = sale_row
            trans_mode = trans_mode or "Road"
            ship_cost = float(ship_cost or 0.0)
            delayed_flag = int(delayed_flag or 0)
        else:
            quantity, final_amount, trans_mode, ship_cost, delayed_flag, sale_date = 1, refund_amount, "Road", 0.0, 0, datetime.datetime.now().isoformat()

        # 4. Return history for the customer return ratio calculation
        cursor.execute("SELECT COUNT(*) FROM returns WHERE customer_id = ?", (cust_int,))
        ret_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sales WHERE customer_id = ?", (cust_int,))
        sales_count = max(cursor.fetchone()[0], 1)

        conn.close()

        # Parse date features
        try:
            sale_datetime = pd.to_datetime(sale_date)
            month = int(sale_datetime.month)
            weekday = int(sale_datetime.weekday())
            is_weekend = int(weekday in [5, 6])
        except Exception:
            now = datetime.datetime.now()
            month = int(now.month)
            weekday = int(now.weekday())
            is_weekend = int(weekday in [5, 6])

        # refund_without_pickup logic: flag if high refund and specific reasons
        refund_without_pickup = 1 if (reason_code in ["DAMAGED", "DAMAGED_IN_TRANSIT"] and refund_amount > 10000) else 0

        # Construct raw features dict
        data_dict = {
            "product_id": product_id,
            "customer_id": cust_int,
            "category": str(category),
            "brand": str(brand),
            "city": str(city),
            "selling_price": float(selling_price),
            "quantity": int(quantity),
            "final_amount": float(final_amount),
            "shipping_cost": float(ship_cost),
            "transportation_mode": str(trans_mode),
            "delayed_flag": int(delayed_flag),
            "refund_amount": float(refund_amount),
            "refund_without_pickup": int(refund_without_pickup),
            "month": int(month),
            "weekday": int(weekday),
            "is_weekend": int(is_weekend)
        }

        # Encode categorical columns using the metadata LabelEncoders
        for col in ["category", "brand", "city", "transportation_mode"]:
            if col in encoders:
                le = encoders[col]
                val_str = data_dict[col]
                if val_str in le.classes_:
                    data_dict[col] = int(le.transform([val_str])[0])
                else:
                    # Unseen class fallback
                    data_dict[col] = 0

        # Create DataFrame in the exact feature ordering
        df = pd.DataFrame([data_dict])[features_list]

        # Inference
        fraud_score = float(model.predict_proba(df)[0][1])
        return_ratio = float(ret_count / sales_count)

        # Isolation Forest Anomaly Heuristic or model
        # Try loading actual isolation_forest.pkl if it exists
        anomaly_flag = fraud_score > 0.80
        iso_path = os.path.join(os.path.dirname(__file__), "artifacts", "isolation_forest.pkl")
        if os.path.exists(iso_path):
            try:
                with open(iso_path, "rb") as f:
                    iso_model = pickle.load(f)
                # Fallback input for IF (using numeric reason code score, refund, product_id)
                reason_risk = {"CHANGED_MIND": 0.8, "NO_REASON": 0.9, "OTHER": 0.5,
                               "DEFECTIVE": 0.2, "WRONG_ITEM": 0.1, "DAMAGED_IN_TRANSIT": 0.15}
                reason_score = reason_risk.get(reason_code or "", 0.4)
                normalized_refund = min(refund_amount / 50000, 1.0)
                features_if = np.array([[reason_score, normalized_refund, product_id % 100]])
                anomaly_flag = iso_model.predict(features_if)[0] == -1
            except Exception as e:
                logger.warning(f"Failed to run isolation forest: {e}")

        return self._build_result(fraud_score, return_ratio, anomaly_flag)

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
