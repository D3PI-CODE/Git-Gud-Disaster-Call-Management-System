"""Reply templates for the ResQNet Telegram bot."""

from datetime import datetime, timezone

PRIORITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

SENTIMENT_EMOJI = {
    "positive": "😊",
    "neutral": "😐",
    "negative": "😟",
}

TRANSCRIPT_MAX_LEN = 400


def welcome_text() -> str:
    return (
        "⚡ *ResQNet Disaster Call Bot*\n\n"
        "Report an emergency by sending a voice message. "
        "Your report will be analysed and appear on the live dashboard.\n\n"
        "Use /new to log another incident, /help for instructions, /cancel to abort."
    )


def help_text() -> str:
    return (
        "*How to report an incident*\n\n"
        "1. Send the *caller name* (or tap “Use my Telegram name”)\n"
        "2. Send the *location* (city or area)\n"
        "3. Send a *voice message* describing the emergency\n\n"
        "Commands:\n"
        "/start — Welcome message\n"
        "/new — Log a new incident\n"
        "/cancel — Cancel the current report\n"
        "/help — Show this help"
    )


def ask_caller_name(telegram_name: str | None) -> str:
    hint = f"\n\nYour Telegram name: _{telegram_name}_" if telegram_name else ""
    return (
        "👤 *Step 1 of 3 — Caller name*\n\n"
        "Who is reporting this emergency? Send the caller's name as text."
        f"{hint}"
    )


def ask_location() -> str:
    return (
        "📍 *Step 2 of 3 — Location*\n\n"
        "Where is the emergency? Send the city or area as text."
    )


def ask_voice() -> str:
    return (
        "🎙 *Step 3 of 3 — Voice report*\n\n"
        "Hold the microphone button and record a *voice message* "
        "describing the emergency.\n\n"
        "_Do not send a text message or audio file — use the voice note button._"
    )


def processing_text() -> str:
    return "⏳ *Processing your emergency report…*\n\nAnalysing audio. This may take up to a minute."


def still_processing_text() -> str:
    return "⏳ Still analysing your report, please wait…"


def cancel_text() -> str:
    return "❌ Report cancelled. Send /new when you want to log another incident."


def wrong_input_at_name() -> str:
    return "Please send the *caller name* as a text message."


def wrong_input_at_location() -> str:
    return "Please send the *location* as a text message."


def wrong_input_at_voice() -> str:
    return (
        "Please send a *voice message* (hold the mic icon), not text or a file."
    )


def voice_too_long(max_sec: int) -> str:
    return f"⚠ Voice too long (max {max_sec}s). Please send a shorter voice message."


def error_validation(detail: str) -> str:
    return f"⚠ *Could not process your report*\n\n{detail}"


def error_server() -> str:
    return (
        "⚠ *Server is busy or unreachable*\n\n"
        "Please try again in a minute. If the problem persists, "
        "contact your system administrator."
    )


def error_timeout() -> str:
    return (
        "⚠ *Request timed out*\n\n"
        "Audio processing is taking longer than expected. "
        "Your report may still have been saved — check the dashboard. "
        "Otherwise, try again with a shorter voice message."
    )


def _pct(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{round(float(value) * 100)}%"


def _parse_action_items(text: str | None) -> list[str]:
    if not text:
        return []
    items = []
    for line in text.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) > 2 and line[0].isdigit() and line[1] in ".)":
            line = line[2:].strip()
        items.append(line)
    return items


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def format_success(
    *,
    caller_name: str,
    location: str,
    api_data: dict,
) -> str:
    """Build Tier A or Tier B success message from API response."""
    priority = (api_data.get("priority") or "low").lower()
    emoji = PRIORITY_EMOJI.get(priority, "⚪")
    priority_label = priority.upper()

    lines = [
        f"✅ *INCIDENT LOGGED* — {emoji} {priority_label}",
        "",
        f"👤 {caller_name}",
        f"📍 {location}",
    ]

    has_scores = any(
        api_data.get(k) is not None for k in ("urgency", "stress", "frustration")
    )
    if has_scores:
        lines.extend([
            "",
            f"📊 Urgency {_pct(api_data.get('urgency'))} · "
            f"Stress {_pct(api_data.get('stress'))} · "
            f"Frustration {_pct(api_data.get('frustration'))}",
        ])

    sentiment = api_data.get("sentiment")
    if sentiment:
        s_emoji = SENTIMENT_EMOJI.get(str(sentiment).lower(), "")
        lines.append(f"{s_emoji} Sentiment: {sentiment}")

    action_items = _parse_action_items(api_data.get("action_items"))
    if action_items:
        lines.append("")
        lines.append("📋 *Action items:*")
        for item in action_items[:8]:
            lines.append(f"• {item}")

    transcript = api_data.get("transcript")
    if transcript:
        excerpt = _truncate(str(transcript).strip(), TRANSCRIPT_MAX_LEN)
        lines.extend(["", "📝 *Transcript (excerpt):*", f"_{excerpt}_"])

    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines.extend([
        "",
        "🖥️ Your report is on the live ResQNet dashboard.",
        f"_Logged at {ts}_",
    ])

    return "\n".join(lines)
