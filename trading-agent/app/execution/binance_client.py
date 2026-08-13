import os

import ccxt
from loguru import logger

from app.config.settings import settings


class BinanceExecutionClient:

    def __init__(self, testnet: bool = True):

        self.api_key = os.getenv(
            "BINANCE_API_KEY",
            settings.BINANCE_API_KEY,
        )

        self.api_secret = os.getenv(
            "BINANCE_API_SECRET",
            settings.BINANCE_API_SECRET,
        )

        self.testnet = testnet

        self.exchange = ccxt.binance({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
            },
        })

        if self.testnet:

            self.exchange.set_sandbox_mode(True)

            logger.info(
                "[BINANCE] Initialized in TESTNET "
                "SANDBOX mode."
            )

        else:

            logger.warning(
                "[BINANCE] LIVE PRODUCTION MODE."
            )

    @staticmethod
    def normalize_symbol(symbol: str) -> str:

        symbol = symbol.upper().strip()

        replacements = {
            "BTCUSDT": "BTC/USDT",
            "BTC-USD": "BTC/USDT",
            "BTCUSD": "BTC/USDT",
            "ETHUSDT": "ETH/USDT",
            "ETH-USD": "ETH/USDT",
            "ETHUSD": "ETH/USDT",
        }

        if symbol in replacements:
            return replacements[symbol]

        if "/" in symbol:
            return symbol

        if symbol.endswith("USDT"):
            base = symbol[:-4]
            return f"{base}/USDT"

        return symbol

    def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict:

        if side.upper() not in (
            "BUY",
            "SELL",
        ):
            return {
                "status": "error",
                "message": (
                    "Invalid order side."
                ),
            }

        if amount <= 0:
            return {
                "status": "error",
                "message": (
                    "Order amount must be greater than zero."
                ),
            }

        formatted_symbol = (
            self.normalize_symbol(symbol)
        )

        side = side.lower()

        logger.info(
            f"[BINANCE] Preparing "
            f"{side.upper()} order: "
            f"{amount:.8f} {formatted_symbol}"
        )

        try:

            # Load exchange market metadata.
            self.exchange.load_markets()

            if formatted_symbol not in self.exchange.markets:

                return {
                    "status": "error",
                    "message": (
                        f"Symbol {formatted_symbol} "
                        "is not available."
                    ),
                }

            market = self.exchange.market(
                formatted_symbol
            )

            # Respect exchange precision.
            amount = float(
                self.exchange.amount_to_precision(
                    formatted_symbol,
                    amount,
                )
            )

            if amount <= 0:
                return {
                    "status": "error",
                    "message": (
                        "Amount became zero after "
                        "exchange precision formatting."
                    ),
                }

            logger.info(
                f"[BINANCE] Submitting "
                f"{side.upper()} MARKET order "
                f"for {amount} "
                f"{formatted_symbol}"
            )

            order = self.exchange.create_order(
                symbol=formatted_symbol,
                type="market",
                side=side,
                amount=amount,
            )

            logger.info(
                "[BINANCE] Order successful! "
                f"ID: {order.get('id')}"
            )

            return {
                "status": "success",
                "order_id": order.get("id"),
                "symbol": formatted_symbol,
                "side": side.upper(),
                "requested_amount": amount,
                "filled_amount": order.get(
                    "filled"
                ),
                "filled_price": order.get(
                    "average",
                    order.get("price"),
                ),
                "cost": order.get("cost"),
                "raw_status": order.get("status"),
                "market_type": market.get(
                    "type"
                ),
            }

        except Exception as e:

            logger.error(
                f"[BINANCE ERROR] "
                f"Order execution failed: {e}"
            )

            return {
                "status": "error",
                "message": str(e),
            }