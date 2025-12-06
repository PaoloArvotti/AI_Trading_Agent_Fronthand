import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def inspect_tables():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cur.fetchall()
        print("Tables:", [t[0] for t in tables])
        
        # Check columns for forecasts_contexts and indicators_contexts
        for table in ['forecasts_contexts', 'indicators_contexts']:
            print(f"\nColumns in {table}:")
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}';")
            cols = cur.fetchall()
            print([c[0] for c in cols])
            
            # Sample data
            print(f"Sample data from {table}:")
            cur.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 1;")
            row = cur.fetchone()
            print(row)

        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_tables()
