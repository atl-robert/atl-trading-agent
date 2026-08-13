import pandas as pd
from loguru import logger

class DataValidator:
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, symbol: str) -> bool:
        if df is None or df.empty:
            logger.error(f"[DATA UNAVAILABLE] DataFrame for {symbol} is empty.")
            return False
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                return False
        if df[required_cols].isnull().any().any() or (df[required_cols] <= 0).any().any():
            return False
        return True
