import pandas as pd
from loguru import logger

class TrendStrategy:
    @staticmethod
    def generate_signal(df: pd.DataFrame) -> str:
        """
        Generates an expert signal based on moving average crossovers, 
        RSI momentum, ADX trend strength, and Volume confirmation.
        Returns 'BUY', 'SELL', or 'HOLD'.
        """
        if df is None or len(df) < 2:
            return "HOLD"

        latest = df.iloc[-1]
        close = latest.get('close', 0)
        sma_9 = latest.get('sma_9', 0)
        sma_21 = latest.get('sma_21', 0)
        rsi = latest.get('rsi', latest.get('rsi_14', 50))
        
        # Expert Filters (ADX for strength, Volume for institutional backing)
        adx = latest.get('adx', 30)  # Defaults above threshold if missing
        volume = latest.get('volume', 0)
        volume_sma = latest.get('volume_sma', 0)
        
        strong_trend = adx > 20
        high_volume = volume > volume_sma

        # Bullish Trend condition with Expert Confluence
        if sma_9 > sma_21 and 50 < rsi < 70 and strong_trend and high_volume:
            logger.info(f"[EXPERT TREND] Signal: BUY | SMA_9: {sma_9:.4f} > SMA_21: {sma_21:.4f} | RSI: {rsi:.2f} | ADX: {adx:.2f} (Strong)")
            return "BUY"

        # Bearish Trend condition with Expert Confluence
        elif sma_9 < sma_21 and 30 < rsi < 50 and strong_trend and high_volume:
            logger.info(f"[EXPERT TREND] Signal: SELL | SMA_9: {sma_9:.4f} < SMA_21: {sma_21:.4f} | RSI: {rsi:.2f} | ADX: {adx:.2f} (Strong)")
            return "SELL"

        return "HOLD"


class MeanReversionStrategy:
    @staticmethod
    def generate_signal(df: pd.DataFrame) -> str:
        """
        Generates a signal based on Bollinger Band bounces and extreme RSI levels.
        Returns 'BUY', 'SELL', or 'HOLD'.
        """
        if df is None or len(df) < 2:
            return "HOLD"

        latest = df.iloc[-1]
        close = latest.get('close', 0)
        bb_lower = latest.get('bb_lower', 0)
        bb_upper = latest.get('bb_upper', 0)
        rsi = latest.get('rsi', latest.get('rsi_14', 50))

        # Oversold bounce condition
        if close <= bb_lower or rsi < 30:
            logger.info(f"[MEAN REVERSION] Signal: BUY (Price {close:.4f} near lower band {bb_lower:.4f} or RSI {rsi:.2f} oversold)")
            return "BUY"

        # Overbought reversal condition
        elif close >= bb_upper or rsi > 70:
            logger.info(f"[MEAN REVERSION] Signal: SELL (Price {close:.4f} near upper band {bb_upper:.4f} or RSI {rsi:.2f} overbought)")
            return "SELL"

        return "HOLD"