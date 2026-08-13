from datetime import datetime, UTC
from pathlib import Path

from loguru import logger
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
)

from app.config.settings import settings


# ============================================================
# Database URL
# ============================================================

DATABASE_URL = settings.DATABASE_URL


# ============================================================
# SQLite directory
# ============================================================

if DATABASE_URL.startswith(
    "sqlite:///./"
):

    db_path = DATABASE_URL.replace(
        "sqlite:///./",
        "",
        1,
    )

    Path(db_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# Engine
# ============================================================

connect_args = {}

if DATABASE_URL.startswith("sqlite"):

    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


# ============================================================
# Trade Journal
# ============================================================

class TradeJournalModel(Base):

    __tablename__ = "trade_journal"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

    symbol = Column(
        String,
        index=True,
    )

    signal = Column(
        String,
    )

    regime = Column(
        String,
    )

    entry_price = Column(
        Float,
    )

    position_size = Column(
        Float,
    )

    status = Column(
        String,
    )


# ============================================================
# Initialize database
# ============================================================

def init_db():

    Base.metadata.create_all(
        bind=engine
    )

    logger.info(
        "[DATABASE] SQLite journal "
        "initialized successfully."
    )


# ============================================================
# Log trade
# ============================================================

def log_trade_to_db(
    symbol: str,
    signal: str,
    regime: str,
    entry_price: float,
    position_size: float,
    status: str = "SIGNAL_GENERATED",
):

    init_db()

    db = SessionLocal()

    try:

        trade_log = TradeJournalModel(
            symbol=symbol,
            signal=signal,
            regime=regime,
            entry_price=entry_price,
            position_size=position_size,
            status=status,
        )

        db.add(trade_log)
        db.commit()
        db.refresh(trade_log)

        logger.info(
            f"[DATABASE] Logged "
            f"{symbol} | "
            f"Signal: {signal} | "
            f"Status: {status}"
        )

        return trade_log.id

    except Exception as e:

        db.rollback()

        logger.error(
            f"[DATABASE ERROR] "
            f"Failed to log trade: {e}"
        )

        return None

    finally:

        db.close()