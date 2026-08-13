import ccxt
import pandas as pd

from app.execution.router import ExecutionRouter


def main():

    print("=" * 60)
    print("TRADING AGENT — PHASE 1 TEST")
    print("=" * 60)

    print()
    print("Connecting to Binance Testnet...")

    exchange = ccxt.binance({
        "enableRateLimit": True,
    })

    exchange.set_sandbox_mode(True)

    symbol = "BTC/USDT"
    timeframe = "1h"
    limit = 200

    print(
        f"Fetching {limit} candles "
        f"for {symbol}..."
    )

    try:

        ohlcv = exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit,
        )

    except Exception as e:

        print()
        print(
            f"ERROR: Failed to fetch market data: {e}"
        )

        return

    if not ohlcv:

        print(
            "ERROR: Binance returned no candles."
        )

        return

    df = pd.DataFrame(
        ohlcv,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="ms",
        utc=True,
    )

    df = df.set_index(
        "timestamp"
    )

    print(
        f"Fetched {len(df)} candles."
    )

    print()
    print(
        "Passing market data through "
        "ExecutionRouter..."
    )

    result = ExecutionRouter.process_tick(
        symbol=symbol,
        df=df,
    )

    print()
    print("=" * 60)
    print("EXECUTION RESULT")
    print("=" * 60)

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )

    print()
    print("=" * 60)
    print("PHASE 1 TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()