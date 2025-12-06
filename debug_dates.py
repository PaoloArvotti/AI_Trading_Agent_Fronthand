
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def check_dates():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Get snapshots to simulate get_closed_positions logic
    cur.execute("""
        SELECT s.id, s.created_at, op.symbol, op.side
        FROM account_snapshots s
        JOIN open_positions op ON s.id = op.snapshot_id
        ORDER BY s.created_at ASC;
    """)
    rows = cur.fetchall()
    conn.close()
    
    print(f"Total rows: {len(rows)}")
    if rows:
        print(f"Sample row: {rows[0]}")
        print(f"Type of created_at: {type(rows[0][1])}")
        print(f"Value of created_at: {rows[0][1]}")

    # Simulate the split logic
    split_date = datetime(2025, 12, 5).date()
    print(f"Split date: {split_date}")
    
    # We can't easily reproduce the full closed_positions logic here without copying the code,
    # but we can check if the DB returns naive or aware datetimes.
    
    dt = rows[0][1]
    print(f"Is naive? {dt.tzinfo is None}")
    print(f"Date part: {dt.date()}")
    print(f"Comparison with split_date: {dt.date()} >= {split_date} is {dt.date() >= split_date}")

if __name__ == "__main__":
    check_dates()
