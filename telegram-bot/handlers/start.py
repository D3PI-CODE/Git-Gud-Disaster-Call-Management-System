"""Handlers for /start, /help, and /status commands."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from clients.incident_api import BackendError, fetch_incident_status
from messages import (
    HELP,
    PRIORITY_ICONS,
    STATUS_ERROR,
    STATUS_LABELS,
    STATUS_MISSING_ID,
    STATUS_NOT_FOUND,
    STATUS_REPORT,
    WELCOME,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP, parse_mode="Markdown")


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []

    if not args:
        await update.message.reply_text(STATUS_MISSING_ID, parse_mode="Markdown")
        return

    ref_id = args[0].strip()

    try:
        data = await fetch_incident_status(ref_id)
    except BackendError as exc:
        logger.error("Status check backend error for %s: %s", ref_id, exc)
        await update.message.reply_text(STATUS_ERROR)
        return
    except Exception as exc:
        logger.error("Status check error for %s: %s", ref_id, exc)
        await update.message.reply_text(STATUS_ERROR)
        return

    if data is None:
        await update.message.reply_text(
            STATUS_NOT_FOUND.format(ref_id=ref_id), parse_mode="Markdown"
        )
        return

    priority = data.get("priority", "unknown")
    status = data.get("status", "unknown")
    created_at = (data.get("created_at") or "")[:16].replace("T", " ")

    await update.message.reply_text(
        STATUS_REPORT.format(
            ref_id=ref_id,
            priority_icon=PRIORITY_ICONS.get(priority, "⚪"),
            priority=priority.upper(),
            status_label=STATUS_LABELS.get(status, status),
            created_at=created_at,
        ),
        parse_mode="Markdown",
    )
