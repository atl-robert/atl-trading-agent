import yfinance as yf
import pandas as pd
from loguru import logger

class MarketDataFetcher:
    @staticmethod
    def fetch_ohlcv(symbol: str = "EURUSD=X", period: str = "60d", interval: str = "1h") -> pd.DataFrame:
        """
        Fetches historical OHLCV data from Yahoo Finance for the specified symbol.
        """
        logger.info(f"[DATA FETCHER] Fetching data for {symbol} (Period: {period}, Interval: {interval})...")
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.error(f"[DATA FETCHER ERROR] No data returned for symbol {symbol}.")
                return pd.DataFrame()

            # Clean and standardize column names to lowercase
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            
            # Drop any rows with NaN values
            df.dropna(inplace=True)
            
            logger.info(f"[DATA FETCHER] Successfully fetched {len(df)} candles for {symbol}.")
            return df

        except Exception as e:
            logger.error(f"[DATA FETCHER ERROR] Failed to fetch data for {symbol}: {e}")
            return pd.DataFrame()