import os
import sqlite3
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

from xgboost import XGBRegressor


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
    print("DELIVERY ETA PREDICTION MODEL")
    print("====================================")

    # =====================================================
    # DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT

        shipment_id,

        source_city,
        destination_city,

        transportation_mode,
        logistics_provider,

        distance_km,

        expected_delivery_days,
        actual_delivery_days,

        weather_delay_flag,
        remote_area_flag,

        shipping_cost

    FROM shipments

    WHERE actual_delivery_days IS NOT NULL
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
    # ENCODING
    # =====================================================

    categorical_cols = [

        "source_city",
        "destination_city",
        "transportation_mode",
        "logistics_provider"
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

        "source_city",
        "destination_city",

        "transportation_mode",
        "logistics_provider",

        "distance_km",

        "expected_delivery_days",

        "weather_delay_flag",
        "remote_area_flag",

        "shipping_cost"
    ]

    TARGET = "actual_delivery_days"

    X = df[FEATURES]

    y = df[TARGET]

    # =====================================================
    # SPLIT
    # =====================================================

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    print("\nTrain Shape:", X_train.shape)
    print("Test Shape :", X_test.shape)

    # =====================================================
    # MODEL
    # =====================================================

    model = XGBRegressor(
        n_estimators=300,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
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

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            predictions
        )
    )

    r2 = r2_score(
        y_test,
        predictions
    )

    print("\n==============================")
    print("MODEL EVALUATION")
    print("==============================")

    print(f"MAE  : {mae:.4f}")
    print(f"RMSE : {rmse:.4f}")
    print(f"R2   : {r2:.4f}")

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
        f"{MODEL_DIR}/delivery_eta_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/delivery_eta_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()