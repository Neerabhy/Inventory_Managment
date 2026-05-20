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

DB_PATH = "electronics_inventory_v3_full/electronics_inventory_v3.db"

MODEL_DIR = "models"

os.makedirs(MODEL_DIR, exist_ok=True)


# =========================================================
# MAIN
# =========================================================

def main():

    print("====================================")
    print("DYNAMIC PRICING OPTIMIZATION MODEL")
    print("====================================")

    # =====================================================
    # DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT

        p.category,
        p.brand,

        p.manufacturing_cost,
        p.selling_price,

        i.current_stock,
        i.inventory_turnover,
        i.safety_stock,

        COALESCE(SUM(s.quantity), 0) AS total_units_sold,

        COUNT(s.sale_id) AS total_orders

    FROM products p

    LEFT JOIN inventory i
        ON p.product_id = i.product_id

    LEFT JOIN sales s
        ON p.product_id = s.product_id

    GROUP BY p.product_id
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
        "category",
        "brand"
    ]

    encoders = {}

    for col in categorical_cols:

        le = LabelEncoder()

        df[col] = le.fit_transform(df[col])

        encoders[col] = le

    # =====================================================
    # TARGET
    # =====================================================

    TARGET = "selling_price"

    # =====================================================
    # FEATURES
    # =====================================================

    FEATURES = [

        "category",
        "brand",

        "manufacturing_cost",

        "current_stock",
        "safety_stock",
        "inventory_turnover",

        "total_units_sold",
        "total_orders"
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
        shuffle=True
    )

    print("\nTrain Shape:", X_train.shape)
    print("Test Shape :", X_test.shape)

    # =====================================================
    # MODEL
    # =====================================================

    model = XGBRegressor(
        n_estimators=200,
        max_depth=4,
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

    mae = mean_absolute_error(y_test, predictions)

    rmse = np.sqrt(
        mean_squared_error(y_test, predictions)
    )

    r2 = r2_score(y_test, predictions)

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
    # SAMPLE PREDICTIONS
    # =====================================================

    sample_results = pd.DataFrame({
        "Actual Price": y_test.values[:10],
        "Predicted Price": predictions[:10]
    })

    print("\n==============================")
    print("SAMPLE PREDICTIONS")
    print("==============================")

    print(sample_results)

    # =====================================================
    # SAVE MODEL
    # =====================================================

    joblib.dump(
        model,
        f"{MODEL_DIR}/dynamic_pricing_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/dynamic_pricing_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()