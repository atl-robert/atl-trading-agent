import os

import requests
from loguru import logger

from app.config.settings import settings


class TelegramNotifier:

    BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        settings.TELEGRAM_BOT_TOKEN,
    )

    CHAT_ID = os.getenv(
        "TELEGRAM_CHAT_ID",
        settings.TELEGRAM_CHAT_ID,
    )

    @classmethod
    def send_alert(
        cls,
        message: str,
    ) -> bool:

        if not cls.BOT_TOKEN:

            logger.warning(
                "[TELEGRAM] Bot token not configured."
            )

            return False

        if not cls.CHAT_ID:

            logger.warning(
                "[TELEGRAM] Chat ID not configured."
            )

            return False

        url = (
            "https://api.telegram.org/"
            f"bot{cls.BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": cls.CHAT_ID,
            "text": message,
        }

        try:

            response = requests.post(
                url,
                json=payload,
                timeout=10,
            )

            if response.status_code == 200:

                logger.info(
                    "[TELEGRAM] Alert sent successfully."
                )

                return True

            logger.error(
                "[TELEGRAM ERROR] "
                f"HTTP {response.status_code}: "
                f"{response.text}"
            )

            return False

        except requests.RequestException as e:

            logger.error(
                f"[TELEGRAM ERROR] Connection error: {e}"
            )

            return False