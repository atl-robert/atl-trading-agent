import os
import time
import logging
import sqlite3
import requests
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timezone

from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Credentials & Telemetry Endpoints ---
API_KEY = "PKTD6P7JQMZEGQSYTWGKJI6JKD"
SECRET_KEY = "B8Lo3bo2XjJ3ZigmgVQu3tWiasi5fdo9eTzat947MjhP"
TELEGRAM_TOKEN = "883215756:AAHM4oBhil3Xart5pJ0FpODT5pzITg3pQ"
TELEGRAM_CHAT_ID = "1995234129"

# --- Watchlist & Risk Parameters ---
WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA", "META"]
MAX_CAPITAL_ALLOCATION_PCT = 0.05  # Max 5% of account balance per position
STOP_LOSS_PCT = 0.015              # 1.5% Stop-Loss buffer
TAKE_PROFIT_PCT = 0.03             # 3.0% Take-Profit target
MODEL_PATH = "incremental_trading_model.joblib"

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
stock_data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

def send_telegram_alert(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Telegram telemetry error: {e}")

def send_daily_performance_summary():
    try:
        conn = sqlite3.connect('trading_logs.db')
        cursor = conn.cursor()
        today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT symbol, action, price, status 
            FROM execution_logs 
            WHERE timestamp LIKE ? AND action IN ('BUY', 'BRACKET_ORDER_SUBMITTED')
        ''', (f"{today_str}%",))
        
        rows = cursor.fetchall()
        conn.close()
        
        total_trades = len(rows)
        if total_trades == 0:
            summary = f"📊 *Daily Trading Summary ({today_str})*\nNo new orders executed during this cycle."
        else:
            summary = f"📊 *Daily Trading Summary ({today_str})*\nTotal Orders Placed: `{total_trades}`\n\n*Recent Activity:* \n"
            for row in rows[-5:]:
                summary += f"• `{row[0]}`: {row[1]} @ ${row[2]:.2f}\n"
                
        send_telegram_alert(summary)
    except Exception as e:
        logger.error(f"Failed to generate daily summary: {e}")

def init_db():
    conn = sqlite3.connect('trading_logs.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            action TEXT,
            price REAL,
            prediction INTEGER,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_execution(symbol, action, price, prediction, status):
    try:
        conn = sqlite3.connect('trading_logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO execution_logs (timestamp, symbol, action, price, prediction, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now(timezone.utc).isoformat(), symbol, action, price, prediction, status))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database insertion failed: {e}")

def load_model():
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            pass
    return SGDClassifier(loss='log_loss', max_iter=1000, random_state=42)

def save_model(model):
    joblib.dump(model, MODEL_PATH)

def fetch_data(symbol: str) -> pd.DataFrame:
    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(1, TimeFrameUnit.Hour),
            limit=100,
            feed=DataFeed.IEX
        )
        bars = stock_data_client.get_stock_bars(request_params)
        df = bars.df
        if df.empty:
            return df
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol)
        return df
    except Exception as e:
        logger.error(f"Failed pulling data for {symbol}: {e}")
        return pd.DataFrame()

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df['SMA_9'] = df['close'].rolling(window=9).mean()
    df['SMA_21'] = df['close'].rolling(window=21).mean()
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    rolling_mean = df['close'].rolling(window=20).mean()
    rolling_std = df['close'].rolling(window=20).std()
    upper_band = rolling_mean + (rolling_std * 2)
    lower_band = rolling_mean - (rolling_std * 2)
    
    df['BB_Width'] = (upper_band - lower_band) / rolling_mean
    df['BB_Percent_B'] = (df['close'] - lower_band) / (upper_band - lower_band)

    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=14).mean()

    df['Price_Change'] = df['close'].pct_change()
    df['Volatility'] = df['close'].rolling(window=14).std()
    
    df['Target'] = (df['close'].shift(-1) > df['close']).astype(int)
    df.dropna(inplace=True)
    return df

def calculate_position_size(equity: float, price: float, volatility: float) -> int:
    capital = equity * MAX_CAPITAL_ALLOCATION_PCT
    if volatility > 0 and not np.isnan(volatility):
        capital = capital / (1.0 + float(volatility))
    shares = int(capital / price)
    return max(shares, 1)

def execute_trading_cycle():
    model = load_model()
    scaler = StandardScaler()
    
    try:
        account = trading_client.get_account()
        equity = float(account.equity)
    except Exception as e:
        logger.error(f"Portfolio equity fetch error: {e}")
        return

    logger.info("Initializing multi-asset market scan cycle...")

    for symbol in WATCHLIST:
        df = fetch_data(symbol)
        if df.empty or len(df) < 30:
            continue

        df = compute_features(df)
        features = [
            'SMA_9', 'SMA_21', 'SMA_50', 
            'RSI', 'MACD', 'MACD_Signal', 
            'BB_Width', 'BB_Percent_B', 'ATR', 
            'Price_Change', 'Volatility'
        ]
        
        X = df[features]
        y = df['Target']
        
        if len(X) < 5:
            continue

        X_scaled = scaler.fit_transform(X)
        latest_vector = X_scaled[-1].reshape(1, -1)
        current_vol = float(df['Volatility'].iloc[-1])
        current_price = float(df['close'].iloc[-1])

        if not hasattr(model, "classes_"):
            model.partial_fit(X_scaled, y, classes=np.array([0, 1]))
            save_model(model)

        prediction = model.predict(latest_vector)[0]
        actual_label = y.iloc[-1]
        
        model.partial_fit(latest_vector, np.array([actual_label]))
        save_model(model)

        action = "BUY" if prediction == 1 else "HOLD"
        log_execution(symbol, action, current_price, int(prediction), "Evaluated")

        if prediction == 1:
            shares = calculate_position_size(equity, current_price, current_vol)
            
            stop_loss_price = round(current_price * (1 - STOP_LOSS_PCT), 2)
            take_profit_price = round(current_price * (1 + TAKE_PROFIT_PCT), 2)
            
            logger.info(f"Signal BUY verified for {symbol} | Qty: {shares} | Price: ${current_price:.2f} | SL: ${stop_loss_price} | TP: ${take_profit_price}")
            
            try:
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    order_class=OrderClass.BRACKET,
                    stop_loss=StopLossRequest(stop_price=stop_loss_price),
                    take_profit=TakeProfitRequest(limit_price=take_profit_price)
                )
                order_response = trading_client.submit_order(order_data=order_request)
                alert_text = f"🚀 *BRACKET ORDER EXECUTED*\nSymbol: `{symbol}`\nShares: `{shares}`\nPrice: `${current_price:.2f}`\nSL: `${stop_loss_price}` | TP: `${take_profit_price}`"
                send_telegram_alert(alert_text)
                log_execution(symbol, "BRACKET_ORDER_SUBMITTED", current_price, 1, str(order_response.id))
            except Exception as order_err:
                logger.error(f"Bracket order submission failed for {symbol}: {order_err}")

if __name__ == "__main__":
    init_db()
    logger.info("Autonomous Trading Agent operational.")
    send_telegram_alert("🤖 *System Online*\nAdvanced Multi-Asset Agent active with Bracket Orders and %B/ATR features.")
    
    while True:
        try:
            execute_trading_cycle()
        except Exception as main_err:
            logger.error(f"Critical loop fault: {main_err}")
        
        logger.info("Sleeping for 60 seconds before next scan cycle...")
        time.sleep(60)