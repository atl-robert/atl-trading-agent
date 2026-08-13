import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    """
    Central configuration for the trading agent.

    IMPORTANT:
    Phase 1 is intended for Binance Testnet / paper-style testing.
    Do not switch to live trading until the complete system has been
    validated with extensive testing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------------------------------------------------------
    # Trading mode
    # ---------------------------------------------------------

    TRADING_MODE: str = Field(
        default_factory=lambda: os.getenv("TRADING_MODE", "PAPER")
    )

    # ---------------------------------------------------------
    # Account
    # ---------------------------------------------------------

    ACCOUNT_BALANCE: float = Field(
        default_factory=lambda: float(
            os.getenv("ACCOUNT_BALANCE", "10000")
        )
    )

    # ---------------------------------------------------------
    # Broker / exchange
    # ---------------------------------------------------------

    BROKER_API_KEY: str = Field(
        default_factory=lambda: os.getenv("BROKER_API_KEY", "")
    )

    BROKER_ACCOUNT_ID: str = Field(
        default_factory=lambda: os.getenv("BROKER_ACCOUNT_ID", "")
    )

    BROKER_ENVIRONMENT: str = Field(
        default_factory=lambda: os.getenv(
            "BROKER_ENVIRONMENT",
            "practice",
        )
    )

    BINANCE_API_KEY: str = Field(
        default_factory=lambda: os.getenv("BINANCE_API_KEY", "")
    )

    BINANCE_API_SECRET: str = Field(
        default_factory=lambda: os.getenv("BINANCE_API_SECRET", "")
    )

    BINANCE_TESTNET: bool = Field(
        default_factory=lambda: os.getenv(
            "BINANCE_TESTNET",
            "true",
        ).lower()
        in ("true", "1", "yes", "on")
    )

    # ---------------------------------------------------------
    # Risk management
    # ---------------------------------------------------------

    RISK_PER_TRADE_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("RISK_PER_TRADE_PCT", "0.005")
        )
    )

    MAX_OPEN_RISK_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("MAX_OPEN_RISK_PCT", "0.02")
        )
    )

    MAX_DAILY_LOSS_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("MAX_DAILY_LOSS_PCT", "0.02")
        )
    )

    MAX_WEEKLY_LOSS_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("MAX_WEEKLY_LOSS_PCT", "0.05")
        )
    )

    MAX_DRAWDOWN_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("MAX_DRAWDOWN_PCT", "0.10")
        )
    )

    STOP_LOSS_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("STOP_LOSS_PCT", "0.02")
        )
    )

    TAKE_PROFIT_PCT: float = Field(
        default_factory=lambda: float(
            os.getenv("TAKE_PROFIT_PCT", "0.04")
        )
    )

    # ---------------------------------------------------------
    # Database
    # ---------------------------------------------------------

    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "sqlite:///./data/trading_agent.db",
        )
    )

    # ---------------------------------------------------------
    # Ollama
    # ---------------------------------------------------------

    OLLAMA_HOST: str = Field(
        default_factory=lambda: os.getenv(
            "OLLAMA_HOST",
            "http://localhost:11434",
        )
    )

    OLLAMA_MODEL: str = Field(
        default_factory=lambda: os.getenv(
            "OLLAMA_MODEL",
            "qwen2.5:7b",
        )
    )

    # ---------------------------------------------------------
    # Telegram
    # ---------------------------------------------------------

    TELEGRAM_BOT_TOKEN: str = Field(
        default_factory=lambda: os.getenv(
            "TELEGRAM_BOT_TOKEN",
            "",
        )
    )

    TELEGRAM_CHAT_ID: str = Field(
        default_factory=lambda: os.getenv(
            "TELEGRAM_CHAT_ID",
            "",
        )
    )


settings = Settings()