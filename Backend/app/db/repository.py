"""Persist incident pipeline results to normalized Postgres tables."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.services.gemini import GeminiExtraction
from app.services.priority import merge_priority, priority_from_score, score_from_prosody
from app.services.valsea import ProsodyResult, SentimentResult, TranscriptionResult

logger = logging.getLogger(__name__)


@dataclass
class SavedIncident:
    id: str
    priority: str
    caller_name: str
    location: str
    sentiment: str | None
    urgency: float
    stress: float
    frustration: float
    transcript: str
    action_items: str
    summary: str | None
    created_at: str


def _action_items_text(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


async def _log_step(
    conn: AsyncConnection,
    incident_id: UUID,
    step: str,
    status: str,
    *,
    detail: str | None = None,
    duration_ms: int | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO processing_logs (incident_id, step, status, detail, duration_ms)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (incident_id, step, status, detail, duration_ms),
    )


async def upsert_caller(
    conn: AsyncConnection,
    *,
    display_name: str,
    telegram_user_id: int | None,
) -> UUID | None:
    if telegram_user_id is None:
        return None

    row = await conn.execute(
        """
        INSERT INTO callers (display_name, telegram_user_id)
        VALUES (%s, %s)
        ON CONFLICT (telegram_user_id) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                updated_at = now()
        RETURNING id
        """,
        (display_name, telegram_user_id),
    )
    result = await row.fetchone()
    return result["id"] if result else None


async def save_incident_pipeline(
    conn: AsyncConnection,
    *,
    caller_name: str,
    location: str,
    source: str,
    telegram_user_id: int | None,
    transcription: TranscriptionResult,
    prosody: ProsodyResult,
    sentiment: SentimentResult,
    gemini: GeminiExtraction,
    valsea_action_items: str,
    gemini_model: str,
) -> SavedIncident:
    t0 = time.monotonic()
    caller_id = await upsert_caller(
        conn,
        display_name=caller_name,
        telegram_user_id=telegram_user_id,
    )

    prosody_score = score_from_prosody(
        urgency=prosody.urgency,
        stress=prosody.stress,
        frustration=prosody.frustration,
    )
    prosody_priority = priority_from_score(prosody_score)
    final_priority = merge_priority(prosody_priority, gemini.suggested_priority)

    action_list = gemini.action_items
    if not action_list and valsea_action_items:
        action_list = [
            line.strip()
            for line in valsea_action_items.replace("\r", "").split("\n")
            if line.strip()
        ]
    action_items_text = _action_items_text(action_list)

    transcript_text = transcription.text

    async with conn.transaction():
        row = await conn.execute(
            """
            INSERT INTO incidents (
                caller_id, caller_name, location, source, priority,
                sentiment, urgency, stress, frustration,
                transcript, action_items, summary
            )
            VALUES (%s, %s, %s, %s::incident_source, %s::priority_level,
                    %s::sentiment_label, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                caller_id,
                caller_name,
                location,
                source,
                final_priority,
                sentiment.sentiment,
                prosody.urgency,
                prosody.stress,
                prosody.frustration,
                transcript_text,
                action_items_text,
                gemini.summary or None,
            ),
        )
        incident = await row.fetchone()
        incident_id: UUID = incident["id"]

        await conn.execute(
            """
            INSERT INTO transcripts (
                incident_id, raw_text, clarified_text,
                detected_languages, semantic_tags, valsea_model
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                transcript_text,
                transcription.clarified_text,
                transcription.detected_languages or None,
                json.dumps(transcription.semantic_tags)
                if transcription.semantic_tags
                else None,
                "valsea-transcribe",
            ),
        )

        await conn.execute(
            """
            INSERT INTO voice_analyses (
                incident_id, frustration, stress, politeness,
                hesitation, urgency, valsea_job_id, raw_predictions
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                prosody.frustration,
                prosody.stress,
                prosody.politeness,
                prosody.hesitation,
                prosody.urgency,
                prosody.job_id,
                json.dumps(prosody.raw_predictions)
                if prosody.raw_predictions
                else None,
            ),
        )

        await conn.execute(
            """
            INSERT INTO sentiment_analyses (
                incident_id, sentiment, confidence, emotions, reasoning
            )
            VALUES (%s, %s::sentiment_label, %s, %s, %s)
            """,
            (
                incident_id,
                sentiment.sentiment,
                sentiment.confidence,
                sentiment.emotions,
                sentiment.reasoning,
            ),
        )

        await conn.execute(
            """
            INSERT INTO gemini_analyses (
                incident_id, model_version, summary,
                suggested_priority, raw_response
            )
            VALUES (%s, %s, %s, %s::priority_level, %s)
            """,
            (
                incident_id,
                gemini_model,
                gemini.summary,
                gemini.suggested_priority,
                json.dumps(gemini.raw_response),
            ),
        )

        for i, topic in enumerate(gemini.topics):
            await conn.execute(
                """
                INSERT INTO incident_topics (incident_id, topic, sort_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (incident_id, topic) DO NOTHING
                """,
                (incident_id, topic, i),
            )

        for i, point in enumerate(gemini.key_points):
            await conn.execute(
                """
                INSERT INTO incident_key_points (incident_id, point, sort_order)
                VALUES (%s, %s, %s)
                """,
                (incident_id, point, i),
            )

        for i, item in enumerate(action_list):
            await conn.execute(
                """
                INSERT INTO incident_action_items (incident_id, item, sort_order)
                VALUES (%s, %s, %s)
                """,
                (incident_id, item, i),
            )

        elapsed = int((time.monotonic() - t0) * 1000)
        await _log_step(
            conn,
            incident_id,
            "persist",
            "completed",
            duration_ms=elapsed,
        )

    created_at = incident["created_at"]
    if hasattr(created_at, "isoformat"):
        created_at_str = created_at.isoformat()
    else:
        created_at_str = str(created_at)

    return SavedIncident(
        id=str(incident_id),
        priority=final_priority,
        caller_name=caller_name,
        location=location,
        sentiment=sentiment.sentiment,
        urgency=prosody.urgency,
        stress=prosody.stress,
        frustration=prosody.frustration,
        transcript=transcript_text,
        action_items=action_items_text,
        summary=gemini.summary or None,
        created_at=created_at_str,
    )


async def log_pipeline_step(
    conn: AsyncConnection,
    incident_id: UUID | None,
    step: str,
    status: str,
    *,
    detail: str | None = None,
    duration_ms: int | None = None,
) -> None:
    if incident_id is None:
        return
    await _log_step(conn, incident_id, step, status, detail=detail, duration_ms=duration_ms)
