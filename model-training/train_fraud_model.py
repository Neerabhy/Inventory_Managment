import os
import sqlite3
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
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
    print("UNIVERSAL FRAUD DETECTION MODEL")
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
        s.final_amount,

        p.product_id,
        p.category,
        p.brand,
        p.selling_price,

        c.customer_id,
        c.city,

        sh.transportation_mode,
        sh.shipping_cost,
        sh.delayed_flag,

        r.return_id,
        r.refund_amount,
        r.refund_without_pickup

    FROM sales s

    JOIN products p
        ON s.product_id = p.product_id

    JOIN customers c
        ON s.customer_id = c.customer_id

    LEFT JOIN shipments sh
        ON s.shipment_id = sh.shipment_id

    LEFT JOIN returns r
        ON s.sale_id = r.sale_id
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    print(f"Dataset Shape: {df.shape}")

    # =====================================================
    # CLEANING
    # =====================================================

    df.drop_duplicates(inplace=True)

    df.fillna(0, inplace=True)

    print(f"After Cleaning: {df.shape}")

    # =====================================================
    # DATE FEATURES
    # =====================================================

    df["sale_date"] = pd.to_datetime(df["sale_date"])

    df["month"] = df["sale_date"].dt.month

    df["weekday"] = df["sale_date"].dt.weekday

    df["is_weekend"] = (
        df["weekday"].isin([5, 6]).astype(int)
    )

    # =====================================================
    # CREATE FRAUD LABEL
    # =====================================================

    # Business logic fraud generation

    df["fraud_label"] = 0

    df.loc[
        (
            (df["refund_without_pickup"] == 1)
            &
            (df["refund_amount"] > 10000)
        ),
        "fraud_label"
    ] = 1

    df.loc[
        (
            (df["quantity"] >= 3)
            &
            (df["return_id"] != 0)
            &
            (df["final_amount"] > 50000)
        ),
        "fraud_label"
    ] = 1

    df.loc[
        (
            (df["delayed_flag"] == 1)
            &
            (df["refund_without_pickup"] == 1)
        ),
        "fraud_label"
    ] = 1

    print("\nFraud Distribution:")
    print(df["fraud_label"].value_counts())

    # =====================================================
    # ENCODING
    # =====================================================

    categorical_cols = [
        "category",
        "brand",
        "city",
        "transportation_mode"
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
        "customer_id",
        "category",
        "brand",
        "city",
        "selling_price",
        "quantity",
        "final_amount",
        "shipping_cost",
        "transportation_mode",
        "delayed_flag",
        "refund_amount",
        "refund_without_pickup",
        "month",
        "weekday",
        "is_weekend"
    ]

    TARGET = "fraud_label"

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
        n_estimators=400,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        scale_pos_weight=5,
        random_state=42
    )

    print("\nTraining model...")

    model.fit(X_train, y_train)

    print("Training completed!")

    # =====================================================
    # EVALUATION
    # =====================================================

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    precision = precision_score(y_test, predictions)

    recall = recall_score(y_test, predictions)

    f1 = f1_score(y_test, predictions)

    print("\n==============================")
    print("MODEL EVALUATION")
    print("==============================")

    print(f"Accuracy  : {accuracy:.4f}")
    print(f"Precision : {precision:.4f}")
    print(f"Recall    : {recall:.4f}")
    print(f"F1 Score  : {f1:.4f}")

    print("\nConfusion Matrix:\n")

    print(confusion_matrix(y_test, predictions))

    print("\nClassification Report:\n")

    print(classification_report(y_test, predictions))

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
        f"{MODEL_DIR}/universal_fraud_detection_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/universal_fraud_detection_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()