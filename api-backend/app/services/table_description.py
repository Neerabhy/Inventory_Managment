TABLE_DESCRIPTIONS = {
    # -------------------------
    # CORE BUSINESS TABLES
    # -------------------------

    "products": """
    Master table for all products/SKUs sold by the business.
    Use this table when the user asks about a product name, SKU, brand, category,
    subcategory, selling price, manufacturing cost, margin, rating, return rate,
    defect rate, or product-level performance.
    This is usually the central table for product-specific questions such as
    'Samsung Galaxy S23 Ultra', 'show iPhone stock', or 'which product has high returns'.
    """,

    "inventory": """
    Stores current stock position for each product, usually by warehouse.
    Use this table when the user asks about current stock, available stock,
    reserved stock, incoming stock, safety stock, reorder point, low inventory,
    stockout risk, or warehouse-level inventory.
    Join with products for product name/category and warehouses for location.
    """,

    "warehouses": """
    Stores warehouse/location master data.
    Use this table when the user asks about warehouse city, warehouse stock,
    inventory by location, fulfillment location, or stock distribution across cities.
    Can join with inventory and purchase_orders.
    """,

    "customers": """
    Stores customer master data such as customer profile, city, customer segment,
    fraud score, or customer risk information.
    Use this table when the user asks about customers, customer behavior,
    customer locations, repeat buyers, fraud-prone customers, or customer analytics.
    Join with sales and returns for customer transaction history.
    """,

    "sales": """
    Stores sales/order transactions.
    Use this table when the user asks about revenue, sales, sold units, order count,
    top-selling products, sales trend, demand, average order value, channel performance,
    or product/customer sales history.
    Join with products for product details, customers for buyer details,
    and shipments for delivery details.
    """,

    "returns": """
    Stores customer return/refund records.
    Use this table when the user asks about returns, refunds, return reason,
    return status, return approval, refund amount, defective products,
    fraud-related returns, or return trends.
    Join with products, sales, customers, shipments, and return_risk_predictions.
    """,

    "shipments": """
    Stores logistics and delivery records.
    Use this table when the user asks about shipment status, delivery delay,
    delayed orders, weather delay, damaged shipment, transportation mode,
    source city, destination city, delivery days, logistics provider, or shipping cost.
    Join with sales for customer orders and purchase_orders for inbound procurement shipments.
    """,

    "suppliers": """
    Stores vendor/supplier master data.
    Use this table when the user asks about suppliers, vendors, supplier reliability,
    supplier defect rate, on-time delivery rate, average lead time, supplier city,
    minimum order quantity, or supplier performance.
    Join with product_suppliers, purchase_orders, vendor_recommendations,
    and procurement_decisions.
    """,

    "purchase_orders": """
    Stores procurement purchase orders raised to suppliers.
    Use this table when the user asks about procurement orders, inbound orders,
    ordered quantity, supplier orders, PO status, expected delivery, actual delivery,
    landed cost, unit cost, logistics cost, or AI procurement score.
    Join with products, suppliers, warehouses, shipments, and procurement_decisions.
    """,

    "reviews": """
    Stores customer review and rating data for products.
    Use this table when the user asks about product reviews, ratings,
    customer feedback, sentiment, complaints, satisfaction, or how customers feel
    about a product.
    Join with products and optionally returns to correlate reviews with returns.
    """,

    # -------------------------
    # AI / ML PERSISTENCE TABLES
    # -------------------------

    "return_risk_predictions": """
    Stores ML prediction outputs for return risk.
    Use this table when the user asks about fraud score, return probability,
    return ratio, risk label, anomaly flag, high-risk returns, suspicious returns,
    or AI-scored return decisions.
    Join with returns using return_id, with products using product_id,
    and with customers using customer_id if customer details are needed.
    """,

    "sales_features": """
    Stores engineered sales and inventory features per product.
    Use this table when the user asks about recent demand, 7-day average sales,
    30-day average sales, 30-day revenue, inventory turnover, current stock,
    safety stock, product demand features, or model input features.
    This table is useful for explaining why a forecast or reorder recommendation exists.
    Join with products using product_id.
    """,

    "sales_forecasts": """
    Stores per-product daily demand forecasts.
    Use this table when the user asks about forecast, predicted demand,
    future sales, next 30 days demand, stockout in days, forecast quantity,
    confidence range, lower forecast, upper forecast, or model-used forecast output.
    Join with products using product_id and inventory when stock coverage is needed.
    """,

    "vendor_recommendations": """
    Stores AI-generated vendor recommendations for products.
    Use this table when the user asks about saved AI recommendation status,
    rank position, days stock covers, active recommendations, or recommendation labels.
    It includes composite score, adjusted score, supplier price, lead time,
    days stock covers, average daily demand, supplier risk label, rank position,
    and recommendation status. It does NOT contain reliability_score, defect_rate,
    on_time_delivery_rate, or avg_cost_index; join suppliers for those fields or use
    v_product_supplier_matrix for supplier comparison/lowest-price questions.
    """,

    "inventory_reorder_plans": """
    Stores calculated reorder plans per product and warehouse.
    Use this table when the user asks what to reorder, recommended reorder point,
    monthly demand, average daily demand, coverage days, safety buffer,
    max lead time, or warehouse-level replenishment planning.
    Join with products and warehouses.
    """,

    # -------------------------
    # PROCUREMENT / SUPPLIER INTELLIGENCE
    # -------------------------

    "product_suppliers": """
    Many-to-many mapping between products and suppliers.
    Use this table when the user asks which suppliers provide a product,
    vendor comparison for a product, supplier price, lead time,
    minimum order quantity, preferred supplier, contract status, or supplier rating.
    This table is very important for questions like
    'which vendor should I buy this product from?'.
    Join with products and suppliers.
    """,

    "procurement_decisions": """
    Stores decisions made after AI procurement recommendations.
    Use this table when the user asks whether AI recommendations were accepted,
    overridden, why a supplier was chosen, estimated savings, actual savings,
    procurement decision audit, or procurement team behavior.
    Join with purchase_orders, suppliers, products, and users.
    """,

    # -------------------------
    # INVENTORY AUDIT / MOVEMENTS
    # -------------------------

    "inventory_movements": """
    Stores stock movement audit trail.
    Use this table when the user asks about stock in, stock out, returns to inventory,
    damage adjustments, transfers, manual adjustments, inventory history,
    stock reconciliation, or why inventory changed.
    Join with products, warehouses, and inventory.
    """,

    # -------------------------
    # KPI / DASHBOARD METADATA
    # -------------------------

    "kpi_definitions": """
    Stores KPI metadata for dashboard tooltips and explanations.
    Use this table when the user asks what a KPI means, KPI formula,
    KPI threshold, warning threshold, critical threshold, unit, dashboard module,
    or whether higher value is better.
    This table explains dashboard metrics but does not store live KPI values.
    """,

    # -------------------------
    # LOCATION MASTER
    # -------------------------

    "serviceable_cities": """
    Master table for supported cities.
    Use this table when the user asks about serviceable cities, city tier,
    active cities, supported business locations, or city normalization.
    It connects with customers, suppliers, and warehouses through city_id.
    """,

    # -------------------------
    # RBAC / USER MANAGEMENT
    # -------------------------

    "users": """
    Stores application users such as procurement managers, return approvers,
    warehouse operators, analysts, fraud analysts, and ML engineers.
    Use this table only when the user asks about app users, approvers,
    decision makers, departments, user activity, or role ownership.
    Do not expose password_hash in generated SQL or final answers.
    """,

    "roles": """
    Stores role definitions and permission sets.
    Use this table when the user asks about user roles, permissions,
    access control, RBAC, return approver permissions, procurement manager permissions,
    or system access levels.
    """,

    "user_roles": """
    Junction table between users and roles.
    Use this table when the user asks which user has which role,
    active roles, expired roles, revoked roles, granted roles, or access status.
    Join with users and roles.
    """,

    # -------------------------
    # ANALYTICAL VIEWS
    # -------------------------

    "v_supplier_scorecard": """
    Analytical view summarizing supplier performance.
    Use this view when the user asks for supplier scorecard, supplier tier,
    total purchase orders, total spend, late deliveries, supplier reliability,
    supplier defect rate, or average AI recommendation score.
    Prefer this view over raw supplier and purchase order joins for supplier dashboard questions.
    """,

    "v_shipment_delay_analysis": """
    Analytical view for logistics delay analysis.
    Use this view when the user asks about delayed shipments, delay days,
    weather delays, remote area delays, shipment cost, forward orders,
    reverse orders, source city, destination city, or logistics provider performance.
    Prefer this view for logistics dashboard questions.
    """,

    "v_product_supplier_matrix": """
    Analytical view showing all supplier options per product with supplier price,
    lead time, MOQ, contract status, supplier rating, reliability, defect rate,
    on-time delivery rate, cost index, composite AI score, and supplier tier.
    Prefer this view when the user asks for vendor comparison, best vendor,
    supplier ranking, lowest price, cheapest supplier, fastest supplier,
    preferred supplier, or suppliers/vendors for a product/category.
    """,

    "v_inventory_movement_summary": """
    Analytical view summarizing stock movements by product, warehouse, and movement type.
    Use this view when the user asks about inventory movement summary,
    total units moved, last movement, movement count, stock audit,
    or warehouse-level stock movement trends.
    """,

    "v_procurement_decision_audit": """
    Analytical view for auditing AI procurement decisions.
    Use this view when the user asks about AI accepted vs overridden decisions,
    selected supplier vs recommended supplier, override reason,
    estimated savings, actual savings, decision maker, or procurement audit history.
    """,

    "v_user_role_permissions": """
    Analytical view showing users, roles, permissions, and access status.
    Use this view when the user asks about user permissions, active roles,
    expired roles, revoked access, department-wise access, or RBAC dashboard.
    """
}

TABLE_RELATIONSHIPS = [
    # Product-centered relationships
    "inventory.product_id = products.product_id",
    "sales.product_id = products.product_id",
    "returns.product_id = products.product_id",
    "reviews.product_id = products.product_id",
    "shipments.product_id = products.product_id",
    "sales_features.product_id = products.product_id",
    "sales_forecasts.product_id = products.product_id",
    "return_risk_predictions.product_id = products.product_id",
    "vendor_recommendations.product_id = products.product_id",
    "inventory_reorder_plans.product_id = products.product_id",
    "product_suppliers.product_id = products.product_id",
    "purchase_orders.product_id = products.product_id",
    "inventory_movements.product_id = products.product_id",

    # Supplier / vendor relationships
    "product_suppliers.supplier_id = suppliers.supplier_id",
    "vendor_recommendations.supplier_id = suppliers.supplier_id",
    "purchase_orders.supplier_id = suppliers.supplier_id",
    "procurement_decisions.recommended_supplier_id = suppliers.supplier_id",
    "procurement_decisions.selected_supplier_id = suppliers.supplier_id",

    # Sales / returns / shipments
    "sales.customer_id = customers.customer_id",
    "sales.shipment_id = shipments.shipment_id",
    "returns.sale_id = sales.sale_id",
    "returns.customer_id = customers.customer_id",
    "returns.shipment_id = shipments.shipment_id",
    "return_risk_predictions.return_id = returns.return_id",

    # Warehouse / procurement / inventory
    "inventory.warehouse_id = warehouses.warehouse_id",
    "purchase_orders.warehouse_id = warehouses.warehouse_id",
    "purchase_orders.shipment_id = shipments.shipment_id",
    "inventory_reorder_plans.warehouse_id = warehouses.warehouse_id",
    "inventory_movements.inventory_id = inventory.inventory_id",
    "inventory_movements.warehouse_id = warehouses.warehouse_id",

    # Procurement decisions
    "procurement_decisions.po_id = purchase_orders.po_id",
    "procurement_decisions.decision_taken_by = users.user_id",

    # City normalization
    "customers.city_id = serviceable_cities.city_id",
    "warehouses.city_id = serviceable_cities.city_id",
    "suppliers.city_id = serviceable_cities.city_id",

    # RBAC
    "user_roles.user_id = users.user_id",
    "user_roles.role_id = roles.role_id"
]
