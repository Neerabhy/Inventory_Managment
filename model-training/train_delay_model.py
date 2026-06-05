import os
import sqlite3
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score
)

from xgboost import XGBClassifier


# =========================================================
# CONFIG
# =========================================================

DB_PATH = "inventory-database/electronics_inventory_v3.db"

MODEL_DIR = "ml-artifacts"

os.makedirs(MODEL_DIR, exist_ok=True)


# =========================================================
# MAIN
# =========================================================

def main():

    print("====================================")
    print("SHIPMENT DELAY PREDICTION MODEL")
    print("====================================")

    # =====================================================
    # CONNECT DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT

        shipment_id,

        logistics_provider,
        source_city,
        destination_city,

        transportation_mode,

        distance_km,

        expected_delivery_days,
        actual_delivery_days,

        delayed_flag,
        weather_delay_flag,
        remote_area_flag,

        shipping_cost,

        shipment_status

    FROM shipments

    WHERE delayed_flag IS NOT NULL
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
    # TARGET
    # =====================================================

    TARGET = "delayed_flag"

    # =====================================================
    # ENCODING
    # =====================================================

    categorical_cols = [
        "logistics_provider",
        "source_city",
        "destination_city",
        "transportation_mode",
        "shipment_status"
    ]

    encoders = {}

    for col in categorical_cols:

        le = LabelEncoder()

        df[col] = le.fit_transform(
            df[col].astype(str)
        )

        encoders[col] = le

    # =====================================================
    # FEATURES
    # =====================================================

    FEATURES = [

    "logistics_provider",

    "source_city",
    "destination_city",

    "transportation_mode",

    "distance_km",

    "expected_delivery_days",

    "weather_delay_flag",
    "remote_area_flag",

    "shipping_cost"
]

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

    # =====================================================
    # MODEL
    # =====================================================

    model = XGBClassifier(
        n_estimators=300,
        max_depth=7,
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
    # EVALUATION
    # =====================================================

    predictions = model.predict(X_test)

    probabilities = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    auc = roc_auc_score(
        y_test,
        probabilities
    )

    print("\n==============================")
    print("MODEL EVALUATION")
    print("==============================")

    print(f"Accuracy : {accuracy:.4f}")
    print(f"ROC-AUC  : {auc:.4f}")

    print("\nClassification Report:\n")

    print(classification_report(
        y_test,
        predictions
    ))

    print("\nConfusion Matrix:\n")

    print(confusion_matrix(
        y_test,
        predictions
    ))

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
        f"{MODEL_DIR}/shipment_delay_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/shipment_delay_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()