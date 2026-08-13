from loguru import logger

from app.config.settings import settings


class RiskManager:
    """
    Centralized position-sizing and risk-management engine.
    """

    @staticmethod
    def calculate_position_size(
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:

        if account_balance <= 0:
            logger.error(
                "[RISK MANAGER] Invalid account balance."
            )
            return 0.0

        if entry_price <= 0:
            logger.error(
                "[RISK MANAGER] Invalid entry price."
            )
            return 0.0

        if stop_loss_price <= 0:
            logger.error(
                "[RISK MANAGER] Invalid stop-loss price."
            )
            return 0.0

        risk_amount = (
            account_balance
            * settings.RISK_PER_TRADE_PCT
        )

        price_risk = abs(
            entry_price - stop_loss_price
        )

        if price_risk <= 0:
            logger.error(
                "[RISK MANAGER] Entry and stop loss "
                "cannot be identical."
            )
            return 0.0

        position_size = (
            risk_amount / price_risk
        )

        logger.info(
            "[RISK MANAGER] "
            f"Account: ${account_balance:,.2f} | "
            f"Risk: ${risk_amount:,.2f} | "
            f"Entry: ${entry_price:,.4f} | "
            f"Stop: ${stop_loss_price:,.4f} | "
            f"Units: {position_size:.8f}"
        )

        return float(position_size)