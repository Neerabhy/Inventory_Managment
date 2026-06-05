"""Apply migration_v4_predictions.sql to the project SQLite database."""

from __future__ import annotations

import sqlite3
import traceback
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
MIGRATION_SQL = BACKEND_DIR / "migration_v4_predictions.sql"
DB_PATH = (
    PROJECT_ROOT
    / "inventory-database"
    / "electronics_inventory_v3.db"
)


def main() -> None:
    try:
        sql = MIGRATION_SQL.read_text(encoding="utf-8")
        with sqlite3.connect(DB_PATH) as con:
            cursor = con.cursor()
            
            # ==================================================================
            # AUTOMATED SCHEMA RESET FOR ML TABLES ONLY
            # Drops the outdated v3 prediction shells so they can rebuild cleanly.
            # ==================================================================
            print("⚙️  Cleaning up outdated ML/Prediction table shells...")
            ml_tables = [
                "return_risk_predictions",
                "sales_features",
                "sales_forecasts",
                "vendor_recommendations",
                "inventory_reorder_plans"
            ]
            
            # Temporarily drop foreign keys constraint checking to clear tables cleanly
            cursor.execute("PRAGMA foreign_keys = OFF;")
            for table in ml_tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table};")
            cursor.execute("PRAGMA foreign_keys = ON;")
            con.commit()
            print("✅ Outdated shells cleared. Ready for clean rebuild.")
            # ==================================================================

            print("Running database migrations...")
            con.executescript(sql)
            
        print("Migration successful")
    except Exception as exc:
        print("Error:", exc)
        traceback.print_exc()


if __name__ == "__main__":
    main()
