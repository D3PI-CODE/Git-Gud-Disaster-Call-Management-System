import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    api_url: str
    request_timeout_seconds: float
    max_voice_duration_sec: int


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        api_url=_require("API_URL").rstrip("/"),
        request_timeout_seconds=float(
            os.getenv("REQUEST_TIMEOUT_SECONDS", "120")
        ),
        max_voice_duration_sec=int(os.getenv("MAX_VOICE_DURATION_SEC", "60")),
    )
