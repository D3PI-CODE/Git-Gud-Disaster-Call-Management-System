"""ResQNet Telegram bot — entry point (polling)."""

import logging
import sys

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import load_settings
from handlers import incident_flow, start
from handlers.incident_flow import LOCATION, NAME, VOICE

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    settings = load_settings()

    incident_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start.cmd_start),
            CommandHandler("new", start.cmd_new),
        ],
        states={
            NAME: [
                CallbackQueryHandler(
                    incident_flow.use_telegram_name_callback,
                    pattern="^use_telegram_name$",
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, incident_flow.receive_name),
                MessageHandler(filters.ALL & ~filters.COMMAND, incident_flow.wrong_input_name),
            ],
            LOCATION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    incident_flow.receive_location,
                ),
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    incident_flow.wrong_input_location,
                ),
            ],
            VOICE: [
                MessageHandler(filters.VOICE, incident_flow.receive_voice),
                MessageHandler(filters.ALL & ~filters.COMMAND, incident_flow.wrong_input_voice),
            ],
        },
        fallbacks=[CommandHandler("cancel", start.cmd_cancel)],
        allow_reentry=True,
    )

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    app.bot_data["settings"] = settings

    app.add_handler(incident_conversation)
    app.add_handler(CommandHandler("help", start.cmd_help))

    return app


def main() -> None:
    try:
        app = build_application()
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info("Starting ResQNet Telegram bot (polling)…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
