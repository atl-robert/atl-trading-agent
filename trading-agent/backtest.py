import os
import requests
import pandas as pd
from loguru import logger
from app.execution.router import ExecutionRouter

def fetch_binance_historical_data(symbol="BTCUSDT", interval="1h", limit=500):
    """
    Automatically fetches public historical kline/candlestick data from Binance.
    """
    logger.info(f"[BACKTEST] Fetching fresh historical data for {symbol} from Binance API...")
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Binance klines format mapping
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # Convert price and volume columns to floats
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        # Keep only necessary columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # Optionally save it locally for future runs
        os.makedirs("data", exist_ok=True)
        df.to_csv("data/historical_btc.csv", index=False)
        logger.info("[BACKTEST] Successfully saved downloaded data to data/historical_btc.csv")
        return df
    except Exception as e:
        logger.error(f"[BACKTEST ERROR] Failed to fetch data from Binance API: {e}")
        return pd.DataFrame()

def run_backtest(csv_file_path: str, symbol: str = "BTCUSDT"):
    """
    Simulates historical market execution using the intelligent ExecutionRouter.
    """
    if not os.path.exists(csv_file_path):
        logger.warning(f"[BACKTEST] CSV file not found at {csv_file_path}. Downloading sample data...")
        df = fetch_binance_historical_data(symbol=symbol)
        if df.empty:
            logger.error("[BACKTEST ERROR] Could not retrieve backtest data.")
            return
    else:
        logger.info(f"[BACKTEST] Loading historical dataset from {csv_file_path}...")
        try:
            df = pd.read_csv(csv_file_path)
        except Exception as e:
            logger.error(f"[BACKTEST ERROR] Could not load CSV file: {e}")
            return

    initial_capital = 10000.0
    capital = initial_capital
    position = 0.0
    entry_price = 0.0
    trades_taken = 0
    winning_trades = 0

    logger.info(f"[BACKTEST] Starting simulation with initial capital: ${initial_capital:,.2f}")

    min_window = 150
    for i in range(min_window, len(df)):
        window_df = df.iloc[i - min_window : i + 1].copy()
        current_row = window_df.iloc[-1]
        current_price = float(current_row['close'])

        # Let the intelligent ExecutionRouter analyze the tick
        result = ExecutionRouter.process_tick(symbol=symbol, df=window_df)
        signal = result.get("signal", "HOLD")
        pos_size = result.get("position_size", 0.0)

        # Simulate execution outcomes
        if position == 0.0 and signal in ["BUY", "SELL"] and pos_size > 0:
            position = pos_size if signal == "BUY" else -pos_size
            entry_price = current_price
            trades_taken += 1
            logger.info(f"[BACKTEST TRADE] Opened {signal} at ${entry_price:,.2f} | Size: {abs(position):.4f}")

        elif position != 0.0:
            should_exit = False
            if position > 0 and signal == "SELL":
                should_exit = True
            elif position < 0 and signal == "BUY":
                should_exit = True

            if should_exit:
                pnl = (current_price - entry_price) * position if position > 0 else (entry_price - current_price) * abs(position)
                capital += pnl
                if pnl > 0:
                    winning_trades += 1
                
                logger.info(f"[BACKTEST TRADE] Closed position at ${current_price:,.2f} | PnL: ${pnl:,.2f} | New Capital: ${capital:,.2f}")
                position = 0.0
                entry_price = 0.0

    # Final performance summary
    total_return_pct = ((capital - initial_capital) / initial_capital) * 100
    win_rate = (winning_trades / trades_taken * 100) if trades_taken > 0 else 0.0

    print("\n" + "="*40)
    print("📈 INTELLIGENT BACKTEST PERFORMANCE REPORT")
    print("="*40)
    print(f"• Initial Capital : ${initial_capital:,.2f}")
    print(f"• Final Capital   : ${capital:,.2f}")
    print(f"• Total Return    : {total_return_pct:.2f}%")
    print(f"• Total Trades    : {trades_taken}")
    print(f"• Win Rate        : {win_rate:.2f}%")
    print("="*40 + "\n")

if __name__ == "__main__":
    run_backtest("data/historical_btc.csv", symbol="BTCUSDT")