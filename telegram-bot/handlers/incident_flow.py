"""Conversation: caller name → location → voice → POST /incident."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, ConversationHandler

from clients.incident_api import IncidentApiError, submit_incident
from config import Settings
import messages

logger = logging.getLogger(__name__)

NAME, LOCATION, VOICE = range(3)


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def use_telegram_name_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    tg_name = context.user_data.get("telegram_name") or "Unknown"
    context.user_data["caller_name"] = tg_name
    await query.edit_message_text(
        f"✓ Caller: *{tg_name}*",
        parse_mode="Markdown",
    )
    await query.message.reply_text(
        messages.ask_location(),
        parse_mode="Markdown",
    )
    return LOCATION


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(
            messages.wrong_input_at_name(),
            parse_mode="Markdown",
        )
        return NAME

    context.user_data["caller_name"] = text
    await update.message.reply_text(
        messages.ask_location(),
        parse_mode="Markdown",
    )
    return LOCATION


async def receive_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(
            messages.wrong_input_at_location(),
            parse_mode="Markdown",
        )
        return LOCATION

    context.user_data["location"] = text
    await update.message.reply_text(
        messages.ask_voice(),
        parse_mode="Markdown",
    )
    return VOICE


async def receive_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = _settings(context)
    voice = update.message.voice

    if voice is None:
        await update.message.reply_text(
            messages.wrong_input_at_voice(),
            parse_mode="Markdown",
        )
        return VOICE

    if voice.duration and voice.duration > settings.max_voice_duration_sec:
        await update.message.reply_text(
            messages.voice_too_long(settings.max_voice_duration_sec),
            parse_mode="Markdown",
        )
        return VOICE

    caller_name = context.user_data.get("caller_name", "Unknown")
    location = context.user_data.get("location", "Unknown")

    processing_msg = await update.message.reply_text(
        messages.processing_text(),
        parse_mode="Markdown",
    )

    async def typing_loop() -> None:
        try:
            while True:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action=ChatAction.TYPING,
                )
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    async def reminder_loop() -> None:
        try:
            await asyncio.sleep(60)
            await processing_msg.edit_text(
                messages.still_processing_text(),
                parse_mode="Markdown",
            )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Could not edit processing reminder", exc_info=True)

    typing_task = asyncio.create_task(typing_loop())
    reminder_task = asyncio.create_task(reminder_loop())

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        audio_bytes = bytes(await tg_file.download_as_bytearray())

        tg_user = update.effective_user
        api_data = await submit_incident(
            api_url=settings.api_url,
            caller_name=caller_name,
            location=location,
            audio_bytes=audio_bytes,
            filename="voice.ogg",
            mime_type="audio/ogg",
            timeout_seconds=settings.request_timeout_seconds,
            source="telegram",
            telegram_user_id=tg_user.id if tg_user else None,
        )

        reply = messages.format_success(
            caller_name=caller_name,
            location=location,
            api_data=api_data,
        )
        await processing_msg.edit_text(reply, parse_mode="Markdown")
        logger.info(
            "Incident logged chat_id=%s priority=%s",
            update.effective_chat.id,
            api_data.get("priority"),
        )

    except IncidentApiError as exc:
        if exc.status_code is None and "timed out" in str(exc).lower():
            text = messages.error_timeout()
        elif exc.status_code is not None and 400 <= exc.status_code < 500:
            text = messages.error_validation(str(exc))
        else:
            text = messages.error_server()
        await processing_msg.edit_text(text, parse_mode="Markdown")
        logger.warning(
            "Incident API error chat_id=%s status=%s: %s",
            update.effective_chat.id,
            exc.status_code,
            exc,
        )

    except Exception:
        logger.exception("Unexpected error processing voice")
        await processing_msg.edit_text(
            messages.error_server(),
            parse_mode="Markdown",
        )

    finally:
        typing_task.cancel()
        reminder_task.cancel()
        context.user_data.clear()

    return ConversationHandler.END


async def wrong_input_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        messages.wrong_input_at_name(),
        parse_mode="Markdown",
    )
    return NAME


async def wrong_input_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        messages.wrong_input_at_location(),
        parse_mode="Markdown",
    )
    return LOCATION


async def wrong_input_voice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    await update.message.reply_text(
        messages.wrong_input_at_voice(),
        parse_mode="Markdown",
    )
    return VOICE
