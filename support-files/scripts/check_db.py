import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "sqlite.db"

def run():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM return_history;")
    print("Return history:", c.fetchall())
    c.execute("SELECT * FROM inbound_orders;")
    print("Inbound orders:", c.fetchall())

if __name__ == "__main__":
    run()
