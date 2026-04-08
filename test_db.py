import sqlite3

db = sqlite3.connect('backend/warehouse_v2.db')
cursor = db.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='barcodes'")
row = cursor.fetchone()

if row:
    print(row[0])
    
    # Check UNIQUE indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='barcodes' AND sql LIKE '%UNIQUE%'")
    for idx_row in cursor.fetchall():
        print("UNIQUE INDEX:", idx_row[0])
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE name='{idx_row[0]}'")
        print(cursor.fetchone()[0])
else:
    print("Table not found")
