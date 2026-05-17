"""User-facing message templates for ResQNet."""

WELCOME = (
    "👋 Welcome to *ResQNet* — Sri Lanka Disaster Management\n\n"
    "Use /report to log an emergency incident.\n"
    "Use /cancel at any time to stop."
)

HELP = (
    "📋 *ResQNet Commands*\n\n"
    "/report — Log a new emergency incident\n"
    "/status <ref> — Check your report status\n"
    "/cancel — Cancel current report\n"
    "/help — Show this message\n\n"
    "_For life-threatening emergencies call 119 immediately._"
)

ASK_INCIDENT_TYPE = (
    "🚨 *New Incident Report*\n\n"
    "What type of emergency are you reporting?"
)

INVALID_TYPE = "Please choose *1* or *2*."

ASK_PHONE = (
    "✅ Got it.\n\n"
    "Please send your *phone number* so an agent can follow up with you.\n"
    "_Example: 0771234567_"
)

INVALID_PHONE = "⚠️ That doesn't look like a valid phone number. Please try again."

ASK_VOICE = (
    "📞 Phone saved: `{phone}`\n\n"
    "Now please *send a voice message* describing your situation.\n\n"
    "_Hold the 🎤 microphone button to record. Speak clearly — "
    "ResQNet will transcribe and analyse your report automatically._"
)

NOT_A_VOICE = (
    "⚠️ I didn't receive a voice message.\n"
    "Please hold the 🎤 button and record your message."
)

PROCESSING = "⏳ Analysing your report... this takes about 20–30 seconds."

REPORT_SUCCESS = (
    "{icon} *Report logged — Priority: {priority}*\n\n"
    "Your incident has been received and an agent has been notified.\n"
    "Reference: `{ref_id}`\n\n"
    "An agent may contact you at `{phone}`. Stay safe. 🙏"
)

REPORT_ERROR = (
    "❌ Something went wrong processing your report.\n"
    "Please try again with /report or call emergency services directly."
)

CANCELLED = "Report cancelled. Use /report to start again."

UNEXPECTED_INPUT = "I was expecting a different response. Use /cancel to start over."

STATUS_NOT_FOUND = (
    "⚠️ No report found with ID `{ref_id}`.\n"
    "Check the ID and try again."
)

STATUS_MISSING_ID = (
    "Please provide your reference ID.\n"
    "_Example: /status a3f9b21c_"
)

STATUS_REPORT = (
    "📋 *Report Status*\n\n"
    "Reference: `{ref_id}`\n"
    "Priority: {priority_icon} {priority}\n"
    "Status: {status_label}\n"
    "Logged at: {created_at} UTC"
)

STATUS_ERROR = "❌ Could not fetch status. Please try again."

PRIORITY_ICONS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

STATUS_LABELS = {
    "open": "🟡 Open — awaiting agent",
    "PENDING": "🟡 Open — awaiting agent",
    "assigned": "🔵 Assigned — agent responding",
    "IN_PROGRESS": "🔵 Assigned — agent responding",
    "resolved": "✅ Resolved",
    "RESOLVED": "✅ Resolved",
}
