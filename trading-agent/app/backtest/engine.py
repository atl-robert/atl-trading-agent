import pandas as pd
from loguru import logger
from app.features.calculator import FeatureEngineer
from app.strategy.regime import MarketRegimeDetector
from app.strategy.engines import TrendStrategy, MeanReversionStrategy
import numpy as np
import pandas as pd

def calculate_backtest_metrics(initial_capital: float, equity_curve: pd.Series, trades: list) -> dict:
    final_capital = equity_curve.iloc[-1]
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100
    
    # Calculate Drawdown
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown_pct = drawdown.min() * 100
    
    # Win Rate & Profit Factor
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0.0
    
    # Sharpe Ratio (assuming daily returns, annualized)
    returns = equity_curve.pct_change().dropna()
    sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if not returns.empty and returns.std() != 0 else 0.0

    return {
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "win_rate_pct": round(win_rate, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "total_trades": len(trades)
    }

class BacktestEngine:
    @staticmethod
    def run_backtest(df: pd.DataFrame, initial_capital: float = 10000.0) -> dict:
        """
        Simulates the trading agent step-by-step across historical OHLCV data
        and returns performance statistics.
        """
        if df is None or len(df) < 50:
            logger.error("[BACKTEST] Insufficient data for backtesting.")
            return {"status": "ERROR", "message": "Not enough data."}

        logger.info(f"[BACKTEST] Starting simulation with initial capital: ${initial_capital:,.2f}")
        
        capital = initial_capital
        position = 0.0
        entry_price = 0.0
        trades = []

        # Compute features across the entire dataset first
        featured_df = FeatureEngineer.compute_features(df)
        if featured_df.empty:
            return {"status": "ERROR", "message": "Feature calculation failed during backtest."}

        # Step through historical candles
        for i in range(20, len(featured_df)):
            window_df = featured_df.iloc[:i+1]
            current_row = window_df.iloc[-1]
            price = current_row['close']

            # 1. Detect Regime & Generate Signal
            regime = MarketRegimeDetector.detect_regime(window_df)
            signal = "HOLD"
            if regime == "TRENDING":
                signal = TrendStrategy.generate_signal(window_df)
            elif regime == "RANGING":
                signal = MeanReversionStrategy.generate_signal(window_df)

            # 2. Execute Trade Simulation
            if position == 0:
                if signal == "BUY":
                    position = (capital * 0.95) / price  # Allocate 95% of capital
                    entry_price = price
                    trades.append({"type": "BUY", "price": entry_price, "index": i})
                elif signal == "SELL":
                    # Short or exit logic simplified for MVP simulation
                    pass
            elif position > 0:
                # Exit condition: Stop loss (1%) or take profit (2%) or opposite signal
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct <= -0.01 or pnl_pct >= 0.02 or signal == "SELL":
                    capital = position * price
                    trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "capital": capital})
                    position = 0.0

        # Close any open position at the final price
        if position > 0:
            final_price = featured_df.iloc[-1]['close']
            capital = position * final_price
            trades.append({"type": "CLOSE", "price": final_price, "capital": capital})

        total_return_pct = ((capital - initial_capital) / initial_capital) * 100
        logger.info(f"[BACKTEST COMPLETE] Final Capital: ${capital:,.2f} | Return: {total_return_pct:.2f}%")

        return {
            "initial_capital": initial_capital,
            "final_capital": round(capital, 2),
            "total_return_pct": round(total_return_pct, 2),
            "total_trades": len(trades) // 2
        }