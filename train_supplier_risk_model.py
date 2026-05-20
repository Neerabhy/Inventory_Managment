import os
import sqlite3
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score
)

from xgboost import XGBClassifier


# =========================================================
# CONFIG
# =========================================================

DB_PATH = "electronics_inventory_v3_full/electronics_inventory_v3.db"

MODEL_DIR = "models"

os.makedirs(MODEL_DIR, exist_ok=True)


# =========================================================
# MAIN
# =========================================================

def main():

    print("====================================")
    print("SUPPLIER RISK PREDICTION MODEL")
    print("====================================")

    # =====================================================
    # DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT

        s.supplier_id,
        s.supplier_name,
        s.city,

        s.reliability_score,
        s.defect_rate,
        s.on_time_delivery_rate,
        s.avg_lead_time_days,
        s.avg_cost_index,
        s.minimum_order_qty,

        COUNT(po.po_id) AS total_purchase_orders,

        COALESCE(SUM(po.quantity), 0) AS total_units_ordered,

        COALESCE(AVG(po.unit_cost), 0) AS avg_unit_cost,

        SUM(
            CASE
                WHEN po.status = 'Cancelled'
                THEN 1
                ELSE 0
            END
        ) AS cancelled_orders,

        SUM(
            CASE
                WHEN po.actual_delivery > po.expected_delivery
                THEN 1
                ELSE 0
            END
        ) AS delayed_orders

    FROM suppliers s

    LEFT JOIN purchase_orders po
        ON s.supplier_id = po.supplier_id

    GROUP BY s.supplier_id
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    print(f"Dataset Shape: {df.shape}")

    # =====================================================
    # CLEANING
    # =====================================================

    df = df.dropna()

    df = df.drop_duplicates()

    print(f"After Cleaning: {df.shape}")

    # =====================================================
    # CREATE TARGET
    # HIGH RISK SUPPLIER
    # =====================================================

    df["supplier_risk"] = np.where(

        (
            (df["reliability_score"] < 0.80)
            |
            (df["defect_rate"] > 0.08)
            |
            (df["on_time_delivery_rate"] < 0.80)
            |
            (df["delayed_orders"] > 5)
        ),

        1,
        0
    )

    print("\nTarget Distribution:")
    print(df["supplier_risk"].value_counts())

    # =====================================================
    # ENCODING
    # =====================================================

    categorical_cols = [
        "city"
    ]

    encoders = {}

    for col in categorical_cols:

        le = LabelEncoder()

        df[col] = le.fit_transform(df[col])

        encoders[col] = le

    # =====================================================
    # FEATURES
    # =====================================================

    FEATURES = [

        "city",

        "reliability_score",
        "defect_rate",
        "on_time_delivery_rate",
        "avg_lead_time_days",
        "avg_cost_index",
        "minimum_order_qty",

        "total_purchase_orders",
        "total_units_ordered",
        "avg_unit_cost",

        "cancelled_orders",
        "delayed_orders"
    ]

    TARGET = "supplier_risk"

    X = df[FEATURES]

    y = df[TARGET]

    # =====================================================
    # SPLIT
    # =====================================================

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    print("\nTrain Shape:", X_train.shape)
    print("Test Shape :", X_test.shape)

    # =====================================================
    # MODEL
    # =====================================================

    model = XGBClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42
    )

    print("\nTraining model...")

    model.fit(X_train, y_train)

    print("Training completed!")

    # =====================================================
    # PREDICTIONS
    # =====================================================

    predictions = model.predict(X_test)

    # =====================================================
    # EVALUATION
    # =====================================================

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    print("\n==============================")
    print("MODEL EVALUATION")
    print("==============================")

    print(f"\nAccuracy: {accuracy:.4f}")

    print("\nClassification Report:\n")

    print(
        classification_report(
            y_test,
            predictions
        )
    )

    print("\nConfusion Matrix:\n")

    print(
        confusion_matrix(
            y_test,
            predictions
        )
    )

    # =====================================================
    # FEATURE IMPORTANCE
    # =====================================================

    importance_df = pd.DataFrame({
        "feature": FEATURES,
        "importance": model.feature_importances_
    })

    importance_df = importance_df.sort_values(
        by="importance",
        ascending=False
    )

    print("\n==============================")
    print("FEATURE IMPORTANCE")
    print("==============================")

    print(importance_df)

    # =====================================================
    # SAVE MODEL
    # =====================================================

    joblib.dump(
        model,
        f"{MODEL_DIR}/supplier_risk_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/supplier_risk_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()