import pandas as pd

class MovingAverageStrategy:
    def __init__(self, short_window=10, long_window=30):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, df: pd.DataFrame) -> dict:
        if len(df) < self.long_window:
            return {"signal": "HOLD", "reason": "Insufficient data"}

        df['SMA_Short'] = df['close'].rolling(window=self.short_window).mean()
        df['SMA_Long'] = df['close'].rolling(window=self.long_window).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if prev['SMA_Short'] <= prev['SMA_Long'] and latest['SMA_Short'] > latest['SMA_Long']:
            return {"signal": "BUY", "price": float(latest['close'])}
        elif prev['SMA_Short'] >= prev['SMA_Long'] and latest['SMA_Short'] < latest['SMA_Long']:
            return {"signal": "SELL", "price": float(latest['close'])}
        
        return {"signal": "HOLD", "price": float(latest['close'])}