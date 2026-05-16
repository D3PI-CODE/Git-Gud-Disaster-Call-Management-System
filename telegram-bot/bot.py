import logging, os, aiohttp
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

load_dotenv()

TOKEN   = os.getenv("TELEGRAM_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Conversation states
ASK_TYPE, ASK_PHONE, ASK_VOICE = range(3)

INCIDENT_TYPES = {"1": "disaster", "2": "medical"}

PRIORITY_ICONS = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to ResQNet - Sri Lanka Disaster Management\n\n"
        "Use /report to log an emergency incident.\n"
        "Use /cancel at any time to stop."
    )

# /report - Step 1: ask incident type
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["1 - Natural disaster"], ["2 - Medical emergency"]]
    await update.message.reply_text(
        "New Incident Report\n\n"
        "What type of emergency are you reporting?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_TYPE

# Step 2: receive type, ask phone
async def received_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    key = text[0] if text and text[0] in INCIDENT_TYPES else None

    if not key:
        await update.message.reply_text("Please choose 1 or 2.")
        return ASK_TYPE

    context.user_data["incident_type"] = INCIDENT_TYPES[key]

    await update.message.reply_text(
        "Got it.\n\n"
        "Please send your phone number so an agent can follow up with you.\n"
        "Example: 0771234567",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE

# Step 3: receive phone, ask voice
async def received_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip().replace(" ", "")

    if len(phone) < 7 or not any(c.isdigit() for c in phone):
        await update.message.reply_text(
            "That doesn't look like a valid phone number. Please try again."
        )
        return ASK_PHONE

    context.user_data["phone"] = phone
    context.user_data["caller_name"] = update.effective_user.full_name or "Unknown"

    await update.message.reply_text(
        f"Phone saved: {phone}\n\n"
        "Now please send a voice message describing your situation.\n\n"
        "Hold the microphone button to record. Speak clearly - "
        "ResQNet will transcribe and analyse your report automatically."
    )
    return ASK_VOICE

# Step 4: receive voice, send to FastAPI
async def received_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice

    if not voice:
        await update.message.reply_text(
            "I didn't receive a voice message.\n"
            "Please hold the microphone button and record your message."
        )
        return ASK_VOICE

    processing = await update.message.reply_text(
        "Analysing your report... this takes about 20-30 seconds."
    )

    try:
        voice_file  = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()

        caller_name   = context.user_data.get("caller_name", "Unknown")
        phone         = context.user_data.get("phone", "")
        incident_type = context.user_data.get("incident_type", "disaster")

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field(
                "audio",
                bytes(voice_bytes),
                filename="report.ogg",
                content_type="audio/ogg"
            )
            form.add_field("caller_name",    caller_name)
            form.add_field("contact_number", phone)
            form.add_field("incident_type",  incident_type)

            async with session.post(f"{API_URL}/incident", data=form) as resp:
                if resp.status != 200:
                    raise Exception(f"Backend returned {resp.status}")
                data = await resp.json()

        priority = data.get("priority", "unknown")
        icon     = PRIORITY_ICONS.get(priority, "⚪")
        ref_id   = str(data.get("id", ""))[:8]

        await processing.edit_text(
            f"{icon} Report logged - Priority: {priority.upper()}\n\n"
            f"Your incident has been received and an agent has been notified.\n"
            f"Reference: {ref_id}\n\n"
            f"An agent may contact you at {phone}. Stay safe."
        )

    except Exception as e:
        logging.error(f"Error processing voice: {e}")
        await processing.edit_text(
            "Something went wrong processing your report.\n"
            "Please try again with /report or call emergency services on 119."
        )

    context.user_data.clear()
    return ConversationHandler.END

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Report cancelled. Use /report to start again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Fallback for unexpected messages mid-flow
async def unexpected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I was expecting a different response. Use /cancel to start over."
    )

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ResQNet Commands\n\n"
        "/report - Log a new emergency incident\n"
        "/status - Check your report status\n"
        "/cancel - Cancel current report\n"
        "/help   - Show this message\n\n"
        "For life-threatening emergencies call 119 immediately."
    )

# /status
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text(
            "Please provide your reference ID.\n"
            "Example: /status a3f9b21c"
        )
        return

    ref_id = args[0].strip()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/incident/status/{ref_id}") as resp:
                if resp.status == 404:
                    await update.message.reply_text(
                        f"No report found with ID {ref_id}.\n"
                        "Check the ID and try again."
                    )
                    return
                data = await resp.json()

        STATUS_ICONS = {
            "open":     "🟡 Open - awaiting agent",
            "assigned": "🔵 Assigned - agent responding",
            "resolved": "✅ Resolved",
        }

        priority = data.get("priority", "unknown")
        status   = data.get("status",   "unknown")

        await update.message.reply_text(
            f"Report Status\n\n"
            f"Reference: {ref_id}\n"
            f"Priority: {PRIORITY_ICONS.get(priority, '⚪')} {priority.upper()}\n"
            f"Status: {STATUS_ICONS.get(status, status)}\n"
            f"Logged at: {data.get('created_at', '')[:16].replace('T', ' ')} UTC"
        )

    except Exception as e:
        logging.error(f"Status check error: {e}")
        await update.message.reply_text("Could not fetch status. Please try again.")

# Main
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("report", report)],
        states={
            ASK_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_type)
            ],
            ASK_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_phone)
            ],
            ASK_VOICE: [
                MessageHandler(filters.VOICE, received_voice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(conv_handler)

    print("ResQNet Telegram bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()