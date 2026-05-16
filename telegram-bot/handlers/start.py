from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import messages


def _telegram_display_name(update: Update) -> str | None:
    user = update.effective_user
    if not user:
        return None
    name = user.full_name or user.first_name
    if user.username:
        name = f"{name} (@{user.username})" if name else f"@{user.username}"
    return name or None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        messages.welcome_text(),
        parse_mode="Markdown",
    )
    return await _begin_incident(update, context)


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _begin_incident(update, context)


async def _begin_incident(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.incident_flow import NAME  # noqa: PLC0415 — avoid circular import at load

    context.user_data.clear()
    tg_name = _telegram_display_name(update)
    context.user_data["telegram_name"] = tg_name

    keyboard = []
    if tg_name:
        keyboard.append([
            InlineKeyboardButton(
                "Use my Telegram name",
                callback_data="use_telegram_name",
            )
        ])
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await update.message.reply_text(
    "🚨 <b>New Incident Report</b>\n\n"
    "What type of emergency are you reporting?\n"
    "<i>Example text here</i>",
    parse_mode="HTML"
    )
    return NAME


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        messages.help_text(),
        parse_mode="Markdown",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data:
        await update.message.reply_text(
            "No active report to cancel. Send /new to log an incident.",
        )
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        messages.cancel_text(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END
