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
    print("UNIVERSAL DEMAND FORECAST MODEL")
    print("====================================")

    # =====================================================
    # CONNECT DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        s.sale_id,
        s.sale_date,
        s.quantity,

        p.product_id,
        p.category,
        p.brand,
        p.selling_price,
        p.manufacturing_cost,

        c.city,

        i.current_stock,
        i.safety_stock,
        i.inventory_turnover

    FROM sales s

    JOIN products p
        ON s.product_id = p.product_id

    JOIN customers c
        ON s.customer_id = c.customer_id

    LEFT JOIN inventory i
        ON p.product_id = i.product_id

    WHERE s.quantity IS NOT NULL
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    print(f"Dataset Shape: {df.shape}")

    # =====================================================
    # CLEANING
    # =====================================================

    df = df.drop_duplicates()

    # fill nulls from LEFT JOIN inventory
    df.fillna(0, inplace=True)

    print(f"After Cleaning: {df.shape}")

    # =====================================================
    # DATE FEATURES
    # =====================================================

    df["sale_date"] = pd.to_datetime(df["sale_date"])

    df["month"] = df["sale_date"].dt.month

    df["day"] = df["sale_date"].dt.day

    df["weekday"] = df["sale_date"].dt.weekday

    df["is_weekend"] = (
        df["weekday"].isin([5, 6]).astype(int)
    )

    # =====================================================
    # ENCODING
    # =====================================================

    categorical_cols = [
        "category",
        "brand",
        "city"
    ]

    encoders = {}

    for col in categorical_cols:

        le = LabelEncoder()

        df[col] = le.fit_transform(df[col].astype(str))

        encoders[col] = le

    # =====================================================
    # FEATURES
    # =====================================================

    FEATURES = [
        "product_id",
        "category",
        "brand",
        "city",
        "selling_price",
        "manufacturing_cost",
        "current_stock",
        "safety_stock",
        "inventory_turnover",
        "month",
        "day",
        "weekday",
        "is_weekend"
    ]

    TARGET = "quantity"

    X = df[FEATURES]

    y = df[TARGET].clip(lower=0)

    # =====================================================
    # SPLIT
    # =====================================================

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    # =====================================================
    # MODEL
    # =====================================================

    model = XGBRegressor(
        n_estimators=300,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="count:poisson",
        eval_metric="poisson-nloglik",
        random_state=42
    )

    print("\nTraining model...")

    model.fit(X_train, y_train)

    print("Training completed!")

    # =====================================================
    # EVALUATION
    # =====================================================

    predictions = np.clip(model.predict(X_test), 0, None)

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
    # SAVE
    # =====================================================

    joblib.dump(
        model,
        f"{MODEL_DIR}/universal_demand_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/universal_demand_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()
