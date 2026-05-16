import logging
import os
import aiohttp
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
MAX_VOICE_DURATION_SEC = int(os.getenv("MAX_VOICE_DURATION_SEC", "60"))

ASK_VOICE = 1

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *ResQNet Disaster Reporting Bot*\n\n"
        "If you are in danger, use /report and send one voice message.\n\n"
        "In your voice message, clearly say:\n"
        "1. Your name\n"
        "2. Your contact number\n"
        "3. Your location\n"
        "4. What happened and your current situation\n\n"
        "For life-threatening emergencies, contact emergency services immediately.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Available Commands*\n\n"
        "/start - Start the bot\n"
        "/report - Send a disaster report\n"
        "/cancel - Cancel current report\n"
        "/help - Show help message",
        parse_mode="Markdown",
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚨 *New Disaster Report*\n\n"
        "Please send *one voice message* including:\n\n"
        "1. Your name\n"
        "2. Contact number\n"
        "3. Location\n"
        "4. Current situation\n\n"
        "Example:\n"
        "_My name is Nimal. My number is 0771234567. "
        "I am near Kandy railway station. There is flooding and two people are trapped._\n\n"
        "Please record and send your voice message now.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ASK_VOICE


async def received_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice

    if not voice:
        await update.message.reply_text(
            "⚠️ I did not receive a voice message.\n"
            "Please hold the microphone button and send a voice recording."
        )
        return ASK_VOICE

    if voice.duration and voice.duration > MAX_VOICE_DURATION_SEC:
        await update.message.reply_text(
            f"⚠️ Your voice message is too long.\n"
            f"Please send a voice message under {MAX_VOICE_DURATION_SEC} seconds."
        )
        return ASK_VOICE

    processing_message = await update.message.reply_text(
        "⏳ Report received. Analysing your voice message now..."
    )

    try:
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()

        telegram_user = update.effective_user
        telegram_name = telegram_user.full_name if telegram_user else "Unknown"
        telegram_user_id = telegram_user.id if telegram_user else "Unknown"

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            form = aiohttp.FormData()

            form.add_field(
                "audio",
                bytes(voice_bytes),
                filename="telegram_voice.ogg",
                content_type="audio/ogg",
            )

            form.add_field("source", "telegram")
            form.add_field("telegram_name", str(telegram_name))
            form.add_field("telegram_user_id", str(telegram_user_id))

            async with session.post(f"{API_URL}/incident", data=form) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Backend error {response.status}: {error_text}")

                data = await response.json()

        incident_id = str(data.get("id", "N/A"))
        priority = str(data.get("priority", "unknown")).upper()
        transcript = data.get("transcript", "Transcript not available.")
        extracted_name = data.get("name", "Not detected")
        contact_number = data.get("contact_number", "Not detected")
        location = data.get("location", "Not detected")
        situation = data.get("situation", "Not detected")

        await processing_message.edit_text(
            "✅ *Disaster report submitted successfully*\n\n"
            f"*Reference ID:* `{incident_id}`\n"
            f"*Priority:* {priority}\n\n"
            f"*Name:* {extracted_name}\n"
            f"*Contact:* {contact_number}\n"
            f"*Location:* {location}\n"
            f"*Situation:* {situation}\n\n"
            f"*Transcript:*\n_{transcript}_\n\n"
            "Rescue/response team will review this report.",
            parse_mode="Markdown",
        )

    except Exception as error:
        logger.error(f"Error while processing voice report: {error}")

        await processing_message.edit_text(
            "❌ Sorry, something went wrong while processing your report.\n\n"
            "Please try again using /report.\n"
            "If this is an emergency, contact emergency services directly."
        )

    return ConversationHandler.END


async def received_wrong_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Please send a *voice message*, not text/image/video.\n\n"
        "In the voice message, say your name, contact number, location, and situation.",
        parse_mode="Markdown",
    )

    return ASK_VOICE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Report cancelled. Use /report to start again.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


def main():
    if not TOKEN:
        raise ValueError(
            "TELEGRAM_TOKEN is missing. Add it to your .env file."
        )

    app = Application.builder().token(TOKEN).build()

    report_handler = ConversationHandler(
        entry_points=[CommandHandler("report", report)],
        states={
            ASK_VOICE: [
                MessageHandler(filters.VOICE, received_voice),
                MessageHandler(~filters.VOICE, received_wrong_message),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(report_handler)

    print("ResQNet Telegram bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    