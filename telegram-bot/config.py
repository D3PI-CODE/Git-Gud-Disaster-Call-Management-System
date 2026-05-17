"""Central configuration for the ResQNet Telegram bot."""

import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = (
    os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
)
API_URL: str = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
MAX_VOICE_DURATION_SEC: int = int(os.getenv("MAX_VOICE_DURATION_SEC", "60"))

INCIDENT_ENDPOINT = f"{API_URL}/incident"
STATUS_ENDPOINT = f"{API_URL}/incident/status"
