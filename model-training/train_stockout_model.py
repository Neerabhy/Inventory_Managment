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
    confusion_matrix
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
    print("STOCKOUT RISK PREDICTION MODEL")
    print("====================================")

    # =====================================================
    # CONNECT DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT

        i.inventory_id,

        i.product_id,

        i.current_stock,
        i.safety_stock,

        i.inventory_turnover,

        p.category,
        p.brand,
        p.selling_price,

        w.city AS warehouse_city,

        COALESCE(SUM(s.quantity), 0) AS total_sales

    FROM inventory i

    JOIN products p
        ON i.product_id = p.product_id

    JOIN warehouses w
        ON i.warehouse_id = w.warehouse_id

    LEFT JOIN sales s
        ON i.product_id = s.product_id

    GROUP BY i.inventory_id
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
    # TARGET CREATION
    # =====================================================

    # 1 = High stockout risk
    # 0 = Safe inventory

    df["stockout_risk"] = (
        df["current_stock"] <= df["safety_stock"]
    ).astype(int)

    print("\nTarget Distribution:")

    print(df["stockout_risk"].value_counts())

    # =====================================================
    # ENCODING
    # =====================================================

    categorical_cols = [
        "category",
        "brand",
        "warehouse_city"
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

        "product_id",

        "current_stock",
        "safety_stock",

        "inventory_turnover",

        "category",
        "brand",

        "selling_price",

        "warehouse_city",

        "total_sales"
    ]

    TARGET = "stockout_risk"

    X = df[FEATURES]

    y = df[TARGET]

    # =====================================================
    # TRAIN TEST SPLIT
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

    accuracy = accuracy_score(y_test, predictions)

    print("\n==============================")
    print("MODEL EVALUATION")
    print("==============================")

    print(f"Accuracy: {accuracy:.4f}")

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
        f"{MODEL_DIR}/stockout_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/stockout_model_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()