"""ConversationHandler for the /report incident-reporting flow."""

import logging

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from clients.incident_api import BackendError, submit_incident
from config import MAX_VOICE_DURATION_SEC
from messages import (
    ASK_INCIDENT_TYPE,
    ASK_PHONE,
    ASK_VOICE,
    CANCELLED,
    INVALID_PHONE,
    INVALID_TYPE,
    NOT_A_VOICE,
    PRIORITY_ICONS,
    PROCESSING,
    REPORT_ERROR,
    REPORT_SUCCESS,
    UNEXPECTED_INPUT,
)

logger = logging.getLogger(__name__)

ASK_TYPE, ASK_PHONE_STATE, ASK_VOICE_STATE = range(3)

INCIDENT_TYPES = {"1": "disaster", "2": "medical"}


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["1 — Natural disaster"], ["2 — Medical emergency"]]
    await update.message.reply_text(
        ASK_INCIDENT_TYPE,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return ASK_TYPE


async def received_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    key = text[0] if text and text[0] in INCIDENT_TYPES else None

    if not key:
        await update.message.reply_text(INVALID_TYPE, parse_mode="Markdown")
        return ASK_TYPE

    context.user_data["incident_type"] = INCIDENT_TYPES[key]
    await update.message.reply_text(
        ASK_PHONE, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    return ASK_PHONE_STATE


async def received_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip().replace(" ", "")

    if len(phone) < 7 or not any(c.isdigit() for c in phone):
        await update.message.reply_text(INVALID_PHONE)
        return ASK_PHONE_STATE

    context.user_data["phone"] = phone
    context.user_data["caller_name"] = update.effective_user.full_name or "Unknown"

    await update.message.reply_text(
        ASK_VOICE.format(phone=phone), parse_mode="Markdown"
    )
    return ASK_VOICE_STATE


async def received_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    voice = update.message.voice

    if not voice:
        await update.message.reply_text(NOT_A_VOICE)
        return ASK_VOICE_STATE

    if voice.duration and voice.duration > MAX_VOICE_DURATION_SEC:
        await update.message.reply_text(
            f"⚠️ Voice message too long (max {MAX_VOICE_DURATION_SEC}s). Please record a shorter message."
        )
        return ASK_VOICE_STATE

    processing = await update.message.reply_text(PROCESSING)

    try:
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = bytes(await voice_file.download_as_bytearray())

        caller_name = context.user_data.get("caller_name", "Unknown")
        phone = context.user_data.get("phone", "")
        incident_type = context.user_data.get("incident_type", "disaster")

        data = await submit_incident(
            voice_bytes,
            caller_name=caller_name,
            contact_number=phone,
            telegram_id=str(update.effective_user.id),
            incident_type=incident_type,
        )

        priority = data.get("priority", "unknown")
        icon = PRIORITY_ICONS.get(priority, "⚪")
        ref_id = str(data.get("id", ""))[:8]

        await processing.edit_text(
            REPORT_SUCCESS.format(
                icon=icon, priority=priority.upper(), ref_id=ref_id, phone=phone
            ),
            parse_mode="Markdown",
        )

    except BackendError as exc:
        logger.error("Backend error during voice processing: %s", exc)
        await processing.edit_text(REPORT_ERROR)
    except Exception as exc:
        logger.error("Unexpected error processing voice: %s", exc)
        await processing.edit_text(REPORT_ERROR)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(CANCELLED, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def unexpected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(UNEXPECTED_INPUT)
    return ASK_VOICE_STATE


def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("report", report)],
        states={
            ASK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_type)],
            ASK_PHONE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_phone)],
            ASK_VOICE_STATE: [
                MessageHandler(filters.VOICE, received_voice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
