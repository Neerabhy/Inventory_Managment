-- ================================================================
-- ELECTRONICS INVENTORY AI/ML — DATABASE MIGRATION SCRIPT
-- Version      : v3.0.0
-- Depends on   : v2.0.0 (migration_aiml_upgrade_v2.sql)
-- Description  : Additive schema upgrades — product-supplier
--                mapping, inventory ledger, KPI metadata,
--                procurement decision tracking, city master,
--                RBAC user management, auto business-code
--                triggers, PO status enum expansion, and indexes.
-- Engine       : SQLite 3.x
-- Strategy     : Non-destructive. Existing data fully preserved.
-- ================================================================

PRAGMA foreign_keys  = OFF;   -- Required for table rebuild in §8
PRAGMA journal_mode  = WAL;
PRAGMA synchronous   = NORMAL;

-- ================================================================
-- SECTION 1 — PRODUCT-SUPPLIER MANY-TO-MANY MAPPING
-- Enables multiple suppliers per product, AI vendor comparison,
-- procurement analytics, and vendor ranking dashboards.
-- ================================================================

CREATE TABLE IF NOT EXISTS product_suppliers (
    product_supplier_id   INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Core relationships
    product_id            INTEGER NOT NULL
                              REFERENCES products(product_id)
                              ON DELETE RESTRICT,
    supplier_id           INTEGER NOT NULL
                              REFERENCES suppliers(supplier_id)
                              ON DELETE RESTRICT,

    -- Commercial terms
    supplier_price        REAL    CHECK(supplier_price > 0),
    lead_time_days        INTEGER CHECK(lead_time_days >= 0),
    minimum_order_qty     INTEGER CHECK(minimum_order_qty > 0),

    -- Relationship metadata
    preferred_supplier_flag INTEGER NOT NULL DEFAULT 0
                                CHECK(preferred_supplier_flag IN (0,1)),
    contract_status       TEXT    NOT NULL DEFAULT 'Active'
                              CHECK(contract_status IN (
                                  'Active','Expired','Under Negotiation',
                                  'Suspended','Draft')),
    supplier_rating       REAL    CHECK(supplier_rating BETWEEN 0 AND 5),

    created_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT    DEFAULT (datetime('now')),

    -- Prevent duplicate supplier-product pairings
    UNIQUE(product_id, supplier_id)
);

-- Seed from existing purchase_orders data — derive real supplier-product
-- pairings that already exist in transactional data.
INSERT OR IGNORE INTO product_suppliers (
    product_id, supplier_id, supplier_price,
    lead_time_days, minimum_order_qty,
    preferred_supplier_flag, contract_status, supplier_rating
)
SELECT DISTINCT
    po.product_id,
    po.supplier_id,
    ROUND(po.unit_cost, 2)                         AS supplier_price,
    CAST(s.avg_lead_time_days AS INTEGER)           AS lead_time_days,
    s.minimum_order_qty,
    CASE WHEN s.reliability_score >= 0.95 THEN 1
         ELSE 0 END                                AS preferred_supplier_flag,
    'Active'                                       AS contract_status,
    ROUND(s.reliability_score * 5.0, 2)            AS supplier_rating
FROM purchase_orders po
JOIN suppliers s ON po.supplier_id = s.supplier_id;

-- ================================================================
-- SECTION 2 — INVENTORY MOVEMENT LEDGER
-- Complete stock audit trail for analytics, reconciliation,
-- and forecasting feature engineering.
-- ================================================================

CREATE TABLE IF NOT EXISTS inventory_movements (
    movement_id       INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Scope
    inventory_id      INTEGER NOT NULL
                          REFERENCES inventory(inventory_id)
                          ON DELETE RESTRICT,
    warehouse_id      INTEGER NOT NULL
                          REFERENCES warehouses(warehouse_id),
    product_id        INTEGER NOT NULL
                          REFERENCES products(product_id),

    -- Movement detail
    movement_type     TEXT    NOT NULL
                          CHECK(movement_type IN (
                              'STOCK_IN','STOCK_OUT','RETURN',
                              'TRANSFER','DAMAGE','ADJUSTMENT')),
    quantity_changed  INTEGER NOT NULL,         -- positive = in, negative = out
    stock_before      INTEGER NOT NULL CHECK(stock_before >= 0),
    stock_after       INTEGER NOT NULL CHECK(stock_after  >= 0),

    -- Source traceability
    reference_type    TEXT    CHECK(reference_type IN (
                              'SALE','RETURN','PURCHASE_ORDER',
                              'TRANSFER','MANUAL','WRITE_OFF')),
    reference_id      INTEGER,                  -- FK to source table PK
    movement_reason   TEXT,

    -- Audit
    performed_by      INTEGER,                  -- FK to users.user_id (advisory)
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ================================================================
-- SECTION 3 — KPI DEFINITIONS METADATA
-- Frontend-driven tooltip explanations for every dashboard KPI.
-- Allows UI to dynamically display formula, meaning, thresholds.
-- ================================================================

CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_code           TEXT    NOT NULL UNIQUE,   -- e.g. KPI_RETURN_RATE
    kpi_name           TEXT    NOT NULL,
    kpi_category       TEXT    NOT NULL
                           CHECK(kpi_category IN (
                               'Sales','Inventory','Logistics',
                               'Returns','Procurement','Customer',
                               'Finance','AI/ML')),
    formula            TEXT,
    description        TEXT,
    unit               TEXT    DEFAULT '%',        -- %, INR, days, count
    warning_threshold  REAL,
    critical_threshold REAL,
    higher_is_better   INTEGER DEFAULT 1 CHECK(higher_is_better IN (0,1)),
    dashboard_module   TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Seed KPI definitions for all current analytical views
INSERT OR IGNORE INTO kpi_definitions (
    kpi_code, kpi_name, kpi_category, formula,
    description, unit, warning_threshold, critical_threshold,
    higher_is_better, dashboard_module
) VALUES
    ('KPI_TOTAL_REVENUE',
     'Total Revenue', 'Sales',
     'SUM(final_amount) WHERE order_status != Cancelled',
     'Gross revenue from all delivered and shipped orders.',
     'INR', NULL, NULL, 1, 'Sales Overview'),

    ('KPI_AVG_ORDER_VALUE',
     'Average Order Value', 'Sales',
     'SUM(final_amount) / COUNT(sale_id)',
     'Mean revenue generated per order.',
     'INR', NULL, NULL, 1, 'Sales Overview'),

    ('KPI_RETURN_RATE',
     'Return Rate', 'Returns',
     'COUNT(returns) / COUNT(sales) * 100',
     'Percentage of delivered orders that were returned.',
     '%', 8.0, 15.0, 0, 'Returns Intelligence'),

    ('KPI_FRAUD_RISK_PCT',
     'Fraud Risk Customers %', 'Customer',
     'COUNT(customers WHERE fraud_score > 0.7) / COUNT(customers) * 100',
     'Percentage of customers with high fraud probability scores.',
     '%', 5.0, 10.0, 0, 'Fraud Detection'),

    ('KPI_STOCKOUT_RISK',
     'Stockout Risk SKUs', 'Inventory',
     'COUNT(inventory WHERE current_stock <= safety_stock)',
     'Number of SKUs at or below safety stock threshold.',
     'count', 5, 15, 0, 'Inventory Health'),

    ('KPI_DELAYED_SHIPMENTS',
     'Delayed Shipments', 'Logistics',
     'COUNT(shipments WHERE delayed_flag = 1)',
     'Total number of shipments that exceeded expected delivery days.',
     'count', 20, 50, 0, 'Logistics Dashboard'),

    ('KPI_SUPPLIER_OTDR',
     'On-Time Delivery Rate', 'Procurement',
     'AVG(on_time_delivery_rate) FROM suppliers',
     'Average on-time delivery rate across all active suppliers.',
     '%', 85.0, 75.0, 1, 'Supplier Intelligence'),

    ('KPI_INVENTORY_TURNOVER',
     'Inventory Turnover', 'Inventory',
     'AVG(inventory_turnover) FROM inventory',
     'Average number of times inventory is sold and replaced per period.',
     'ratio', 3.0, 1.5, 1, 'Inventory Health'),

    ('KPI_REFUND_WITHOUT_PICKUP',
     'Refund-Without-Pickup Rate', 'Returns',
     'COUNT(refund_without_pickup=1) / COUNT(returns) * 100',
     'Percentage of returns approved without physical product pickup.',
     '%', 30.0, 50.0, 0, 'Returns Intelligence'),

    ('KPI_ML_MODEL_ACCURACY',
     'ML Model Average Accuracy', 'AI/ML',
     'AVG(accuracy_score) FROM ml_models WHERE status = Active',
     'Mean accuracy score across all currently active ML models.',
     '%', 85.0, 75.0, 1, 'AI/ML Monitor'),

    ('KPI_GROSS_MARGIN',
     'Gross Margin', 'Finance',
     '(SUM(final_amount) - SUM(manufacturing_cost * quantity)) / SUM(final_amount) * 100',
     'Gross profit as a percentage of total revenue.',
     '%', 30.0, 20.0, 1, 'Finance'),

    ('KPI_CUSTOMER_SATISFACTION',
     'Avg Customer Review Rating', 'Customer',
     'AVG(rating) FROM reviews',
     'Mean product rating across all customer reviews.',
     'score', 3.5, 3.0, 1, 'Customer Analytics');

-- ================================================================
-- SECTION 4 — PROCUREMENT DECISION TRACKING
-- Records every AI procurement recommendation alongside whether
-- the procurement team accepted or overrode it and the outcome.
-- ================================================================

CREATE TABLE IF NOT EXISTS procurement_decisions (
    decision_id               INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Linked PO
    po_id                     INTEGER NOT NULL
                                  REFERENCES purchase_orders(po_id)
                                  ON DELETE RESTRICT,

    -- Supplier comparison
    recommended_supplier_id   INTEGER NOT NULL
                                  REFERENCES suppliers(supplier_id),
    selected_supplier_id      INTEGER NOT NULL
                                  REFERENCES suppliers(supplier_id),

    -- AI scoring
    ai_recommendation_score   REAL    CHECK(ai_recommendation_score BETWEEN 0 AND 1),

    -- Override tracking
    override_flag             INTEGER NOT NULL DEFAULT 0
                                  CHECK(override_flag IN (0,1)),
    override_reason           TEXT,

    -- Financial impact
    estimated_savings         REAL    DEFAULT 0,  -- INR
    actual_savings            REAL,               -- INR, updated post-delivery

    -- Workflow
    decision_taken_by         INTEGER,            -- FK to users.user_id (advisory)
    decision_date             TEXT    NOT NULL DEFAULT (datetime('now')),

    -- One decision record per PO
    UNIQUE(po_id)
);

-- ================================================================
-- SECTION 5 — SERVICEABLE CITIES MASTER TABLE
-- Single source of truth for all city references in the system.
-- Prevents inconsistent city strings across tables.
-- ================================================================

CREATE TABLE IF NOT EXISTS serviceable_cities (
    city_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name   TEXT    NOT NULL UNIQUE,
    state       TEXT    NOT NULL,
    country     TEXT    NOT NULL DEFAULT 'India',
    tier        TEXT    DEFAULT 'Tier-1'
                    CHECK(tier IN ('Tier-1','Tier-2','Tier-3')),
    is_active   INTEGER NOT NULL DEFAULT 1
                    CHECK(is_active IN (0,1)),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Seed the five supported business cities
INSERT OR IGNORE INTO serviceable_cities (city_name, state, country, tier, is_active) VALUES
    ('Delhi',     'Delhi',           'India', 'Tier-1', 1),
    ('Mumbai',    'Maharashtra',     'India', 'Tier-1', 1),
    ('Bangalore', 'Karnataka',       'India', 'Tier-1', 1),
    ('Jaipur',    'Rajasthan',       'India', 'Tier-2', 1),
    ('Kolkata',   'West Bengal',     'India', 'Tier-1', 1);

-- Advisory FK columns: add city_id to tables that hold free-text city
-- SQLite permits advisory REFERENCES in ALTER TABLE.

ALTER TABLE customers       ADD COLUMN city_id INTEGER REFERENCES serviceable_cities(city_id);
ALTER TABLE warehouses      ADD COLUMN city_id INTEGER REFERENCES serviceable_cities(city_id);
ALTER TABLE suppliers       ADD COLUMN city_id INTEGER REFERENCES serviceable_cities(city_id);

-- Back-fill city_id from city name for all existing rows
UPDATE customers  SET city_id = (SELECT city_id FROM serviceable_cities WHERE city_name = customers.city);
UPDATE warehouses SET city_id = (SELECT city_id FROM serviceable_cities WHERE city_name = warehouses.city);
UPDATE suppliers  SET city_id = (SELECT city_id FROM serviceable_cities WHERE city_name = suppliers.city);

-- ================================================================
-- SECTION 6 — ENTERPRISE USER & ROLE MANAGEMENT (RBAC)
-- Supports return approvals, procurement approvals,
-- warehouse operations, and system admin workflows.
-- ================================================================

-- 6.1  Roles master
CREATE TABLE IF NOT EXISTS roles (
    role_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role_code        TEXT    NOT NULL UNIQUE,   -- RETURN_APPROVER, PROCUREMENT_MGR…
    role_name        TEXT    NOT NULL,
    role_description TEXT,
    permissions      TEXT,                      -- JSON array of permission strings
    is_active        INTEGER NOT NULL DEFAULT 1
                         CHECK(is_active IN (0,1)),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO roles (role_code, role_name, role_description, permissions) VALUES
    ('SYS_ADMIN',
     'System Administrator',
     'Full access to all modules and configuration.',
     '["ALL"]'),

    ('PROCUREMENT_MGR',
     'Procurement Manager',
     'Manage purchase orders, suppliers, and procurement decisions.',
     '["po:read","po:write","supplier:read","supplier:write","decision:write"]'),

    ('RETURN_APPROVER',
     'Returns Approver',
     'Review, approve, or reject customer return requests.',
     '["return:read","return:approve","return:reject","customer:read"]'),

    ('WAREHOUSE_OPS',
     'Warehouse Operations',
     'Manage inventory movements, stock levels, and warehouse tasks.',
     '["inventory:read","inventory:write","movement:write","shipment:read"]'),

    ('SALES_ANALYST',
     'Sales & Analytics Analyst',
     'Read-only access to sales, forecasts, and dashboards.',
     '["sales:read","forecast:read","kpi:read","report:read"]'),

    ('FRAUD_ANALYST',
     'Fraud & Risk Analyst',
     'Investigate fraud signals and manage high-risk customer flags.',
     '["customer:read","return:read","fraud:read","fraud:write","customer:block"]'),

    ('ML_ENGINEER',
     'ML Engineer',
     'Manage model training, deployments, and monitoring.',
     '["model:read","model:write","training_log:read","training_log:write"]');

-- 6.2  Users table
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_code        TEXT    NOT NULL UNIQUE,   -- USR-2026-XXXX
    username         TEXT    NOT NULL UNIQUE,
    full_name        TEXT    NOT NULL,
    email            TEXT    NOT NULL UNIQUE,
    password_hash    TEXT    NOT NULL,          -- bcrypt / argon2 hash
    department       TEXT,
    is_active        INTEGER NOT NULL DEFAULT 1
                         CHECK(is_active IN (0,1)),
    last_login       TEXT,
    failed_attempts  INTEGER NOT NULL DEFAULT 0,
    locked_until     TEXT,                      -- ISO datetime or NULL
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    DEFAULT (datetime('now'))
);

-- Seed system users
INSERT OR IGNORE INTO users
    (user_code, username, full_name, email, password_hash, department, is_active)
VALUES
    ('USR-2026-0001', 'sys.admin',
     'System Administrator',
     'admin@electroinv.in',
     '$2b$12$placeholder_hash_admin',
     'IT', 1),

    ('USR-2026-0002', 'priya.procurement',
     'Priya Sharma',
     'priya.sharma@electroinv.in',
     '$2b$12$placeholder_hash_priya',
     'Procurement', 1),

    ('USR-2026-0003', 'rahul.returns',
     'Rahul Verma',
     'rahul.verma@electroinv.in',
     '$2b$12$placeholder_hash_rahul',
     'Customer Operations', 1),

    ('USR-2026-0004', 'ananya.warehouse',
     'Ananya Patel',
     'ananya.patel@electroinv.in',
     '$2b$12$placeholder_hash_ananya',
     'Warehouse', 1),

    ('USR-2026-0005', 'arjun.analyst',
     'Arjun Mehta',
     'arjun.mehta@electroinv.in',
     '$2b$12$placeholder_hash_arjun',
     'Analytics', 1),

    ('USR-2026-0006', 'kavya.fraud',
     'Kavya Nair',
     'kavya.nair@electroinv.in',
     '$2b$12$placeholder_hash_kavya',
     'Risk & Compliance', 1),

    ('USR-2026-0007', 'aditya.ml',
     'Aditya Kumar',
     'aditya.kumar@electroinv.in',
     '$2b$12$placeholder_hash_aditya',
     'Data Science', 1);

-- 6.3  User-Role junction (many-to-many)
CREATE TABLE IF NOT EXISTS user_roles (
    user_role_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id)  ON DELETE CASCADE,
    role_id       INTEGER NOT NULL REFERENCES roles(role_id)  ON DELETE CASCADE,
    granted_by    INTEGER          REFERENCES users(user_id),
    granted_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at    TEXT,                         -- NULL = permanent
    is_active     INTEGER NOT NULL DEFAULT 1
                      CHECK(is_active IN (0,1)),
    UNIQUE(user_id, role_id)
);

-- Assign default roles to seeded users
INSERT OR IGNORE INTO user_roles (user_id, role_id, granted_by) VALUES
    (1, (SELECT role_id FROM roles WHERE role_code='SYS_ADMIN'),        1),
    (2, (SELECT role_id FROM roles WHERE role_code='PROCUREMENT_MGR'),  1),
    (3, (SELECT role_id FROM roles WHERE role_code='RETURN_APPROVER'),  1),
    (4, (SELECT role_id FROM roles WHERE role_code='WAREHOUSE_OPS'),    1),
    (5, (SELECT role_id FROM roles WHERE role_code='SALES_ANALYST'),    1),
    (6, (SELECT role_id FROM roles WHERE role_code='FRAUD_ANALYST'),    1),
    (7, (SELECT role_id FROM roles WHERE role_code='ML_ENGINEER'),      1);

-- ================================================================
-- SECTION 7 — AUTOMATIC BUSINESS CODE TRIGGERS
-- Fires AFTER INSERT on each table to generate a professional
-- business code when none was supplied by the caller.
-- Pattern: PREFIX-YEAR-ZEROPADDED_PK
-- ================================================================

-- 7.1  products
CREATE TRIGGER IF NOT EXISTS trg_products_business_code
AFTER INSERT ON products
WHEN NEW.product_code IS NULL
BEGIN
    UPDATE products
       SET product_code = PRINTF('PRD-2026-%04d', NEW.product_id)
     WHERE product_id = NEW.product_id;
END;

-- 7.2  customers
CREATE TRIGGER IF NOT EXISTS trg_customers_business_code
AFTER INSERT ON customers
WHEN NEW.customer_code IS NULL
BEGIN
    UPDATE customers
       SET customer_code = PRINTF('CUS-2026-%04d', NEW.customer_id)
     WHERE customer_id = NEW.customer_id;
END;

-- 7.3  suppliers
CREATE TRIGGER IF NOT EXISTS trg_suppliers_business_code
AFTER INSERT ON suppliers
WHEN NEW.supplier_code IS NULL
BEGIN
    UPDATE suppliers
       SET supplier_code = PRINTF('SUP-2026-%04d', NEW.supplier_id)
     WHERE supplier_id = NEW.supplier_id;
END;

-- 7.4  warehouses
CREATE TRIGGER IF NOT EXISTS trg_warehouses_business_code
AFTER INSERT ON warehouses
WHEN NEW.warehouse_code IS NULL
BEGIN
    UPDATE warehouses
       SET warehouse_code = PRINTF('WH-2026-%04d', NEW.warehouse_id)
     WHERE warehouse_id = NEW.warehouse_id;
END;

-- 7.5  sales  (8-digit pad — high volume)
CREATE TRIGGER IF NOT EXISTS trg_sales_business_code
AFTER INSERT ON sales
WHEN NEW.order_code IS NULL
BEGIN
    UPDATE sales
       SET order_code = PRINTF('ORD-2026-%08d', NEW.sale_id)
     WHERE sale_id = NEW.sale_id;
END;

-- 7.6  shipments
CREATE TRIGGER IF NOT EXISTS trg_shipments_business_code
AFTER INSERT ON shipments
WHEN NEW.shipment_code IS NULL
BEGIN
    UPDATE shipments
       SET shipment_code = PRINTF('SHP-2026-%04d', NEW.shipment_id)
     WHERE shipment_id = NEW.shipment_id;
END;

-- 7.7  returns
CREATE TRIGGER IF NOT EXISTS trg_returns_business_code
AFTER INSERT ON returns
WHEN NEW.return_code IS NULL
BEGIN
    UPDATE returns
       SET return_code = PRINTF('RET-2026-%04d', NEW.return_id)
     WHERE return_id = NEW.return_id;
END;

-- 7.8  purchase_orders
CREATE TRIGGER IF NOT EXISTS trg_purchase_orders_business_code
AFTER INSERT ON purchase_orders
WHEN NEW.po_code IS NULL
BEGIN
    UPDATE purchase_orders
       SET po_code = PRINTF('PO-2026-%04d', NEW.po_id)
     WHERE po_id = NEW.po_id;
END;

-- 7.9  users  (auto business code on insert)
CREATE TRIGGER IF NOT EXISTS trg_users_business_code
AFTER INSERT ON users
WHEN NEW.user_code IS NULL
BEGIN
    UPDATE users
       SET user_code = PRINTF('USR-2026-%04d', NEW.user_id)
     WHERE user_id = NEW.user_id;
END;

-- ================================================================
-- SECTION 8 — PURCHASE ORDER STATUS ENUM EXPANSION
-- Current CHECK only allows: Ordered | In Transit | Delivered | Cancelled
-- Required:  Draft | Approved | Ordered | In Transit | Delivered | Cancelled
--
-- SQLite cannot ALTER a CHECK constraint. Safe approach:
--   1. Drop affected views
--   2. Rebuild purchase_orders with extended constraint
--   3. Recreate indexes and views
-- All existing data (status = 'Delivered') passes the new constraint.
-- ================================================================

-- Step 8a: Drop dependent views temporarily
DROP VIEW IF EXISTS v_supplier_scorecard;
DROP VIEW IF EXISTS v_shipment_delay_analysis;

-- Step 8b: Rebuild purchase_orders with extended status enum
CREATE TABLE IF NOT EXISTS purchase_orders_v3 (
    po_id                   INTEGER PRIMARY KEY,
    supplier_id             INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    warehouse_id            INTEGER NOT NULL REFERENCES warehouses(warehouse_id),
    shipment_id             INTEGER          REFERENCES shipments(shipment_id),
    product_id              INTEGER NOT NULL REFERENCES products(product_id),
    order_date              TEXT    NOT NULL,
    expected_delivery       TEXT,
    actual_delivery         TEXT,
    quantity                INTEGER NOT NULL CHECK(quantity > 0),
    unit_cost               REAL    NOT NULL CHECK(unit_cost > 0),
    logistics_cost          REAL    DEFAULT 0,
    landed_cost             REAL,
    -- EXPANDED STATUS ENUM: added Draft and Approved
    status                  TEXT    CHECK(status IN (
                                'Draft','Approved','Ordered',
                                'In Transit','Delivered','Cancelled')),
    ai_recommendation_score REAL    CHECK(ai_recommendation_score BETWEEN 0 AND 1),
    po_code                 TEXT    DEFAULT NULL
);

INSERT INTO purchase_orders_v3
SELECT po_id, supplier_id, warehouse_id, shipment_id, product_id,
       order_date, expected_delivery, actual_delivery,
       quantity, unit_cost, logistics_cost, landed_cost,
       status, ai_recommendation_score, po_code
FROM purchase_orders;

DROP TABLE purchase_orders;
ALTER TABLE purchase_orders_v3 RENAME TO purchase_orders;

-- Step 8c: Restore indexes on rebuilt purchase_orders
CREATE INDEX IF NOT EXISTS idx_po_supplier   ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_product    ON purchase_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_po_status     ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_po_order_date ON purchase_orders(order_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_po_code ON purchase_orders(po_code);

-- Step 8d: Restore dependent views (identical SQL, re-created safely)
CREATE VIEW IF NOT EXISTS v_supplier_scorecard AS
SELECT
    s.supplier_id,
    s.supplier_name,
    s.city,
    s.reliability_score,
    s.defect_rate,
    s.on_time_delivery_rate,
    s.avg_lead_time_days,
    s.avg_cost_index,
    COUNT(po.po_id)                          AS total_pos,
    SUM(po.quantity)                         AS total_units_ordered,
    ROUND(SUM(po.landed_cost), 2)            AS total_spend,
    ROUND(AVG(po.ai_recommendation_score),3) AS avg_ai_score,
    SUM(CASE WHEN po.status = 'Delivered'
             AND po.actual_delivery > po.expected_delivery
             THEN 1 ELSE 0 END)              AS late_deliveries,
    CASE
        WHEN s.reliability_score >= 0.95 THEN 'PREFERRED'
        WHEN s.reliability_score >= 0.85 THEN 'APPROVED'
        ELSE 'UNDER REVIEW'
    END                                      AS supplier_tier
FROM suppliers s
LEFT JOIN purchase_orders po ON s.supplier_id = po.supplier_id
GROUP BY s.supplier_id;

CREATE VIEW IF NOT EXISTS v_shipment_delay_analysis AS
SELECT
    sh.shipment_id,
    sh.logistics_provider,
    sh.source_city,
    sh.destination_city,
    sh.transportation_mode,
    sh.distance_km,
    sh.expected_delivery_days,
    sh.actual_delivery_days,
    (sh.actual_delivery_days - sh.expected_delivery_days) AS delay_days,
    sh.delayed_flag,
    sh.weather_delay_flag,
    sh.remote_area_flag,
    sh.shipment_status,
    sh.shipping_cost,
    COUNT(s.sale_id)   AS forward_orders,
    COUNT(r.return_id) AS reverse_orders
FROM shipments sh
LEFT JOIN sales           s  ON sh.shipment_id = s.shipment_id
LEFT JOIN purchase_orders po ON sh.shipment_id = po.shipment_id
LEFT JOIN returns         r  ON s.sale_id       = r.sale_id
GROUP BY sh.shipment_id;

-- ================================================================
-- SECTION 9 — INDEXES (new tables + FK columns + analytical fields)
-- ================================================================

-- product_suppliers
CREATE INDEX IF NOT EXISTS idx_ps_product
    ON product_suppliers(product_id);
CREATE INDEX IF NOT EXISTS idx_ps_supplier
    ON product_suppliers(supplier_id);
CREATE INDEX IF NOT EXISTS idx_ps_preferred
    ON product_suppliers(preferred_supplier_flag);
CREATE INDEX IF NOT EXISTS idx_ps_contract_status
    ON product_suppliers(contract_status);

-- inventory_movements
CREATE INDEX IF NOT EXISTS idx_im_inventory
    ON inventory_movements(inventory_id);
CREATE INDEX IF NOT EXISTS idx_im_product
    ON inventory_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_im_warehouse
    ON inventory_movements(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_im_movement_type
    ON inventory_movements(movement_type);
CREATE INDEX IF NOT EXISTS idx_im_reference
    ON inventory_movements(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_im_created_at
    ON inventory_movements(created_at);

-- kpi_definitions
CREATE INDEX IF NOT EXISTS idx_kd_category
    ON kpi_definitions(kpi_category);
CREATE INDEX IF NOT EXISTS idx_kd_module
    ON kpi_definitions(dashboard_module);

-- procurement_decisions
CREATE INDEX IF NOT EXISTS idx_pd_po
    ON procurement_decisions(po_id);
CREATE INDEX IF NOT EXISTS idx_pd_recommended_supplier
    ON procurement_decisions(recommended_supplier_id);
CREATE INDEX IF NOT EXISTS idx_pd_selected_supplier
    ON procurement_decisions(selected_supplier_id);
CREATE INDEX IF NOT EXISTS idx_pd_override
    ON procurement_decisions(override_flag);
CREATE INDEX IF NOT EXISTS idx_pd_date
    ON procurement_decisions(decision_date);

-- serviceable_cities
CREATE INDEX IF NOT EXISTS idx_sc_city_name
    ON serviceable_cities(city_name);
CREATE INDEX IF NOT EXISTS idx_sc_active
    ON serviceable_cities(is_active);

-- city_id FK back-fills
CREATE INDEX IF NOT EXISTS idx_customers_city_id
    ON customers(city_id);
CREATE INDEX IF NOT EXISTS idx_warehouses_city_id
    ON warehouses(city_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_city_id
    ON suppliers(city_id);

-- users
CREATE INDEX IF NOT EXISTS idx_users_username
    ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email
    ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active
    ON users(is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_code
    ON users(user_code);

-- roles
CREATE INDEX IF NOT EXISTS idx_roles_code
    ON roles(role_code);

-- user_roles
CREATE INDEX IF NOT EXISTS idx_ur_user
    ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_ur_role
    ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_ur_active
    ON user_roles(is_active);

-- ================================================================
-- SECTION 10 — NEW ANALYTICAL VIEWS
-- All new views; existing V1–V14 remain untouched.
-- ================================================================

-- V15  v_product_supplier_matrix
--      AI/procurement: all supplier options per product with scores.
CREATE VIEW IF NOT EXISTS v_product_supplier_matrix AS
SELECT
    p.product_code,
    p.product_name,
    p.category,
    p.brand,
    s.supplier_code,
    s.supplier_name,
    s.city                               AS supplier_city,
    ps.supplier_price,
    ps.lead_time_days,
    ps.minimum_order_qty,
    ps.preferred_supplier_flag,
    ps.contract_status,
    ps.supplier_rating,
    s.reliability_score,
    s.defect_rate,
    s.on_time_delivery_rate,
    s.avg_cost_index,
    -- Composite AI score: reliability 40%, quality 35%, cost 25%
    ROUND(
        s.reliability_score       * 0.40 +
        (1 - s.defect_rate)       * 0.35 +
        (1 - COALESCE(
              (ps.supplier_price - p.manufacturing_cost)
               / NULLIF(p.manufacturing_cost, 0), 0.3
             ) * 0.5)             * 0.25
    , 3)                                 AS composite_ai_score,
    CASE
        WHEN s.reliability_score >= 0.95 THEN 'PREFERRED'
        WHEN s.reliability_score >= 0.85 THEN 'APPROVED'
        ELSE 'UNDER REVIEW'
    END                                  AS supplier_tier
FROM product_suppliers ps
JOIN products  p ON ps.product_id  = p.product_id
JOIN suppliers s ON ps.supplier_id = s.supplier_id
ORDER BY p.product_id, composite_ai_score DESC;

-- V16  v_inventory_movement_summary
--      Rolling stock movement analytics per product/warehouse.
CREATE VIEW IF NOT EXISTS v_inventory_movement_summary AS
SELECT
    p.product_code,
    p.product_name,
    p.category,
    w.warehouse_code,
    w.warehouse_name,
    im.movement_type,
    COUNT(im.movement_id)               AS movement_count,
    SUM(ABS(im.quantity_changed))       AS total_units_moved,
    ROUND(AVG(ABS(im.quantity_changed)),2) AS avg_qty_per_movement,
    MAX(im.created_at)                  AS last_movement_at
FROM inventory_movements im
JOIN products   p ON im.product_id   = p.product_id
JOIN warehouses w ON im.warehouse_id = w.warehouse_id
GROUP BY p.product_id, w.warehouse_id, im.movement_type
ORDER BY p.product_id, w.warehouse_id, im.movement_type;

-- V17  v_procurement_decision_audit
--      Tracks AI recommendation acceptance rate and savings.
CREATE VIEW IF NOT EXISTS v_procurement_decision_audit AS
SELECT
    pd.decision_id,
    po.po_code,
    po.order_date,
    p.product_name,
    p.category,
    rec_s.supplier_name                  AS recommended_supplier,
    sel_s.supplier_name                  AS selected_supplier,
    pd.ai_recommendation_score,
    pd.override_flag,
    pd.override_reason,
    ROUND(pd.estimated_savings, 2)       AS estimated_savings_inr,
    ROUND(pd.actual_savings, 2)          AS actual_savings_inr,
    u.full_name                          AS decision_by,
    pd.decision_date,
    CASE
        WHEN pd.override_flag = 0 THEN 'AI ACCEPTED'
        ELSE 'AI OVERRIDDEN'
    END                                  AS decision_outcome
FROM procurement_decisions pd
JOIN purchase_orders po  ON pd.po_id                   = po.po_id
JOIN products        p   ON po.product_id               = p.product_id
JOIN suppliers       rec_s ON pd.recommended_supplier_id = rec_s.supplier_id
JOIN suppliers       sel_s ON pd.selected_supplier_id    = sel_s.supplier_id
LEFT JOIN users      u   ON pd.decision_taken_by        = u.user_id
ORDER BY pd.decision_date DESC;

-- V18  v_user_role_permissions
--      RBAC dashboard: which users hold which roles.
CREATE VIEW IF NOT EXISTS v_user_role_permissions AS
SELECT
    u.user_code,
    u.username,
    u.full_name,
    u.email,
    u.department,
    r.role_code,
    r.role_name,
    r.permissions,
    ur.granted_at,
    ur.expires_at,
    ur.is_active                         AS role_active,
    u.is_active                          AS user_active,
    CASE
        WHEN u.is_active = 0              THEN 'INACTIVE USER'
        WHEN ur.is_active = 0             THEN 'ROLE REVOKED'
        WHEN ur.expires_at IS NOT NULL
         AND ur.expires_at < datetime('now') THEN 'ROLE EXPIRED'
        ELSE 'ACTIVE'
    END                                  AS access_status
FROM user_roles ur
JOIN users u ON ur.user_id = u.user_id
JOIN roles r ON ur.role_id = r.role_id
ORDER BY u.user_id, r.role_code;

-- ================================================================
-- RE-ENABLE FOREIGN KEY ENFORCEMENT
-- ================================================================
PRAGMA foreign_keys = ON;

-- ================================================================
-- END OF MIGRATION — v3.0.0
-- ================================================================
