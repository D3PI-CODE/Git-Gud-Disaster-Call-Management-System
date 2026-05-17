"""
Incident audio pipeline: Telegram/web upload → VALSEA → Gemini → structured record.
Database persistence is handled separately by another service/module.
"""

from __future__ import annotations

import uuid
from typing import Any

from gemini import analyze_incident
from valsea import ValseaError, process_audio


def _normalize_priority(priority: str | None, urgency: float, stress: float) -> str:
    if priority:
        p = priority.strip().lower()
        if p in ("critical", "high", "medium", "low"):
            return p

    if urgency >= 0.75 or stress >= 0.8:
        return "critical"
    if urgency >= 0.55 or stress >= 0.6:
        return "high"
    if urgency >= 0.35 or stress >= 0.4:
        return "medium"
    return "low"


def build_structured_data(
    gemini_result: dict[str, Any],
    valsea: dict[str, Any],
    *,
    location: str,
    priority: str,
    source: str,
) -> dict[str, Any]:
    """JSONB payload for incidents.structured_data (ERD-aligned)."""
    return {
        "summary": gemini_result.get("summary", ""),
        "main_points": gemini_result.get("main_points", []),
        "location": location,
        "priority": priority,
        "sentiment": (gemini_result.get("sentiment") or valsea.get("sentiment", "neutral")).lower(),
        "tone": gemini_result.get("tone") or valsea.get("voice_tone", "neutral"),
        "stress_level": gemini_result.get("stress_level", "moderate"),
        "stress": float(gemini_result.get("stress", valsea.get("stress", 0))),
        "frustration": float(gemini_result.get("frustration", valsea.get("frustration", 0))),
        "action_items": gemini_result.get("action_items", ""),
        "language": gemini_result.get("language", ""),
        "source": source,
        "valsea": valsea,
    }


def build_incident_record(
    gemini_result: dict[str, Any],
    valsea: dict[str, Any],
    *,
    caller_name_hint: str = "",
    contact_number: str = "",
    telegram_id: str = "",
    incident_type: str = "disaster",
    source: str = "telegram",
) -> dict[str, Any]:
    """
    Shape analysis output for Supabase / incidents table (for your colleague to insert).
    Flat fields mirror the dashboard DTO; structured_data maps to incidents.structured_data.
    """
    urgency = float(gemini_result.get("urgency", valsea.get("urgency", 0)))
    stress = float(gemini_result.get("stress", valsea.get("stress", 0)))
    frustration = float(gemini_result.get("frustration", valsea.get("frustration", 0)))

    priority = _normalize_priority(gemini_result.get("priority"), urgency, stress)
    location = gemini_result.get("location") or "Unknown"
    transcript = (
        gemini_result.get("transcript")
        or valsea.get("clarified_transcript")
        or valsea.get("raw_transcript", "")
    )

    structured_data = build_structured_data(
        gemini_result,
        valsea,
        location=location,
        priority=priority,
        source=source,
    )

    return {
        "id": str(uuid.uuid4()),
        "caller_name": gemini_result.get("caller_name") or caller_name_hint or "Unknown",
        "contact_number": contact_number,
        "telegram_id": telegram_id,
        "location": location,
        "incident_type": gemini_result.get("incident_type") or incident_type,
        "priority": priority,
        "status": "open",
        "source": source,
        "summary": structured_data["summary"],
        "main_points": structured_data["main_points"],
        "transcript": transcript,
        "action_items": structured_data["action_items"],
        "sentiment": structured_data["sentiment"],
        "tone": structured_data["tone"],
        "stress_level": structured_data["stress_level"],
        "urgency": urgency,
        "urgency_score": urgency,
        "stress": stress,
        "frustration": frustration,
        "language": structured_data["language"],
        "structured_data": structured_data,
        "valsea": valsea,
        "gemini": gemini_result,
    }


def process_incident_audio(
    audio_bytes: bytes,
    filename: str = "audio.ogg",
    *,
    caller_name_hint: str = "",
    contact_number: str = "",
    telegram_id: str = "",
    incident_type: str = "disaster",
    location_hint: str = "",
    source: str = "telegram",
    language: str | None = None,
) -> dict[str, Any]:
    """
    Run VALSEA (transcribe, denoise/clarify, prosody, sentiment) then Gemini analysis.
    Returns a record ready for DB insert plus raw module outputs.
    """
    valsea_result = process_audio(audio_bytes, filename, language)
    valsea_dict = valsea_result.to_dict()

    gemini_result = analyze_incident(
        audio_bytes,
        filename,
        valsea_dict,
        caller_name_hint=caller_name_hint,
        contact_number=contact_number,
        incident_type=incident_type,
        location_hint=location_hint,
    )

    record = build_incident_record(
        gemini_result,
        valsea_dict,
        caller_name_hint=caller_name_hint,
        contact_number=contact_number,
        telegram_id=telegram_id,
        incident_type=incident_type,
        source=source,
    )

    return {
        "status": "success",
        "id": record["id"],
        "priority": record["priority"],
        "record": record,
        "valsea": valsea_dict,
        "gemini": gemini_result,
    }
