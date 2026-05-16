"""HTTP client for POST /incident — mirrors the React AudioRecorder contract."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class IncidentApiError(Exception):
    """Raised when the backend returns a non-success response."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _parse_detail(body: Any) -> str:
    if not isinstance(body, dict):
        return "Unknown server error"
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict) and "msg" in first:
            return str(first["msg"])
        return str(detail[0])
    return "Unknown server error"


async def submit_incident(
    *,
    api_url: str,
    caller_name: str,
    location: str,
    audio_bytes: bytes,
    filename: str = "voice.ogg",
    mime_type: str = "audio/ogg",
    timeout_seconds: float = 120.0,
    source: str = "telegram",
    telegram_user_id: int | None = None,
) -> dict[str, Any]:
    """
    POST multipart/form-data to {api_url}/incident.

    Fields: audio, caller_name, location (same as web frontend).
    """
    url = f"{api_url.rstrip('/')}/incident"
    files = {"audio": (filename, audio_bytes, mime_type)}
    data = {
        "caller_name": caller_name or "Unknown",
        "location": location or "Unknown",
        "source": source,
    }
    if telegram_user_id is not None:
        data["telegram_user_id"] = str(telegram_user_id)

    logger.info(
        "POST %s caller=%r location=%r audio_bytes=%d",
        url,
        data["caller_name"],
        data["location"],
        len(audio_bytes),
    )

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, files=files, data=data)
    except httpx.TimeoutException as exc:
        raise IncidentApiError("Request timed out", status_code=None) from exc
    except httpx.RequestError as exc:
        raise IncidentApiError(
            f"Could not reach server: {exc}",
            status_code=None,
        ) from exc

    try:
        body = response.json()
    except ValueError:
        body = {}

    if not response.is_success:
        detail = _parse_detail(body)
        raise IncidentApiError(detail, status_code=response.status_code)

    if not isinstance(body, dict):
        return {"priority": "low"}
    return body
