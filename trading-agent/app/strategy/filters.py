import pandas as pd
from loguru import logger


class MultiTimeframeFilter:
    """
    Phase 1 multi-timeframe confirmation layer.

    Uses the available dataframe to establish directional
    confirmation from the short and medium moving averages.

    This is not a true external higher-timeframe feed yet.
    """

    @staticmethod
    def confirm_trend(
        df: pd.DataFrame,
        signal: str,
    ) -> str:

        if signal == "HOLD":
            return "HOLD"

        if df is None or df.empty:
            logger.warning(
                "[MTF FILTER] No dataframe available."
            )
            return "HOLD"

        try:

            latest = df.iloc[-1]

            close = float(
                latest.get("close", 0)
            )

            sma_21 = float(
                latest.get("sma_21", close)
            )

            sma_50 = float(
                latest.get("sma_50", close)
            )

            if signal == "BUY":

                if (
                    close > sma_21
                    and close > sma_50
                ):
                    logger.info(
                        "[MTF FILTER] "
                        "Bullish confirmation PASSED."
                    )
                    return "BUY"

                logger.info(
                    "[MTF FILTER] "
                    "Bullish confirmation FAILED."
                )
                return "HOLD"

            if signal == "SELL":

                if (
                    close < sma_21
                    and close < sma_50
                ):
                    logger.info(
                        "[MTF FILTER] "
                        "Bearish confirmation PASSED."
                    )
                    return "SELL"

                logger.info(
                    "[MTF FILTER] "
                    "Bearish confirmation FAILED."
                )
                return "HOLD"

            return "HOLD"

        except Exception as e:

            logger.error(
                f"[MTF FILTER ERROR] {e}"
            )

            return "HOLD"