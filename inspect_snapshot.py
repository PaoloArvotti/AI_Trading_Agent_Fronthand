import os
import psycopg2
from dotenv import load_dotenv
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def inspect_snapshots():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Get the latest snapshot
        cur.execute("SELECT id, created_at, raw_payload FROM account_snapshots ORDER BY created_at DESC LIMIT 1;")
        row = cur.fetchone()
        
        if row:
            print(f"Snapshot ID: {row[0]}")
            print(f"Created At: {row[1]}")
            print("Raw Payload Keys:", row[2].keys())
            print(json.dumps(row[2], indent=2))
        else:
            print("No snapshots found.")
            
        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_snapshots()
