import pandas as pd
import numpy as np

class TradingAgent:
    def __init__(self, short_window=10, long_window=30):
        self.short_window = short_window
        self.long_window = long_window

    def analyze_market(self, df: pd.DataFrame) -> dict:
        """
        Expects a DataFrame with a 'close' price column.
        Calculates Simple Moving Averages and outputs a signal.
        """
        if len(df) < self.long_window:
            return {"signal": "HOLD", "reason": "Insufficient data for window calculation"}

        # Calculate technical indicators using pandas/numpy
        df['SMA_Short'] = df['close'].rolling(window=self.short_window).mean()
        df['SMA_Long'] = df['close'].rolling(window=self.long_window).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Moving average crossover logic
        if prev['SMA_Short'] <= prev['SMA_Long'] and latest['SMA_Short'] > latest['SMA_Long']:
            return {"signal": "BUY", "price": float(latest['close']), "reason": "Bullish crossover detected"}
        elif prev['SMA_Short'] >= prev['SMA_Long'] and latest['SMA_Short'] < latest['SMA_Long']:
            return {"signal": "SELL", "price": float(latest['close']), "reason": "Bearish crossover detected"}
        
        return {"signal": "HOLD", "price": float(latest['close']), "reason": "No crossover"}