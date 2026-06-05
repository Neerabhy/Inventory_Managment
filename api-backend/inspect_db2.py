import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), '..', 'inventory-database', 'electronics_inventory_v3.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Focus on the tables that were truncated
for tbl in ['products', 'inventory', 'suppliers', 'purchase_orders', 'shipments', 'sales']:
    cols = cursor.execute(f"PRAGMA table_info({tbl})").fetchall()
    count = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"\n=== {tbl} ({count} rows) ===")
    for col in cols:
        print(f"  {col[1]:35s} {col[2]:15s}")

# Check for reviews table variants
for tbl_name in ['reviews', 'product_reviews', 'customer_reviews']:
    try:
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl_name}").fetchone()[0]
        print(f"\n=== {tbl_name} ({count} rows) ===")
        cols = cursor.execute(f"PRAGMA table_info({tbl_name})").fetchall()
        for col in cols:
            print(f"  {col[1]:35s} {col[2]:15s}")
    except:
        pass

conn.close()
