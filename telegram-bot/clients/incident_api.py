"""HTTP client for the ResQNet FastAPI backend."""

from __future__ import annotations

import aiohttp

from config import (
    INCIDENT_ENDPOINT,
    REQUEST_TIMEOUT_SECONDS,
    STATUS_ENDPOINT,
    TRIAGE_WEBHOOK_SECRET,
)


class BackendError(Exception):
    """Raised when the backend returns a non-200 response."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"Backend {status}: {detail}")


async def submit_incident(
    audio_bytes: bytes,
    *,
    caller_name: str,
    contact_number: str,
    telegram_id: str,
    incident_type: str,
) -> dict:
    """POST audio + metadata to /incident and return the JSON response."""
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field(
            "audio",
            audio_bytes,
            filename="report.ogg",
            content_type="audio/ogg",
        )
        form.add_field("caller_name", caller_name)
        form.add_field("contact_number", contact_number)
        form.add_field("telegram_id", telegram_id)
        form.add_field("incident_type", incident_type)

        headers = {}
        if TRIAGE_WEBHOOK_SECRET:
            headers["X-Webhook-Secret"] = TRIAGE_WEBHOOK_SECRET

        async with session.post(
            INCIDENT_ENDPOINT,
            data=form,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200:
                detail = body.get("detail", str(body)) if isinstance(body, dict) else str(body)
                raise BackendError(resp.status, detail)
            return body


async def fetch_incident_status(ref_id: str) -> dict | None:
    """GET /incident/status/{ref_id}. Returns None if 404."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{STATUS_ENDPOINT}/{ref_id}",
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 404:
                return None
            body = await resp.json(content_type=None)
            if resp.status != 200:
                detail = body.get("detail", str(body)) if isinstance(body, dict) else str(body)
                raise BackendError(resp.status, detail)
            return body
