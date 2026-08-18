from __future__ import annotations

from app.features.calculator import FeatureCalculator

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from app.config.settings import settings
from app.risk.manager import RiskManager
from app.strategy.engines import MeanReversionStrategy, TrendStrategy
from app.strategy.filters import MultiTimeframeFilter
from app.strategy.regime import MarketRegimeDetector

from app.db.memory import init_db, log_trade_decision, query_setup_expectancy

from app.data.validator import DataValidator, DataValidationError


@dataclass
class BacktestTrade:
    trade_id: int
    symbol: str
    side: str
    entry_time: Any
    exit_time: Any
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    risk_amount: float
    pnl: float
    pnl_pct_on_risk: float
    exit_reason: str
    regime: str


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        val = float(value)
        return val if np.isfinite(val) else default
    except (TypeError, ValueError):
        return default


def calculate_backtest_metrics(
    initial_capital: float, equity_curve: pd.Series, trades: list[dict]
) -> dict:
    default_metrics = {
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(initial_capital, 2),
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": 0.0,
        "profit_factor": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "expectancy_usd": 0.0,
        "average_win": 0.0,
        "average_loss": 0.0,
        "largest_win": 0.0,
        "largest_loss": 0.0,
        "consecutive_losses_max": 0,
        "total_trades": 0,
    }

    if equity_curve is None or equity_curve.empty or len(trades) == 0:
        return default_metrics

    final_capital = float(equity_curve.iloc[-1])
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100.0

    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max.replace(0, np.nan)
    max_drawdown_pct = float(drawdown.min() * 100.0) if not drawdown.empty else 0.0

    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_rate = (len(wins) / len(pnls)) * 100.0 if pnls else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    )

    returns = equity_curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    sharpe_ratio, sortino_ratio = 0.0, 0.0
    if len(returns) > 1 and returns.std(ddof=1) > 0:
        annual_factor = np.sqrt(365 * 24)  # Hourly scaling factor
        sharpe_ratio = (returns.mean() / returns.std(ddof=1)) * annual_factor

        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std(ddof=1) > 0:
            sortino_ratio = (returns.mean() / downside_returns.std(ddof=1)) * annual_factor

    max_consecutive_losses, current_losses = 0, 0
    for pnl in pnls:
        if pnl < 0:
            current_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            current_losses = 0

    expectancy = float(np.mean(pnls)) if pnls else 0.0

    return {
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(final_capital, 2),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2) if np.isfinite(profit_factor) else "INF",
        "sharpe_ratio": round(float(sharpe_ratio), 2),
        "sortino_ratio": round(float(sortino_ratio), 2),
        "expectancy_usd": round(expectancy, 2),
        "average_win": round(float(np.mean(wins)), 2) if wins else 0.0,
        "average_loss": round(float(np.mean(losses)), 2) if losses else 0.0,
        "largest_win": round(max(wins), 2) if wins else 0.0,
        "largest_loss": round(min(losses), 2) if losses else 0.0,
        "consecutive_losses_max": max_consecutive_losses,
        "total_trades": len(trades),
    }


class BacktestEngine:
    """Institutional Phase-1 Event-Driven Backtesting Simulation Engine."""

    DEFAULT_FEE_RATE = 0.00075  # 0.075% Binance Taker Fee
    DEFAULT_SLIPPAGE_RATE = 0.0005  # 0.05% Dynamic Slippage Base

    @staticmethod
    def validate_market_data(
        df: pd.DataFrame,
        *,
        timeframe: str = "1h",
        require_volume: bool = True,
        strict_gaps: bool = False,
    ):
        """
        Validate market data before feature calculation or backtesting.

        DataValidator remains the canonical validation implementation.
        This method only provides the BacktestEngine integration point.
        """
        validator = DataValidator(
            timeframe=timeframe,
            require_volume=require_volume,
            reject_gaps=strict_gaps,
            max_zero_volume_pct=0.0,
            minimum_rows=200,
        )

        return validator.validate(
            df,
            raise_on_error=True,
        )


    @classmethod
    def _generate_signal(cls, window: pd.DataFrame) -> tuple[str, str]:
        regime = MarketRegimeDetector.detect_regime(window)
        signal = "HOLD"

        if regime == "TRENDING":
            signal = TrendStrategy.generate_signal(window)
            # MultiTimeframeFilter is a trend-alignment confirmation (requires
            # close/EMA20/EMA50 stacked in signal direction) — appropriate for
            # trend-following entries, which want confluence with the macro trend.
            signal = MultiTimeframeFilter.confirm_trend(window, signal)
        elif regime == "RANGING":
            signal = MeanReversionStrategy.generate_signal(window)
            # Deliberately NOT passed through MultiTimeframeFilter: mean-reversion
            # entries are taken *against* short-term price extension (price near/
            # below a falling short MA), which is close to definitionally the
            # opposite of what confirm_trend requires. Applying it here rejected
            # 100% of MeanReversionStrategy signals in backtesting (verified: 20
            # raw signals, 0 confirmed, over 1,399 real BTCUSDT_1h candles) — the
            # strategy's own Bollinger-band + RSI-extreme logic is its confirmation.

        return signal, regime

    @classmethod
    def run_backtest(
        cls,
        df: pd.DataFrame,
        initial_capital: float = 10000.0,
        symbol: str = "BTC/USDT",
        fee_rate: float | None = None,
        slippage_rate: float | None = None,
        enable_breakeven: bool = True,
    ) -> dict:

            # ---------------------------------------------------------
        # MARKET DATA VALIDATION
        # ---------------------------------------------------------
        validation_report = BacktestEngine.validate_market_data(
            df,
            timeframe="1h",
            require_volume=True,
            strict_gaps=False,
        )
        
        init_db()



        if df is None or df.empty or len(df) < 60:
            return {"status": "ERROR", "message": "Insufficient data. Minimal 60 bars required."}

        fee = cls.DEFAULT_FEE_RATE if fee_rate is None else max(float(fee_rate), 0.0)
        slippage = cls.DEFAULT_SLIPPAGE_RATE if slippage_rate is None else max(float(slippage_rate), 0.0)

        featured_df = FeatureCalculator.calculate_features(df)
        if featured_df.empty:
            return {"status": "ERROR", "message": "Feature calculation failed."}

        capital = float(initial_capital)
        position, pending_signal = None, None
        trades, equity_values, equity_times = [], [], []
        trade_counter = 0

        for i in range(1, len(featured_df)):
            window = featured_df.iloc[: i + 1]
            row = window.iloc[-1]
            timestamp = window.index[-1]

            open_price = _safe_float(row.get("open"))
            high_price = _safe_float(row.get("high"))
            low_price = _safe_float(row.get("low"))
            close_price = _safe_float(row.get("close"))
            atr = _safe_float(row.get("atr_14"), close_price * 0.015)

            if min(open_price, high_price, low_price, close_price) <= 0:
                continue

            # 1. Execute Pending Signal at Bar OPEN (Strict Zero Look-Ahead Bias)
            if pending_signal is not None and position is None:
                sig_side = pending_signal["signal"]
                sig_regime = pending_signal["regime"]

                exec_entry = open_price * (1 + slippage) if sig_side == "BUY" else open_price * (1 - slippage)

                stop_loss = RiskManager.calculate_stop_loss(exec_entry, sig_side, atr)
                take_profit = RiskManager.calculate_take_profit(exec_entry, stop_loss, sig_side) if stop_loss else None

                if stop_loss and take_profit:
                    pos_size = RiskManager.calculate_position_size(capital, exec_entry, stop_loss)
                    actual_pos_size = pos_size.get("position_size", 0.0) if isinstance(pos_size, dict) else pos_size
                    risk_amt = abs(exec_entry - stop_loss) * actual_pos_size

                    if actual_pos_size > 0 and RiskManager.check_open_risk_capacity(capital, 0.0, risk_amt):
                        entry_fee = (exec_entry * actual_pos_size) * fee
                        if capital > entry_fee:
                            capital -= entry_fee
                            position = {
                                "side": sig_side,
                                "entry_time": timestamp,
                                "entry_price": exec_entry,
                                "stop_loss": stop_loss,
                                "initial_stop": stop_loss,
                                "take_profit": take_profit,
                                "position_size": actual_pos_size,
                                "risk_amount": risk_amt,
                                "regime": sig_regime,
                                "breakeven_active": False,
                            }
                pending_signal = None

            # 2. Position Lifecycle Management (Stops, Targets, Breakeven)
            if position is not None:
                side = position["side"]
                st_loss = position["stop_loss"]
                tk_prof = position["take_profit"]

                # Breakeven Stop Adjustment (Triggers at 1.0 R:R distance)
                if enable_breakeven and not position["breakeven_active"]:
                    trigger_dist = abs(position["entry_price"] - position["initial_stop"])
                    if (side == "BUY" and high_price >= position["entry_price"] + trigger_dist) or \
                       (side == "SELL" and low_price <= position["entry_price"] - trigger_dist):
                        position["stop_loss"] = position["entry_price"]
                        position["breakeven_active"] = True

                stop_hit = low_price <= st_loss if side == "BUY" else high_price >= st_loss
                target_hit = high_price >= tk_prof if side == "BUY" else low_price <= tk_prof

                exit_price, exit_reason = None, None
                if stop_hit:
                    exit_price, exit_reason = st_loss, "STOP_LOSS"
                elif target_hit:
                    exit_price, exit_reason = tk_prof, "TAKE_PROFIT"

                if exit_price is not None:
                    exec_exit = exit_price * (1 - slippage) if side == "BUY" else exit_price * (1 + slippage)
                    gross_pnl = (
                        (exec_exit - position["entry_price"]) * position["position_size"]
                        if side == "BUY"
                        else (position["entry_price"] - exec_exit) * position["position_size"]
                    )
                    exit_fee = (exec_exit * position["position_size"]) * fee
                    net_pnl = gross_pnl - exit_fee

                    capital += net_pnl
                    trade_counter += 1

                    trades.append(
                        asdict(
                            BacktestTrade(
                                trade_id=trade_counter,
                                symbol=symbol,
                                side=side,
                                entry_time=position["entry_time"],
                                exit_time=timestamp,
                                entry_price=position["entry_price"],
                                exit_price=exec_exit,
                                stop_loss=position["initial_stop"],
                                take_profit=position["take_profit"],
                                position_size=position["position_size"],
                                risk_amount=position["risk_amount"],
                                pnl=net_pnl,
                                pnl_pct_on_risk=(net_pnl / position["risk_amount"] * 100.0) if position["risk_amount"] > 0 else 0.0,
                                exit_reason=exit_reason,
                                regime=position["regime"],
                            )
                        )
                    )
                    
                    log_trade_decision({
                        "timestamp": str(timestamp),
                        "symbol": symbol,
                        "regime": position["regime"],
                        "adx": _safe_float(row.get("adx")),
                        "bb_width": _safe_float(row.get("bb_width")),
                        "volume": _safe_float(row.get("volume")),
                        "rsi": int(_safe_float(row.get("rsi_14"), 50)),
                        "signal_type": side,
                        "strategy_name": "TrendStrategy" if position["regime"] == "TRENDING" else "MeanReversionStrategy",
                        "risk_reward": abs(position["take_profit"] - position["entry_price"]) / abs(position["entry_price"] - position["initial_stop"]) if abs(position["entry_price"] - position["initial_stop"]) > 0 else 0.0,
                        "result": "WIN" if net_pnl > 0 else "LOSS",
                        "pnl": net_pnl,
                        "notes": f"Exit via {exit_reason}"
                    })
                    position = None

            # 3. Generate Signals Post-Bar Close
            sig, reg = cls._generate_signal(window)
            if position is None and sig in ("BUY", "SELL"):
                
                # --- MARKET MEMORY FILTER ---
                current_adx = _safe_float(row.get("adx_14"))
                current_rsi = int(_safe_float(row.get("rsi_14"), 50))
                
                # Check +/- 5 points on ADX (RSI +/- 3 is handled inside the SQL query)
                adx_range = (current_adx - 5.0, current_adx + 5.0)
                
                # Query historical performance for this exact market state
                expectancy = query_setup_expectancy(reg, adx_range, current_rsi)
                
                # Block the trade if we have enough data (e.g., at least 1 past trade) 
                # AND the historical win rate is poor (< 50%) or average PnL is negative.
                if expectancy["total_trades"] >= 1 and (expectancy["win_rate"] < 50.0 or expectancy["avg_pnl"] < 0):
                    logger.info(
                        f"[MEMORY FILTER] Blocked {sig} in {reg} | "
                        f"ADX: {current_adx:.1f}, RSI: {current_rsi} | "
                        f"Past Trades: {expectancy['total_trades']}, "
                        f"Win Rate: {expectancy['win_rate']:.1f}%, Avg PnL: {expectancy['avg_pnl']:.2f}"
                    )
                    pending_signal = None  # Trade blocked by memory!
                else:
                    pending_signal = {"signal": sig, "regime": reg}
                    
            # 4. Mark-To-Market Equity Curve Evaluation
            mtm_equity = capital
            if position is not None:
                unrealized = (
                    (close_price - position["entry_price"]) * position["position_size"]
                    if position["side"] == "BUY"
                    else (position["entry_price"] - close_price) * position["position_size"]
                )
                mtm_equity += unrealized

            equity_times.append(timestamp)
            equity_values.append(float(mtm_equity))

        # Close Remaining Open Position at End of Dataset
        if position is not None:
            last_close = _safe_float(featured_df.iloc[-1]["close"])
            exec_exit = last_close * (1 - slippage) if position["side"] == "BUY" else last_close * (1 + slippage)
            gross_pnl = (
                (exec_exit - position["entry_price"]) * position["position_size"]
                if position["side"] == "BUY"
                else (position["entry_price"] - exec_exit) * position["position_size"]
            )
            net_pnl = gross_pnl - ((exec_exit * position["position_size"]) * fee)
            capital += net_pnl
            trade_counter += 1

            trades.append(
                asdict(
                    BacktestTrade(
                        trade_id=trade_counter,
                        symbol=symbol,
                        side=position["side"],
                        entry_time=position["entry_time"],
                        exit_time=featured_df.index[-1],
                        entry_price=position["entry_price"],
                        exit_price=exec_exit,
                        stop_loss=position["initial_stop"],
                        take_profit=position["take_profit"],
                        position_size=position["position_size"],
                        risk_amount=position["risk_amount"],
                        pnl=net_pnl,
                        pnl_pct_on_risk=(net_pnl / position["risk_amount"] * 100.0) if position["risk_amount"] > 0 else 0.0,
                        exit_reason="END_OF_DATA",
                        regime=position["regime"],
                    )
                )
            )

        equity_curve = pd.Series(equity_values, index=equity_times, name="equity", dtype=float)
        metrics = calculate_backtest_metrics(initial_capital, equity_curve, trades)

        metrics.update(
            {
                "status": "SUCCESS",
                "symbol": symbol,
                "candles_tested": len(featured_df),
                "fee_rate": fee,
                "slippage_rate": slippage,
                "equity_curve": equity_curve,
                "trades": trades,
            }
        )

        return metrics
