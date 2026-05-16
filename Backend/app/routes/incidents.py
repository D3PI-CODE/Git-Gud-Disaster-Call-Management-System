"""POST /incident — audio upload from web UI or Telegram bot."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.config import Settings
from app.services.pipeline import PipelineError, PipelineInput, process_incident

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "audio/ogg",
    "audio/opus",
    "audio/webm",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "application/ogg",
}

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _guess_content_type(upload: UploadFile) -> str:
    ct = (upload.content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_CONTENT_TYPES:
        return ct
    name = (upload.filename or "").lower()
    if name.endswith(".ogg"):
        return "audio/ogg"
    if name.endswith(".webm"):
        return "audio/webm"
    if name.endswith(".mp4") or name.endswith(".m4a"):
        return "audio/mp4"
    if name.endswith(".wav"):
        return "audio/wav"
    return "audio/ogg"


@router.post("/incident")
async def create_incident(
    settings: Annotated[Settings, Depends(get_settings)],
    audio: Annotated[UploadFile, File()],
    caller_name: Annotated[str, Form()] = "Unknown",
    location: Annotated[str, Form()] = "Unknown",
    source: Annotated[str, Form()] = "web",
    telegram_user_id: Annotated[str | None, Form()] = None,
):
    raw = await audio.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Audio file is empty")
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="Audio file too large (max 25 MB)")

    content_type = _guess_content_type(audio)
    filename = audio.filename or "audio.ogg"

    tg_id: int | None = None
    if telegram_user_id:
        try:
            tg_id = int(telegram_user_id)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="telegram_user_id must be an integer",
            ) from None

    src = source.strip().lower()
    if src not in ("web", "telegram", "api"):
        src = "web"

    payload = PipelineInput(
        audio_bytes=raw,
        filename=filename,
        content_type=content_type,
        caller_name=(caller_name or "Unknown").strip() or "Unknown",
        location=(location or "Unknown").strip() or "Unknown",
        source=src,
        telegram_user_id=tg_id,
    )

    try:
        saved = await process_incident(settings, payload)
    except PipelineError as exc:
        logger.warning("Pipeline failed at step=%s: %s", exc.step, exc)
        status = 502 if exc.step == "valsea" else 503
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected pipeline error")
        raise HTTPException(
            status_code=500,
            detail="Internal error processing incident",
        ) from None

    return {
        "id": saved.id,
        "priority": saved.priority,
        "caller_name": saved.caller_name,
        "location": saved.location,
        "sentiment": saved.sentiment,
        "urgency": saved.urgency,
        "stress": saved.stress,
        "frustration": saved.frustration,
        "transcript": saved.transcript,
        "action_items": saved.action_items,
        "summary": saved.summary,
        "created_at": saved.created_at,
    }
