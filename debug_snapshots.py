
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def check_snapshots():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT created_at, balance_usd
        FROM account_snapshots
        WHERE created_at >= '2025-12-05 00:00:00+00'
        ORDER BY created_at ASC
        LIMIT 20;
    """)
    rows = cur.fetchall()
    conn.close()
    
    print("Snapshots on 05/12:")
    for row in rows:
        print(f"Time: {row[0]}, Balance: {row[1]}")

if __name__ == "__main__":
    check_snapshots()
