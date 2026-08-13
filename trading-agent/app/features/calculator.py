import numpy as np
import pandas as pd
from loguru import logger


class FeatureCalculator:
    """
    Robust technical-feature engine for the trading agent.

    Produces:
    - SMA / EMA
    - RSI
    - ATR
    - ADX / +DI / -DI
    - MACD
    - Bollinger Bands
    - Volatility
    - Volume statistics
    """

    @staticmethod
    def compute_features(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            logger.error("[FEATURE ENGINEERING] Empty DataFrame received.")
            return pd.DataFrame()

        required = ["open", "high", "low", "close", "volume"]

        missing = [col for col in required if col not in df.columns]
        if missing:
            logger.error(
                f"[FEATURE ENGINEERING] Missing required columns: {missing}"
            )
            return pd.DataFrame()

        # Never mutate the caller's DataFrame.
        data = df.copy()

        # Ensure numeric OHLCV data.
        for col in required:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        data.replace([np.inf, -np.inf], np.nan, inplace=True)

        # Remove invalid raw candles first.
        data.dropna(subset=required, inplace=True)

        if len(data) < 60:
            logger.warning(
                f"[FEATURE ENGINEERING] Only {len(data)} valid candles available. "
                "At least 60 are recommended."
            )

        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]

        try:
            # ==========================================================
            # 1. MOVING AVERAGES
            # ==========================================================

            data["sma_9"] = close.rolling(9).mean()
            data["sma_21"] = close.rolling(21).mean()
            data["sma_50"] = close.rolling(50).mean()

            data["ema_9"] = close.ewm(span=9, adjust=False).mean()
            data["ema_21"] = close.ewm(span=21, adjust=False).mean()

            # ==========================================================
            # 2. RSI
            # ==========================================================

            delta = close.diff()

            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)

            avg_gain = gain.ewm(
                alpha=1 / 14,
                min_periods=14,
                adjust=False
            ).mean()

            avg_loss = loss.ewm(
                alpha=1 / 14,
                min_periods=14,
                adjust=False
            ).mean()

            rs = avg_gain / avg_loss.replace(0, np.nan)

            data["rsi"] = 100 - (100 / (1 + rs))
            data["rsi_14"] = data["rsi"]

            # ==========================================================
            # 3. TRUE RANGE / ATR
            # ==========================================================

            previous_close = close.shift(1)

            tr1 = high - low
            tr2 = (high - previous_close).abs()
            tr3 = (low - previous_close).abs()

            true_range = pd.concat(
                [tr1, tr2, tr3],
                axis=1
            ).max(axis=1)

            data["true_range"] = true_range

            data["atr_14"] = true_range.ewm(
                alpha=1 / 14,
                min_periods=14,
                adjust=False
            ).mean()

            # ==========================================================
            # 4. ADX / DIRECTIONAL MOVEMENT
            # ==========================================================

            up_move = high.diff()
            down_move = -low.diff()

            plus_dm = pd.Series(
                np.where(
                    (up_move > down_move) & (up_move > 0),
                    up_move,
                    0.0
                ),
                index=data.index
            )

            minus_dm = pd.Series(
                np.where(
                    (down_move > up_move) & (down_move > 0),
                    down_move,
                    0.0
                ),
                index=data.index
            )

            atr = data["atr_14"]

            data["plus_di"] = (
                100 * plus_dm.ewm(
                    alpha=1 / 14,
                    min_periods=14,
                    adjust=False
                ).mean() / atr.replace(0, np.nan)
            )

            data["minus_di"] = (
                100 * minus_dm.ewm(
                    alpha=1 / 14,
                    min_periods=14,
                    adjust=False
                ).mean() / atr.replace(0, np.nan)
            )

            di_sum = data["plus_di"] + data["minus_di"]

            data["dx"] = (
                100
                * (data["plus_di"] - data["minus_di"]).abs()
                / di_sum.replace(0, np.nan)
            )

            data["adx"] = data["dx"].ewm(
                alpha=1 / 14,
                min_periods=14,
                adjust=False
            ).mean()

            # ==========================================================
            # 5. MACD
            # ==========================================================

            ema_12 = close.ewm(
                span=12,
                adjust=False
            ).mean()

            ema_26 = close.ewm(
                span=26,
                adjust=False
            ).mean()

            data["macd"] = ema_12 - ema_26

            data["macd_signal"] = data["macd"].ewm(
                span=9,
                adjust=False
            ).mean()

            data["macd_hist"] = (
                data["macd"] - data["macd_signal"]
            )

            # ==========================================================
            # 6. BOLLINGER BANDS
            # ==========================================================

            data["bb_middle"] = close.rolling(20).mean()

            bb_std = close.rolling(20).std()

            data["bb_upper"] = (
                data["bb_middle"] + (2 * bb_std)
            )

            data["bb_lower"] = (
                data["bb_middle"] - (2 * bb_std)
            )

            data["bb_width"] = (
                (data["bb_upper"] - data["bb_lower"])
                / data["bb_middle"].replace(0, np.nan)
            )

            # ==========================================================
            # 7. VOLATILITY
            # ==========================================================

            data["rolling_volatility"] = (
                close.pct_change()
                .rolling(14)
                .std()
            )

            data["price_change"] = close.pct_change()

            # ==========================================================
            # 8. VOLUME
            # ==========================================================

            data["volume_sma"] = volume.rolling(20).mean()

            data["volume_ratio"] = (
                volume
                / data["volume_sma"].replace(0, np.nan)
            )

            # ==========================================================
            # 9. MARKET POSITION / ATR FEATURES
            # ==========================================================

            data["atr_percent"] = (
                data["atr_14"]
                / close.replace(0, np.nan)
            ) * 100

            data["distance_from_sma_50"] = (
                (close - data["sma_50"])
                / data["sma_50"].replace(0, np.nan)
            )

            # ==========================================================
            # FINAL CLEANUP
            # ==========================================================

            data.replace([np.inf, -np.inf], np.nan, inplace=True)

            # Only remove rows that are unusable for the core strategy.
            core_features = [
                "sma_9",
                "sma_21",
                "sma_50",
                "rsi",
                "atr_14",
                "adx",
                "plus_di",
                "minus_di",
                "macd",
                "macd_signal",
                "bb_middle",
                "bb_upper",
                "bb_lower",
                "volume_sma",
            ]

            before = len(data)

            data.dropna(
                subset=core_features,
                inplace=True
            )

            dropped = before - len(data)

            if data.empty:
                logger.error(
                    "[FEATURE ENGINEERING] No usable rows remain "
                    "after indicator warm-up."
                )
                return pd.DataFrame()

            logger.info(
                "[FEATURE ENGINEERING] Successfully computed features. "
                f"Input rows: {before} | Dropped: {dropped} | "
                f"Usable rows: {len(data)}"
            )

            return data

        except Exception as e:
            logger.exception(
                f"[FEATURE ENGINEERING ERROR] {e}"
            )
            return pd.DataFrame()


# Backward compatibility.
FeatureEngineer = FeatureCalculator