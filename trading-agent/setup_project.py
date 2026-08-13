import os

# Define the folder structure and files with their initial content
structure = {
    "app/__init__.py": "",
    "app/config/__init__.py": "",
    "app/config/settings.py": '''import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    TRADING_MODE: str = os.getenv("TRADING_MODE", "PAPER")
    BROKER_API_KEY: str = os.getenv("BROKER_API_KEY", "")
    BROKER_ACCOUNT_ID: str = os.getenv("BROKER_ACCOUNT_ID", "")
    BROKER_ENVIRONMENT: str = os.getenv("BROKER_ENVIRONMENT", "practice")
    RISK_PER_TRADE_PCT: float = float(os.getenv("RISK_PER_TRADE_PCT", "0.005"))
    MAX_OPEN_RISK_PCT: float = float(os.getenv("MAX_OPEN_RISK_PCT", "0.02"))
    MAX_DAILY_LOSS_PCT: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.02"))
    MAX_WEEKLY_LOSS_PCT: float = float(os.getenv("MAX_WEEKLY_LOSS_PCT", "0.05"))
    MAX_DRAWDOWN_PCT: float = float(os.getenv("MAX_DRAWDOWN_PCT", "0.10"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/trading_agent.db")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
''',
    "app/data/__init__.py": "",
    "app/data/schema.py": '''from pydantic import BaseModel, Field
from datetime import datetime

class MarketDataBar(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    source: str
''',
    "app/data/validator.py": '''import pandas as pd
from loguru import logger

class DataValidator:
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, symbol: str) -> bool:
        if df is None or df.empty:
            logger.error(f"[DATA UNAVAILABLE] DataFrame for {symbol} is empty.")
            return False
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                return False
        if df[required_cols].isnull().any().any() or (df[required_cols] <= 0).any().any():
            return False
        return True
''',
    "app/data/fetcher.py": '''import pandas as pd
import yfinance as yf
from loguru import logger
from app.data.validator import DataValidator

class ForexDataFetcher:
    @staticmethod
    def get_ticker_symbol(symbol: str) -> str:
        mapping = {
            "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
            "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X", "NZDUSD": "NZDUSD=X"
        }
        return mapping.get(symbol.upper(), f"{symbol}=X")

    @classmethod
    def fetch_historical_data(cls, symbol: str, period: str = "60d", interval: str = "1h") -> pd.DataFrame:
        ticker = cls.get_ticker_symbol(symbol)
        try:
            raw_data = yf.download(ticker, period=period, interval=interval, progress=False)
            if raw_data.empty:
                return pd.DataFrame()
            if isinstance(raw_data.columns, pd.MultiIndex):
                raw_data.columns = raw_data.columns.get_level_values(0)
            raw_data = raw_data.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            df = raw_data[['open', 'high', 'low', 'close', 'volume']].copy()
            df.dropna(inplace=True)
            if DataValidator.validate_dataframe(df, symbol):
                df['symbol'] = symbol.upper()
                df['source'] = 'yfinance'
                return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
''',
    "requirements.txt": '''fastapi==0.110.0
uvicorn==0.28.0
pandas==2.2.1
numpy==1.26.4
scikit-learn==1.4.1.5
pandas-ta==0.3.14b0
pydantic==2.6.4
pydantic-settings==2.2.1
sqlalchemy==2.0.28
requests==2.31.0
python-dotenv==1.0.1
loguru==0.7.2
pytest==8.1.1
yfinance==0.2.37
''',
    ".env.example": '''TRADING_MODE=PAPER
BROKER_API_KEY=your_broker_api_key_here
BROKER_ACCOUNT_ID=your_account_id_here
BROKER_ENVIRONMENT=practice
RISK_PER_TRADE_PCT=0.005
MAX_OPEN_RISK_PCT=0.02
MAX_DAILY_LOSS_PCT=0.02
MAX_WEEKLY_LOSS_PCT=0.05
MAX_DRAWDOWN_PCT=0.10
DATABASE_URL=sqlite:///./data/trading_agent.db
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
'''
}

def create_structure():
    for filepath, content in structure.items():
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created: {filepath}")
    print("\nProject structure generated successfully!")

if __name__ == "__main__":
    create_structure()