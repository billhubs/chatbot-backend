import sqlite3

def apply_schema(db_path: str, schema_path: str):
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Drop table if exists to avoid conflicts
    cursor.execute("DROP TABLE IF EXISTS reservations")
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()
    print(f"Schema applied successfully to {db_path}")

if __name__ == "__main__":
    apply_schema('./backend/database/reservations.db', './backend/database/database_schema.sql')