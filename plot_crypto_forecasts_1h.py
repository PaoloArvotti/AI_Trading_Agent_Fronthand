import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def plot_crypto_forecasts_1h():
    """
    Plotta tutti i forecast a 1 ora per le criptovalute insieme ai dati a 15 minuti.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        
        # 1. Fetch Forecasts a 1 ora per crypto
        # Il timeframe è "Prossima Ora" per i forecast a 1h
        query_forecasts = """
            SELECT 
                fc.id,
                fc.context_id,
                fc.ticker,
                fc.timeframe,
                fc.last_price,
                fc.prediction,
                fc.lower_bound,
                fc.upper_bound,
                fc.change_pct,
                fc.forecast_timestamp,
                ac.created_at as context_created_at
            FROM forecasts_contexts fc
            JOIN ai_contexts ac ON fc.context_id = ac.id
            WHERE fc.timeframe = 'Prossima Ora'
            ORDER BY fc.context_id, fc.ticker;
        """
        df_forecasts = pd.read_sql_query(query_forecasts, conn)
        
        if df_forecasts.empty:
            print("Nessun forecast a 1h trovato nel database.")
            conn.close()
            return
        
        print(f"Trovati {len(df_forecasts)} forecast a 1h")
        print(f"Ticker unici: {df_forecasts['ticker'].unique()}")
        
        # 2. Fetch dati a 15 minuti (indicators_contexts)
        # Prendiamo i dati intraday che contengono le serie a 15 minuti
        query_indicators = """
            SELECT 
                ic.context_id,
                ic.ticker,
                ic.ts,
                ic.price,
                ic.ema20_15m,
                ic.ema50_15m,
                ic.atr3_15m,
                ic.atr14_15m,
                ic.volume_15m_current,
                ic.volume_15m_average,
                ic.intraday_mid_prices,
                ic.intraday_ema20_series,
                ic.intraday_macd_series,
                ic.intraday_rsi7_series,
                ic.intraday_rsi14_series,
                ic.lt15m_macd_series,
                ic.lt15m_rsi14_series,
                ac.created_at as context_created_at
            FROM indicators_contexts ic
            JOIN ai_contexts ac ON ic.context_id = ac.id
            ORDER BY ic.context_id, ic.ticker;
        """
        df_indicators = pd.read_sql_query(query_indicators, conn)
        
        conn.close()
        
        if df_indicators.empty:
            print("Nessun dato indicatore trovato nel database.")
            return
        
        print(f"Trovati {len(df_indicators)} record di indicatori")
        
        # 3. Merge forecasts con indicators per context_id e ticker
        merged = pd.merge(
            df_forecasts,
            df_indicators,
            on=['context_id', 'ticker'],
            suffixes=('_forecast', '_indicator')
        )
        
        if merged.empty:
            print("Nessuna corrispondenza trovata tra forecast e indicatori.")
            return
        
        print(f"Trovati {len(merged)} record merged")
        
        # 4. Plot per ogni ticker
        tickers = merged['ticker'].unique()
        
        for ticker in tickers:
            ticker_data = merged[merged['ticker'] == ticker].sort_values('context_id')
            
            if ticker_data.empty:
                continue
            
            print(f"\n{'='*60}")
            print(f"Plotting {ticker} - {len(ticker_data)} forecast points")
            print(f"{'='*60}")
            
            # Crea una figura con subplot multipli
            fig, axes = plt.subplots(3, 1, figsize=(16, 12))
            fig.suptitle(f'Forecast 1h vs Dati 15min - {ticker}', fontsize=16, fontweight='bold')
            
            # Subplot 1: Prezzo + Forecast
            ax1 = axes[0]
            
            # Plot dei prezzi reali (price dal context)
            ax1.plot(ticker_data['context_id'], ticker_data['price'], 
                    label='Prezzo Reale (al context)', 
                    marker='o', markersize=5, linewidth=2, color='blue', alpha=0.7)
            
            # Plot delle predizioni
            ax1.plot(ticker_data['context_id'], ticker_data['prediction'], 
                    label='Forecast 1h', 
                    marker='x', markersize=6, linewidth=2, 
                    linestyle='--', color='red', alpha=0.7)
            
            # Plot dei bound di confidenza
            ax1.fill_between(ticker_data['context_id'], 
                            ticker_data['lower_bound'], 
                            ticker_data['upper_bound'],
                            alpha=0.2, color='red', label='Confidence Bounds')
            
            # Calcola MAE e MAPE
            valid_data = ticker_data.dropna(subset=['price', 'prediction'])
            if len(valid_data) > 0:
                mae = np.abs(valid_data['price'] - valid_data['prediction']).mean()
                mape = (np.abs(valid_data['price'] - valid_data['prediction']) / valid_data['price'] * 100).mean()
                ax1.text(0.02, 0.98, f'MAE: {mae:.4f}\nMAPE: {mape:.2f}%', 
                        transform=ax1.transAxes, fontsize=10,
                        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            ax1.set_xlabel('Context ID')
            ax1.set_ylabel('Prezzo ($)')
            ax1.set_title('Prezzo e Forecast')
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # Subplot 2: EMA 15min
            ax2 = axes[1]
            
            ax2.plot(ticker_data['context_id'], ticker_data['price'], 
                    label='Prezzo', marker='o', markersize=4, linewidth=1.5, color='blue', alpha=0.7)
            
            # Plot EMA se disponibili
            if 'ema20_15m' in ticker_data.columns:
                valid_ema20 = ticker_data.dropna(subset=['ema20_15m'])
                if len(valid_ema20) > 0:
                    ax2.plot(valid_ema20['context_id'], valid_ema20['ema20_15m'], 
                            label='EMA20 (15m)', linewidth=1.5, color='orange', alpha=0.7)
            
            if 'ema50_15m' in ticker_data.columns:
                valid_ema50 = ticker_data.dropna(subset=['ema50_15m'])
                if len(valid_ema50) > 0:
                    ax2.plot(valid_ema50['context_id'], valid_ema50['ema50_15m'], 
                            label='EMA50 (15m)', linewidth=1.5, color='green', alpha=0.7)
            
            ax2.set_xlabel('Context ID')
            ax2.set_ylabel('Prezzo ($)')
            ax2.set_title('Medie Mobili 15min')
            ax2.legend(loc='upper left')
            ax2.grid(True, alpha=0.3)
            
            # Subplot 3: Volume 15min
            ax3 = axes[2]
            
            if 'volume_15m_current' in ticker_data.columns:
                valid_vol = ticker_data.dropna(subset=['volume_15m_current'])
                if len(valid_vol) > 0:
                    ax3.bar(valid_vol['context_id'], valid_vol['volume_15m_current'], 
                           label='Volume 15m Current', color='purple', alpha=0.6)
            
            if 'volume_15m_average' in ticker_data.columns:
                valid_vol_avg = ticker_data.dropna(subset=['volume_15m_average'])
                if len(valid_vol_avg) > 0:
                    ax3.plot(valid_vol_avg['context_id'], valid_vol_avg['volume_15m_average'], 
                            label='Volume 15m Average', linewidth=2, color='red', alpha=0.7)
            
            ax3.set_xlabel('Context ID')
            ax3.set_ylabel('Volume')
            ax3.set_title('Volume 15min')
            ax3.legend(loc='upper left')
            ax3.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Salva il plot
            output_dir = "forecast_plots"
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"forecast_1h_{ticker}.png")
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"Plot salvato: {output_file}")
            
            # Mostra il plot
            plt.show()
            
            # Stampa statistiche
            print(f"\nStatistiche per {ticker}:")
            print(f"  - Numero di forecast: {len(ticker_data)}")
            print(f"  - Prezzo medio: ${ticker_data['price'].mean():.2f}")
            print(f"  - Forecast medio: ${ticker_data['prediction'].mean():.2f}")
            if len(valid_data) > 0:
                print(f"  - MAE: ${mae:.4f}")
                print(f"  - MAPE: {mape:.2f}%")
                print(f"  - Change % medio previsto: {ticker_data['change_pct'].mean():.2f}%")
        
        print(f"\n{'='*60}")
        print("Analisi completata!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"Errore: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Avvio analisi forecast 1h per crypto...")
    print("="*60)
    plot_crypto_forecasts_1h()
    print("\nDone.")
