import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def check_forecasts():
    """
    Verifica quali forecast sono disponibili nel database.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Controlla i timeframe disponibili
        print("Timeframe disponibili:")
        cursor.execute("""
            SELECT DISTINCT timeframe, COUNT(*) as count
            FROM forecasts_contexts
            GROUP BY timeframe
            ORDER BY timeframe;
        """)
        timeframes = cursor.fetchall()
        for tf, count in timeframes:
            print(f"  - {tf}: {count} forecast")
        
        print("\nTicker disponibili:")
        cursor.execute("""
            SELECT DISTINCT ticker, COUNT(*) as count
            FROM forecasts_contexts
            GROUP BY ticker
            ORDER BY ticker;
        """)
        tickers = cursor.fetchall()
        for ticker, count in tickers:
            print(f"  - {ticker}: {count} forecast")
        
        print("\nUltimi 10 forecast:")
        cursor.execute("""
            SELECT 
                fc.id,
                fc.context_id,
                fc.ticker,
                fc.timeframe,
                fc.last_price,
                fc.prediction,
                fc.change_pct,
                ac.created_at
            FROM forecasts_contexts fc
            JOIN ai_contexts ac ON fc.context_id = ac.id
            ORDER BY fc.id DESC
            LIMIT 10;
        """)
        forecasts = cursor.fetchall()
        for f in forecasts:
            print(f"  ID: {f[0]}, Context: {f[1]}, Ticker: {f[2]}, Timeframe: {f[3]}, "
                  f"Last: ${f[4]:.2f}, Pred: ${f[5]:.2f}, Change: {f[6]:.2f}%, Time: {f[7]}")
        
        conn.close()
        
    except Exception as e:
        print(f"Errore: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_forecasts()
