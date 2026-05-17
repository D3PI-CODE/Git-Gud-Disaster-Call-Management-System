"""ResQNet Telegram bot entry point (structured version)."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler

from config import TELEGRAM_BOT_TOKEN
from handlers.incident_flow import build_conversation_handler
from handlers.start import check_status, help_command, start

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Add it to telegram-bot/.env or set the TELEGRAM_BOT_TOKEN environment variable."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(build_conversation_handler())

    logger.info("ResQNet Telegram bot starting (structured version)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
