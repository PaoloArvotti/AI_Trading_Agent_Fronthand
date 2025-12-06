import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def check_db_stats():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cur.fetchall()
        print("Tables:", [t[0] for t in tables])
        
        # Check row counts
        if ('account_snapshots',) in tables:
            cur.execute("SELECT COUNT(*) FROM account_snapshots;")
            print("Snapshots count:", cur.fetchone()[0])
            
        if ('open_positions',) in tables:
            cur.execute("SELECT COUNT(*) FROM open_positions;")
            print("Open Positions table count:", cur.fetchone()[0])
        else:
            print("open_positions table does NOT exist.")
            
        conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_db_stats()
