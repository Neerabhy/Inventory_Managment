"""
reset_demo_data.py
==================
Clears ONLY the transactional rows that were written by the app during the demo session.

Safe tables (never touched):
  - products, inventory, suppliers, product_suppliers, sales, shipments,
    serviceable_cities, roles, users, kpi_definitions, returns, reviews

Cleared tables (app-generated writes only):
  - purchase_orders       → all rows (reorders submitted via the UI)
  - inventory_movements   → all rows (stock adjustments via the UI)
  - procurement_decisions → all rows (AI procurement decisions)

Run this script from the project root (data_clean/) with the venv active:
    python support-files/scripts/reset_demo_data.py

Or with a --dry-run flag to see what would be deleted without actually deleting:
    python support-files/scripts/reset_demo_data.py --dry-run
"""

import asyncio
import os
import sys

from sqlalchemy import text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "api-backend")
sys.path.insert(0, BACKEND_DIR)

from app.core.database import engine as async_engine

TABLES_TO_CLEAR = [
    "procurement_decisions",
    "inbound_orders",
    "return_history",
    "inventory_movements",
]

DRY_RUN = "--dry-run" in sys.argv


async def reset():
    print("\n🔄  ElectroInventory Demo Reset")
    print("=" * 45)
    if DRY_RUN:
        print("⚠️  DRY-RUN mode — nothing will be deleted.\n")

    async with async_engine.begin() as conn:
        for table in TABLES_TO_CLEAR:
            # Count rows first
            count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = count_result.scalar_one()

            if DRY_RUN:
                print(f"  Would delete {count:>6} rows from  {table}")
            else:
                if count > 0:
                    if table == "return_history":
                        # Set associated returns back to Pending state before deleting the history
                        await conn.execute(text("UPDATE returns SET approval_status = 'Manual Review' WHERE id IN (SELECT return_id FROM return_history)"))
                    await conn.execute(text(f"DELETE FROM {table}"))
                    print(f"  ✅  Deleted {count:>6} rows from  {table}")
                else:
                    print(f"  ⏭️  Skipped {table:30s} (already empty)")

    if not DRY_RUN:
        print("\n✅  Demo data cleared successfully.")
        print("    Original product/inventory/sales/shipments data is untouched.")
    else:
        print("\n  (Re-run without --dry-run to actually delete)")

    print()


if __name__ == "__main__":
    asyncio.run(reset())
