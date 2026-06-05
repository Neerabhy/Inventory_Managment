import sqlite3
import pprint
con = sqlite3.connect('c:/Users/NeerajKumarKhandelwa/Downloads/data_clean/inventory-database/electronics_inventory_v3.db')
tables = con.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
pprint.pprint(tables)
