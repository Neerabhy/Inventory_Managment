# train_procurement_recommendation_model.py


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
    print("PROCUREMENT AI RECOMMENDATION MODEL")
    print("====================================")

    # =====================================================
    # CONNECT DATABASE
    # =====================================================

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        pd.decision_id,

        po.po_id,
        po.quantity,
        po.unit_cost,
        po.logistics_cost,
        po.landed_cost,
        po.status,
        po.ai_recommendation_score,

        p.product_id,
        p.category,
        p.brand,
        p.manufacturing_cost,
        p.selling_price,

        rec.supplier_id AS recommended_supplier_id,
        rec.city AS recommended_supplier_city,
        rec.reliability_score AS recommended_reliability,
        rec.defect_rate AS recommended_defect_rate,
        rec.on_time_delivery_rate AS recommended_otd,
        rec.avg_cost_index AS recommended_cost_index,

        sel.supplier_id AS selected_supplier_id,
        sel.city AS selected_supplier_city,
        sel.reliability_score AS selected_reliability,
        sel.defect_rate AS selected_defect_rate,
        sel.on_time_delivery_rate AS selected_otd,
        sel.avg_cost_index AS selected_cost_index,

        pd.override_flag,
        pd.estimated_savings,
        pd.actual_savings

    FROM procurement_decisions pd

    JOIN purchase_orders po
        ON pd.po_id = po.po_id

    JOIN products p
        ON po.product_id = p.product_id

    JOIN suppliers rec
        ON pd.recommended_supplier_id = rec.supplier_id

    JOIN suppliers sel
        ON pd.selected_supplier_id = sel.supplier_id

    WHERE pd.override_flag IS NOT NULL
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

    # 0 = AI accepted
    # 1 = AI overridden

    TARGET = "override_flag"

    # =====================================================
    # ENCODING
    # =====================================================

    categorical_cols = [
        "category",
        "brand",
        "status",
        "recommended_supplier_city",
        "selected_supplier_city"
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
        "quantity",
        "unit_cost",
        "logistics_cost",
        "landed_cost",
        "ai_recommendation_score",

        "product_id",
        "category",
        "brand",
        "manufacturing_cost",
        "selling_price",

        "recommended_supplier_id",
        "recommended_supplier_city",
        "recommended_reliability",
        "recommended_defect_rate",
        "recommended_otd",
        "recommended_cost_index",

        "selected_supplier_id",
        "selected_supplier_city",
        "selected_reliability",
        "selected_defect_rate",
        "selected_otd",
        "selected_cost_index",

        "estimated_savings",
        "actual_savings"
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

    accuracy = accuracy_score(y_test, predictions)

    print("\n==============================")
    print("MODEL EVALUATION")
    print("==============================")

    print(f"Accuracy : {accuracy:.4f}")

    print("\nClassification Report:\n")
    print(classification_report(y_test, predictions))

    print("\nConfusion Matrix:\n")
    print(confusion_matrix(y_test, predictions))

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
        f"{MODEL_DIR}/procurement_ai_model.pkl"
    )

    joblib.dump(
        {
            "encoders": encoders,
            "features": FEATURES
        },
        f"{MODEL_DIR}/procurement_ai_metadata.pkl"
    )

    print("\nModel saved successfully!")

    print("\nDONE")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()


'''

# WHAT THIS MODEL DOES

This model learns:

* When procurement teams accept AI supplier recommendations
* When humans override AI suggestions
* Which supplier/product/order conditions cause overrides
* Supplier reliability impact
* Cost impact
* Logistics impact
* Savings impact

---

# OUTPUT

The model predicts:

* 0 → AI recommendation likely accepted
* 1 → Procurement manager likely overrides AI

---

# BUSINESS USE

You can use this for:

* AI procurement copilot
* Vendor recommendation engine
* Override prediction dashboard
* Procurement risk scoring
* Smart supplier ranking
* Procurement KPI analytics

'''
