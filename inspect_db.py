import os
import psycopg2
from dotenv import load_dotenv
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def inspect():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check distinct operations
        cur.execute("SELECT DISTINCT operation FROM bot_operations;")
        ops = cur.fetchall()
        print("Operations found:", ops)
        
        # Check a sample close operation if exists
        cur.execute("SELECT * FROM bot_operations WHERE operation LIKE '%close%' LIMIT 1;")
        row = cur.fetchone()
        if row:
            print("\nSample Close Operation:")
            # row description: id, created_at, context_id, operation, symbol, direction, target.., lev, raw_payload
            print(f"Operation: {row[3]}")
            print(f"Payload: {json.dumps(row[8], indent=2)}")
        else:
            print("\nNo 'close' operations found.")
            
        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect()
