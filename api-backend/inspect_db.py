import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'inventory-database', 'electronics_inventory_v3.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print("=== ALL TABLES ===")
for t in tables:
    print(f"\n--- {t[0]} ---")
    cols = cursor.execute(f"PRAGMA table_info({t[0]})").fetchall()
    for col in cols:
        print(f"  {col[1]:30s}  {col[2]:15s}  {'NOT NULL' if col[3] else 'NULLABLE'}  default={col[4]}")
    # Row count
    count = cursor.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  >>> {count} rows")

conn.close()
