import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def plot_forecasts():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        
        # 1. Fetch Forecasts (Prediction made at context_id N)
        # We need context_id, ticker, prediction
        query_forecasts = """
            SELECT context_id, ticker, prediction 
            FROM forecasts_contexts 
            ORDER BY context_id;
        """
        df_forecasts = pd.read_sql_query(query_forecasts, conn)
        
        # 2. Fetch Real Prices (Price at context_id N)
        # We need context_id, ticker, price
        query_prices = """
            SELECT context_id, ticker, price as real_price 
            FROM indicators_contexts 
            ORDER BY context_id;
        """
        df_prices = pd.read_sql_query(query_prices, conn)
        
        conn.close()
        
        # 3. Merge to compare Prediction(N) vs RealPrice(N+1)
        # We want to see if the prediction made at N matched the reality at N+1
        
        # Shift prices: We want RealPrice at N to be aligned with Forecast at N-1.
        # So if we have Forecast(N), we want RealPrice(N+1).
        # Let's create a 'target_context_id' in forecasts = context_id + 1
        df_forecasts['target_context_id'] = df_forecasts['context_id'] + 1
        
        # Merge forecasts with prices on (target_context_id = context_id) and ticker
        merged = pd.merge(
            df_forecasts, 
            df_prices, 
            left_on=['target_context_id', 'ticker'], 
            right_on=['context_id', 'ticker'], 
            suffixes=('_f', '_p')
        )
        
        # Now 'merged' has:
        # context_id_f (Time T)
        # prediction (Forecast made at T for T+1)
        # real_price (Price at T+1)
        
        if merged.empty:
            print("No overlapping data found to compare forecasts.")
            return

        # 4. Plot per Ticker
        tickers = merged['ticker'].unique()
        
        for ticker in tickers:
            data = merged[merged['ticker'] == ticker].sort_values('context_id_f')
            
            # Calculate Error Metrics
            mae = (data['real_price'] - data['prediction']).abs().mean()
            
            plt.figure(figsize=(14, 7))
            
            # Plot Real Price
            plt.plot(data['context_id_f'], data['real_price'], 
                     label='Real Price (T+1)', 
                     marker='o', 
                     markersize=4,
                     alpha=0.7)
            
            # Plot Forecast
            plt.plot(data['context_id_f'], data['prediction'], 
                     label='Forecast (at T)', 
                     linestyle='--', 
                     marker='x', 
                     markersize=4,
                     alpha=0.7)
            
            plt.title(f"Forecast vs Reality: {ticker} | MAE: {mae:.4f}")
            plt.xlabel("Context ID (Time Step)")
            plt.ylabel("Price ($)")
            plt.legend()
            plt.grid(True, which='both', linestyle='--', linewidth=0.5)
            
            # Interactive mode: show the plot
            print(f"Showing plot for {ticker}. Close the window to proceed to the next one.")
            plt.show()
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting Forecast Analysis...")
    plot_forecasts()
    print("Done.")
