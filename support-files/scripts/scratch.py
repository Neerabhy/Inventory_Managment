import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
db_path = PROJECT_ROOT / "inventory-database" / "electronics_inventory_v3.db"
c = sqlite3.connect(db_path).cursor()
c.execute("SELECT strftime('%Y-%W', sale_date), sum(quantity) FROM sales GROUP BY 1 ORDER BY 1 LIMIT 10")
print(c.fetchall())
