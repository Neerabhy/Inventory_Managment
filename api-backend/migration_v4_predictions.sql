-- ================================================================
-- ELECTROINVENTORY v3 — PREDICTION & FORECAST PERSISTENCE
-- Stores ML outputs; forecasts run on-demand or when tables are empty.
-- ================================================================

PRAGMA foreign_keys = ON;

-- Return risk scores (written when return is created / scored)
CREATE TABLE IF NOT EXISTS return_risk_predictions (
    prediction_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id           INTEGER NOT NULL UNIQUE
                            REFERENCES returns(return_id) ON DELETE CASCADE,
    product_id            INTEGER NOT NULL
                            REFERENCES products(product_id),
    customer_id           INTEGER,
    fraud_score           REAL,
    return_probability    REAL,
    return_ratio          REAL,
    risk_label            TEXT,
    anomaly_flag          INTEGER DEFAULT 0,
    model_version         TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Engineered sales features per product (refreshed with forecast batch)
CREATE TABLE IF NOT EXISTS sales_features (
    feature_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            INTEGER NOT NULL UNIQUE
                            REFERENCES products(product_id) ON DELETE CASCADE,
    category              TEXT,
    brand                 TEXT,
    avg_daily_sales_7d    REAL DEFAULT 0,
    avg_daily_sales_30d   REAL DEFAULT 0,
    total_qty_30d         REAL DEFAULT 0,
    total_revenue_30d     REAL DEFAULT 0,
    current_stock         INTEGER DEFAULT 0,
    safety_stock          INTEGER DEFAULT 0,
    inventory_turnover    REAL DEFAULT 0,
    selling_price         REAL,
    manufacturing_cost    REAL,
    computed_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-product daily demand forecasts (30-day horizon)
CREATE TABLE IF NOT EXISTS sales_forecasts (
    forecast_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            INTEGER NOT NULL
                            REFERENCES products(product_id) ON DELETE CASCADE,
    forecast_date         TEXT NOT NULL,
    predicted_qty         REAL NOT NULL,
    lower_qty             REAL,
    upper_qty             REAL,
    avg_daily_demand      REAL,
    stockout_in_days      INTEGER,
    model_used            TEXT,
    batch_id              TEXT NOT NULL,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, forecast_date, batch_id)
);

-- Vendor recommendations (deleted when product is ordered)
CREATE TABLE IF NOT EXISTS vendor_recommendations (
    recommendation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            INTEGER NOT NULL
                            REFERENCES products(product_id) ON DELETE CASCADE,
    supplier_id           INTEGER NOT NULL
                            REFERENCES suppliers(supplier_id),
    supplier_name         TEXT,
    composite_score       REAL,
    adjusted_score        REAL,
    supplier_price        REAL,
    lead_time_days        INTEGER,
    days_stock_covers     REAL,
    avg_daily_demand      REAL,
    recommendation        TEXT,
    supplier_risk_label   TEXT,
    rank_position         INTEGER,
    status                TEXT NOT NULL DEFAULT 'ACTIVE'
                              CHECK(status IN ('ACTIVE','CONSUMED')),
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Reorder point plans (monthly need + lead time)
CREATE TABLE IF NOT EXISTS inventory_reorder_plans (
    plan_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            INTEGER NOT NULL,
    warehouse_id          INTEGER NOT NULL,
    monthly_demand_units  REAL NOT NULL,
    avg_daily_demand      REAL NOT NULL,
    max_lead_time_days    INTEGER NOT NULL,
    recommended_reorder_point INTEGER NOT NULL,
    safety_buffer_days    INTEGER DEFAULT 7,
    coverage_days         INTEGER,
    computed_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, warehouse_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_forecasts_product ON sales_forecasts(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_forecasts_batch ON sales_forecasts(batch_id);
CREATE INDEX IF NOT EXISTS idx_vendor_rec_product ON vendor_recommendations(product_id, status);
CREATE INDEX IF NOT EXISTS idx_return_risk_return ON return_risk_predictions(return_id);
