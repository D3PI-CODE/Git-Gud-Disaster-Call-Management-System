"""End-to-end incident processing: VALSEA → Gemini → Postgres."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from app.config import Settings
from app.db.pool import get_connection
from app.db.repository import SavedIncident, save_incident_pipeline
from app.services.gemini import GeminiAnalyzer, GeminiError
from app.services.valsea import ValseaClient, ValseaError

logger = logging.getLogger(__name__)


@dataclass
class PipelineInput:
    audio_bytes: bytes
    filename: str
    content_type: str
    caller_name: str
    location: str
    source: str = "web"
    telegram_user_id: int | None = None


class PipelineError(Exception):
    def __init__(self, message: str, *, step: str | None = None):
        super().__init__(message)
        self.step = step


async def process_incident(settings: Settings, payload: PipelineInput) -> SavedIncident:
    valsea = ValseaClient(
        api_key=settings.valsea_api_key,
        base_url=settings.valsea_base_url,
        language=settings.valsea_language,
        prosody_poll_interval_sec=settings.valsea_prosody_poll_interval_sec,
        prosody_max_wait_sec=settings.valsea_prosody_max_wait_sec,
    )
    gemini = GeminiAnalyzer(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )

    try:
        t0 = time.monotonic()
        transcribe_task = asyncio.create_task(
            valsea.transcribe(
                payload.audio_bytes,
                filename=payload.filename,
                content_type=payload.content_type,
            )
        )
        prosody_task = asyncio.create_task(
            valsea.analyze_prosody(
                payload.audio_bytes,
                filename=payload.filename,
                content_type=payload.content_type,
            )
        )

        transcription, prosody = await asyncio.gather(transcribe_task, prosody_task)
        logger.info(
            "VALSEA transcribe+prosody done in %.1fs",
            time.monotonic() - t0,
        )

        sentiment = await valsea.analyze_sentiment(transcription.text)

        valsea_actions = await valsea.format_action_items(transcription.text)

        extraction = await gemini.extract(
            transcript=transcription.text,
            caller_name=payload.caller_name,
            location=payload.location,
            urgency=prosody.urgency,
            stress=prosody.stress,
            frustration=prosody.frustration,
            sentiment=sentiment.sentiment,
        )

    except ValseaError as exc:
        raise PipelineError(str(exc), step="valsea") from exc
    except GeminiError as exc:
        raise PipelineError(str(exc), step="gemini") from exc

    async with get_connection() as conn:
        return await save_incident_pipeline(
            conn,
            caller_name=payload.caller_name,
            location=payload.location,
            source=payload.source,
            telegram_user_id=payload.telegram_user_id,
            transcription=transcription,
            prosody=prosody,
            sentiment=sentiment,
            gemini=extraction,
            valsea_action_items=valsea_actions,
            gemini_model=settings.gemini_model,
        )
