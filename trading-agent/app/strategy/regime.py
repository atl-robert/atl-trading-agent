import pandas as pd
from loguru import logger

class MarketRegimeDetector:
    @staticmethod
    def detect_regime(df: pd.DataFrame) -> str:
        """
        Detects the current market regime based on ADX-like logic, Bollinger Band width,
        and moving average alignments. Returns 'TRENDING', 'RANGING', or 'VOLATILE'.
        """
        if df is None or len(df) < 20:
            return "UNKNOWN"

        try:
            latest = df.iloc[-1]
            
            # Volatility check using Bollinger Band width
            bb_width = latest.get('bb_width', 0.02)
            rolling_vol = latest.get('rolling_volatility', 0.01)

            # Trend checks using moving averages
            sma_9 = latest.get('sma_9', 0)
            sma_21 = latest.get('sma_21', 0)
            sma_50 = latest.get('sma_50', 0)

            # High volatility condition
            if rolling_vol > 0.025 or bb_width > 0.05:
                logger.info("[REGIME DETECTOR] Market Regime: VOLATILE")
                return "VOLATILE"

            # Trending condition (MAs cleanly aligned)
            if (sma_9 > sma_21 > sma_50) or (sma_9 < sma_21 < sma_50):
                logger.info("[REGIME DETECTOR] Market Regime: TRENDING")
                return "TRENDING"

            # Default to Ranging / Mean Reverting
            logger.info("[REGIME DETECTOR] Market Regime: RANGING")
            return "RANGING"

        except Exception as e:
            logger.error(f"[REGIME DETECTOR ERROR] Failed to detect regime: {e}")
            return "UNKNOWN"