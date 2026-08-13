from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from loguru import logger

from app.backtest.engine import BacktestEngine
from app.config.settings import settings
from app.data.fetcher import MarketDataFetcher
from app.execution.router import ExecutionRouter
from app.journal.database import (
    SessionLocal,
    TradeJournalModel,
    init_db,
)


scheduler = BackgroundScheduler()


def scheduled_trading_job():

    symbols = [
        "BTC/USDT",
    ]

    logger.info(
        "[SCHEDULER] Running automated "
        "trading cycle..."
    )

    for symbol in symbols:

        try:

            # Phase 1 scheduler uses Binance data
            # through the execution test script.
            #
            # This scheduler can be expanded into
            # a dedicated exchange data layer later.

            df = MarketDataFetcher.fetch_ohlcv(
                symbol="BTC-USD",
                period="10d",
                interval="1h",
            )

            if df.empty:

                logger.warning(
                    f"[SCHEDULER] "
                    f"Skipped {symbol}: "
                    "No data fetched."
                )

                continue

            result = ExecutionRouter.process_tick(
                symbol=symbol,
                df=df,
            )

            logger.info(
                f"[SCHEDULER] Completed "
                f"{symbol}: "
                f"{result.get('signal', 'UNKNOWN')}"
            )

        except Exception as e:

            logger.error(
                f"[SCHEDULER ERROR] "
                f"{symbol}: {e}"
            )


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    scheduler.add_job(
        scheduled_trading_job,
        "interval",
        hours=1,
        id="hourly_trading_tick",
        replace_existing=True,
    )

    scheduler.start()

    logger.info(
        "[SERVER STARTUP] "
        "Background trading scheduler "
        "started successfully."
    )

    yield

    scheduler.shutdown()

    logger.info(
        "[SERVER SHUTDOWN] "
        "Background trading scheduler "
        "stopped."
    )


app = FastAPI(
    title="Algorithmic Trading Agent",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root():

    return {
        "status": "online",
        "mode": settings.TRADING_MODE,
        "message": (
            "Trading Agent backend and "
            "scheduler are running."
        ),
    }


@app.post("/api/v1/run-tick")
def run_tick(
    symbol: str = "BTC-USD",
    use_live_data: bool = True,
):

    logger.info(
        f"[API] Manual tick: "
        f"{symbol} | "
        f"Live Data: {use_live_data}"
    )

    if use_live_data:

        df = MarketDataFetcher.fetch_ohlcv(
            symbol=symbol,
            period="60d",
            interval="1h",
        )

        if df.empty:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Failed to fetch "
                    f"market data for {symbol}."
                ),
            )

    else:

        np.random.seed(42)

        dates = pd.date_range(
            end=pd.Timestamp.now(),
            periods=200,
            freq="h",
        )

        base_price = 1.1000

        price_walk = (
            base_price
            + np.cumsum(
                np.random.normal(
                    0,
                    0.0010,
                    200,
                )
            )
        )

        df = pd.DataFrame(
            {
                "open": price_walk,
                "high": price_walk
                + abs(
                    np.random.normal(
                        0,
                        0.0005,
                        200,
                    )
                ),
                "low": price_walk
                - abs(
                    np.random.normal(
                        0,
                        0.0005,
                        200,
                    )
                ),
                "close": price_walk,
                "volume": np.random.randint(
                    1000,
                    5000,
                    200,
                ),
            },
            index=dates,
        )

    result = ExecutionRouter.process_tick(
        symbol=symbol,
        df=df,
    )

    return {
        "result": result
    }


@app.post("/api/v1/backtest")
def run_backtest(
    symbol: str = "BTC-USD",
    initial_capital: float = 10000.0,
):

    logger.info(
        f"[API] Running backtest "
        f"for {symbol}..."
    )

    df = MarketDataFetcher.fetch_ohlcv(
        symbol=symbol,
        period="60d",
        interval="1h",
    )

    if df.empty:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Failed to fetch "
                f"backtest data for {symbol}."
            ),
        )

    performance = BacktestEngine.run_backtest(
        df,
        initial_capital=initial_capital,
    )

    return {
        "backtest_results": performance
    }


@app.get("/api/v1/journal")
def get_trade_journal(
    limit: int = 50,
):

    init_db()

    db = SessionLocal()

    try:

        logs = (
            db.query(TradeJournalModel)
            .order_by(
                TradeJournalModel.timestamp.desc()
            )
            .limit(limit)
            .all()
        )

        return {
            "total_records": len(logs),
            "logs": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp,
                    "symbol": log.symbol,
                    "signal": log.signal,
                    "regime": log.regime,
                    "entry_price": log.entry_price,
                    "position_size": log.position_size,
                    "status": log.status,
                }
                for log in logs
            ],
        }

    except Exception as e:

        logger.error(
            f"[API ERROR] "
            f"Failed to fetch journal: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not retrieve trade journal.",
        )

    finally:

        db.close()