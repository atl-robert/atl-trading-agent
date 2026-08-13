import ccxt
import os
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# Initialize CCXT Binance instance
exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
})

# Switch to Binance Sandbox / Testnet mode
exchange.set_sandbox_mode(True)

try:
    print("Testing connection to Binance Testnet...")
    
    # Fetch live ticker data for BTC/USDT
    ticker = exchange.fetch_ticker('BTC/USDT')
    print("Successfully connected to market data stream!")
    print(f"Current Testnet BTC/USDT Price: ${ticker['last']}")
    
    # Fetch testnet wallet balances
    balance = exchange.fetch_balance()
    print("Successfully authenticated and fetched testnet account balance!")
    print(f"USDT Balance: {balance['free'].get('USDT', 0.0)}")

except Exception as e:
    print(f"Connection or authentication failed: {e}")