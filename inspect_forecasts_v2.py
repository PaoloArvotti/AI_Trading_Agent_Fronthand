import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def inspect_tables_v2():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check columns for indicators_contexts
        print(f"\nColumns in indicators_contexts:")
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'indicators_contexts';")
        cols = cur.fetchall()
        print([c[0] for c in cols])
        
        # Sample data from indicators_contexts
        # Assuming it has 'created_at' or similar. Let's try to find a timestamp column from the list above if I could see it.
        # But I can't see it yet. Let's just select * limit 1 to see values.
        print(f"Sample data from indicators_contexts:")
        cur.execute(f"SELECT * FROM indicators_contexts LIMIT 1;")
        row = cur.fetchone()
        print(row)

        print(f"\nSample data from forecasts_contexts:")
        cur.execute(f"SELECT * FROM forecasts_contexts ORDER BY forecast_timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        print(row)

        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_tables_v2()
