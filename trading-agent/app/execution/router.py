import pandas as pd
from loguru import logger

from app.config.settings import settings
from app.features.calculator import FeatureEngineer
from app.strategy.regime import MarketRegimeDetector
from app.strategy.engines import (
    TrendStrategy,
    MeanReversionStrategy,
)
from app.strategy.filters import MultiTimeframeFilter
from app.risk.manager import RiskManager
from app.journal.database import log_trade_to_db
from app.notifications.telegram import TelegramNotifier
from app.execution.binance_client import BinanceExecutionClient


class ExecutionRouter:
    """
    Central execution coordinator.

    Pipeline:

        Market Data
             ↓
        Feature Engineering
             ↓
        Market Regime
             ↓
        Strategy
             ↓
        Macro Trend Filter
             ↓
        Multi-Timeframe Filter
             ↓
        Risk Management
             ↓
        Journal
             ↓
        Telegram
             ↓
        Binance Testnet
    """

    client = BinanceExecutionClient(
        testnet=settings.BINANCE_TESTNET
    )

    @classmethod
    def process_tick(
        cls,
        symbol: str,
        df: pd.DataFrame,
    ) -> dict:

        logger.info(
            f"[ROUTER] Processing execution tick for {symbol}..."
        )

        # =====================================================
        # 1. Validate incoming market data
        # =====================================================

        if df is None or df.empty:
            logger.error(
                "[ROUTER ERROR] Empty market dataframe."
            )

            return {
                "status": "ERROR",
                "message": "Market dataframe is empty.",
                "symbol": symbol,
            }

        # =====================================================
        # 2. Feature Engineering
        # =====================================================

        featured_df = FeatureEngineer.compute_features(df)

        if featured_df is None or featured_df.empty:
            logger.error(
                "[ROUTER ERROR] Feature engineering failed."
            )

            return {
                "status": "ERROR",
                "message": "Feature calculation failed.",
                "symbol": symbol,
            }

        # =====================================================
        # 3. Market Regime Detection
        # =====================================================

        regime = MarketRegimeDetector.detect_regime(
            featured_df
        )

        if regime == "UNKNOWN":
            logger.warning(
                "[ROUTER] Market regime unknown. "
                "No trade will be executed."
            )

            return {
                "status": "NO_TRADE",
                "symbol": symbol,
                "regime": regime,
                "signal": "HOLD",
                "reason": "Unknown market regime.",
            }

        # =====================================================
        # 4. Macro Trend
        # =====================================================

        latest = featured_df.iloc[-1]

        current_price = float(
            latest.get("close", 0)
        )

        sma_50 = float(
            latest.get(
                "sma_50",
                current_price,
            )
        )

        if current_price <= 0:
            logger.error(
                "[ROUTER ERROR] Invalid current price."
            )

            return {
                "status": "ERROR",
                "message": "Invalid market price.",
                "symbol": symbol,
            }

        macro_trend = (
            "BULLISH"
            if current_price >= sma_50
            else "BEARISH"
        )

        logger.info(
            f"[ROUTER] Detected Market Regime: "
            f"{regime} | Macro Trend: {macro_trend}"
        )

        # =====================================================
        # 5. Strategy Routing
        # =====================================================

        signal = "HOLD"

        if regime == "TRENDING":

            raw_signal = TrendStrategy.generate_signal(
                featured_df
            )

            # Bullish macro trend:
            # allow BUY only
            if macro_trend == "BULLISH":
                if raw_signal == "BUY":
                    signal = "BUY"

            # Bearish macro trend:
            # allow SELL only
            elif macro_trend == "BEARISH":
                if raw_signal == "SELL":
                    signal = "SELL"

        elif regime == "RANGING":

            signal = MeanReversionStrategy.generate_signal(
                featured_df
            )

        elif regime == "VOLATILE":

            # Phase 1 safety rule:
            # do not trade extreme volatility.
            signal = "HOLD"

            logger.warning(
                "[ROUTER] VOLATILE regime detected. "
                "Trading disabled for this tick."
            )

        logger.info(
            f"[ROUTER] Strategy generated signal: {signal}"
        )

        # =====================================================
        # 6. Multi-Timeframe Confirmation
        # =====================================================

        signal = MultiTimeframeFilter.confirm_trend(
            featured_df,
            signal,
        )

        logger.info(
            f"[ROUTER] Final signal after MTF filter: "
            f"{signal}"
        )

        # =====================================================
        # 7. Stop Loss
        # =====================================================

        stop_loss = None

        if signal == "BUY":

            stop_loss = current_price * (
                1 - settings.STOP_LOSS_PCT
            )

        elif signal == "SELL":

            stop_loss = current_price * (
                1 + settings.STOP_LOSS_PCT
            )

        # =====================================================
        # 8. Risk Management
        # =====================================================

        position_size = 0.0

        if signal in ("BUY", "SELL"):

            position_size = RiskManager.calculate_position_size(
                account_balance=settings.ACCOUNT_BALANCE,
                entry_price=current_price,
                stop_loss_price=stop_loss,
            )

        logger.info(
            f"[ROUTER] Position size: "
            f"{position_size:.8f}"
        )

        # =====================================================
        # 9. HOLD = No Order
        # =====================================================

        if signal == "HOLD":

            position_size = 0.0

        # =====================================================
        # 10. Journal
        # =====================================================

        journal_status = (
            "SIGNAL_GENERATED"
            if signal in ("BUY", "SELL")
            else "HOLD"
        )

        log_trade_to_db(
            symbol=symbol,
            signal=signal,
            regime=regime,
            entry_price=current_price,
            position_size=position_size,
            status=journal_status,
        )

        # =====================================================
        # 11. Telegram Alert
        # =====================================================

        alert_message = (
            "🚨 *Trading Agent Update* 🚨\n\n"
            f"• *Symbol*: `{symbol}`\n"
            f"• *Regime*: `{regime}`\n"
            f"• *Macro Trend*: `{macro_trend}`\n"
            f"• *Signal*: `{signal}`\n"
            f"• *Price*: `${current_price:,.4f}`\n"
            f"• *Position Size*: `{position_size:.8f}`\n"
        )

        if stop_loss is not None:

            alert_message += (
                f"• *Stop Loss*: "
                f"`${stop_loss:,.4f}`\n"
            )

        TelegramNotifier.send_alert(
            alert_message
        )

        # =====================================================
        # 12. Binance Execution
        # =====================================================

        execution_response = None

        if (
            signal in ("BUY", "SELL")
            and position_size > 0
        ):

            # Phase 1 safety gate.
            if settings.TRADING_MODE.upper() == "PAPER":

                logger.info(
                    "[ROUTER] PAPER mode active. "
                    "Order will NOT be submitted."
                )

                execution_response = {
                    "status": "PAPER",
                    "message": (
                        "Signal generated but "
                        "live exchange order disabled."
                    ),
                }

            else:

                logger.info(
                    f"[ROUTER] Routing {signal} "
                    f"order to Binance..."
                )

                execution_response = (
                    cls.client.execute_order(
                        symbol=symbol,
                        side=signal,
                        amount=position_size,
                    )
                )

        # =====================================================
        # 13. Final Result
        # =====================================================

        return {
            "status": "SUCCESS",
            "symbol": symbol,
            "regime": regime,
            "macro_trend": macro_trend,
            "signal": signal,
            "entry_price": current_price,
            "stop_loss": stop_loss,
            "position_size": position_size,
            "trading_mode": settings.TRADING_MODE,
            "execution": execution_response,
        }