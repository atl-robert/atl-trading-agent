import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta, timezone

from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

API_KEY = "PKTD6P7JQMZEGQSYTWGKJI6JKD"
SECRET_KEY = "B8Lo3bo2XjJ3ZigmgVQu3tWiasi5fdo9eTzat947MjhP"

stock_data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

def fetch_historical_data(symbol: str, days: int = 60) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    request_params = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(1, TimeFrameUnit.Hour),
        start=start,
        end=end,
        feed=DataFeed.IEX
    )

    bars = stock_data_client.get_stock_bars(request_params)
    df = bars.df

    if df.empty:
        return df

    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol)

    return df

def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
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

def calculate_performance_metrics(returns: pd.Series) -> dict:
    if returns.empty:
        return {"Sharpe Ratio": 0.0, "Max Drawdown": 0.0, "Cumulative Return": 0.0}
    
    cumulative_return = (1 + returns).prod() - 1
    mean_ret = returns.mean()
    std_ret = returns.std()
    
    sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252 * 6.5) if std_ret > 0 else 0.0
    
    rolling_max = (1 + returns).cumprod().cummax()
    drawdown = ((1 + returns).cumprod() - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    return {
        "Sharpe Ratio": round(sharpe_ratio, 4),
        "Max Drawdown": round(max_drawdown * 100, 2),
        "Cumulative Return": round(cumulative_return * 100, 2)
    }

def run_advanced_backtest(symbol: str = "AAPL"):
    print(f"[*] Fetching historical dataset for {symbol}...")
    df = fetch_historical_data(symbol, days=60)
    if df.empty:
        print("[!] No historical data returned.")
        return

    df = calculate_features(df)
    feature_cols = [
        'SMA_9', 'SMA_21', 'SMA_50', 
        'RSI', 'MACD', 'MACD_Signal', 
        'BB_Width', 'BB_Percent_B', 'ATR', 
        'Price_Change', 'Volatility'
    ]
    
    X = df[feature_cols]
    y = df['Target']
    price_changes = df['Price_Change']

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = SGDClassifier(loss='log_loss', max_iter=1000, random_state=42)
    
    correct = 0
    total = 0
    strategy_returns = []
    
    split_index = int(len(X_scaled) * 0.4)
    model.partial_fit(X_scaled[:split_index], y.iloc[:split_index], classes=np.array([0, 1]))

    for i in range(split_index, len(X_scaled)):
        x_sample = X_scaled[i].reshape(1, -1)
        true_label = y.iloc[i]
        bar_return = price_changes.iloc[i]
        
        pred = model.predict(x_sample)[0]
        
        if pred == true_label:
            correct += 1
        total += 1
        
        strat_ret = bar_return if pred == 1 else 0.0
        strategy_returns.append(strat_ret)
        
        model.partial_fit(x_sample, np.array([true_label]))

    accuracy = (correct / total) * 100 if total > 0 else 0
    metrics = calculate_performance_metrics(pd.Series(strategy_returns))

    print(f"\n=== Advanced Backtest Results: {symbol} ===")
    print(f"Total Evaluated Bars: {total}")
    print(f"Walk-Forward Accuracy: {accuracy:.2f}%")
    print(f"Cumulative Return:     {metrics['Cumulative Return']}%")
    print(f"Sharpe Ratio:          {metrics['Sharpe Ratio']}")
    print(f"Maximum Drawdown:      {metrics['Max Drawdown']}%")

if __name__ == "__main__":
    run_advanced_backtest("AAPL")