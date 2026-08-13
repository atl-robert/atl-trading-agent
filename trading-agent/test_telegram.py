import os
from dotenv import load_dotenv
import requests

# Force reload environment variables from .env
load_dotenv(override=True)

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

print(f"Loaded Token: {token}")
print(f"Loaded Chat ID: {chat_id}")

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": "🚀 *Test Alert*: Direct connection verified successfully!",
    "parse_mode": "Markdown"
}

response = requests.post(url, json=payload)
print("Response:", response.json())