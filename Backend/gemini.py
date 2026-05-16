"""
Groq text-only LLM integration for the ResQNet incident analysis pipeline.

Drop-in replacement for the previous OpenRouter/Gemini-based implementation.
Groq is text-only — audio understanding relies entirely on VALSEA's clarified
transcript and prosody metrics. All function signatures and output keys are
identical to the original so no changes are needed elsewhere in the codebase.
"""

from __future__ import annotations

import json
import os
from typing import Any

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    print("Warning: GROQ_API_KEY not set in .env — LLM analysis will be unavailable.")
    client = None


def _parse_json_response(raw: str, source: str = "Groq") -> dict:
    """
    Safely parse JSON from a model response.
    Strips markdown fences (```json ... ```) that some models add.
    Falls back gracefully on parse errors.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error parsing {source} response: {exc}")
        print(f"Raw response: {raw}")
        raise RuntimeError(f"Failed to parse structured JSON from {source} response.") from exc


def analyze_incident(
    audio_bytes: bytes,        # accepted for API compatibility — not forwarded (text-only)
    filename: str,             # accepted for API compatibility — not forwarded
    valsea: dict[str, Any],
    *,
    caller_name_hint: str = "",
    contact_number: str = "",
    incident_type: str = "disaster",
    location_hint: str = "",
) -> dict[str, Any]:
    """
    Structured incident analysis using VALSEA transcript + voice metrics via Groq.

    audio_bytes and filename are accepted for compatibility with the previous
    implementation but are not forwarded — Groq does not support audio input.
    All audio understanding is derived from VALSEA's clarified_transcript.
    """
    if not GROQ_API_KEY or client is None:
        raise RuntimeError("GROQ_API_KEY is not configured. Add it to Backend/.env.")

    clarified = valsea.get("clarified_transcript") or valsea.get("raw_transcript") or ""

    system_prompt = (
        "You are an emergency dispatch analyst for ResQNet (Sri Lanka disaster management). "
        "You always respond with a raw JSON object only — no markdown, no code fences, no extra text."
    )

    user_prompt = f"""Analyze the incident report using the VALSEA speech intelligence outputs below.
The transcript has already been denoised and clarified by VALSEA.

Context from the reporting channel:
- Submitted caller name (may be Telegram display name): {caller_name_hint or "unknown"}
- Contact number: {contact_number or "unknown"}
- Incident type selected: {incident_type}
- Location hint from form (if any): {location_hint or "not provided"}

VALSEA voice metrics (0.0–1.0 scales):
- Stress: {valsea.get("stress", 0)}
- Urgency: {valsea.get("urgency", 0)}
- Frustration: {valsea.get("frustration", 0)}
- Politeness: {valsea.get("politeness", 0)}
- Hesitation: {valsea.get("hesitation", 0)}
- Inferred voice tone: {valsea.get("voice_tone", "neutral")}
- Text sentiment: {valsea.get("sentiment", "neutral")} (confidence {valsea.get("sentiment_confidence", 0)})

VALSEA clarified transcript:
\"\"\"{clarified}\"\"\"

Return ONLY a raw JSON object with exactly these keys:
- "caller_name": string — name stated by the caller; use submitted hint only if transcript confirms or is silent
- "location": string — place/area mentioned (city, district, landmark); "unknown" if not stated
- "main_points": array of strings — 3–6 bullet points summarizing the emergency
- "summary": string — one paragraph incident summary for dispatchers
- "stress_level": string — one of "low", "moderate", "high", "critical" derived from VALSEA stress/urgency scores
- "tone": string — caller emotional tone (use VALSEA voice_tone and sentiment)
- "priority": string — exactly one of "critical", "high", "medium", "low" for dispatch triage
- "sentiment": string — exactly one of "positive", "neutral", "negative"
- "urgency": number — 0.0 to 1.0 (align with VALSEA urgency when appropriate)
- "stress": number — 0.0 to 1.0 (align with VALSEA stress when appropriate)
- "frustration": number — 0.0 to 1.0
- "transcript": string — best transcript of what the caller said (prefer clarified text)
- "action_items": string — numbered list of recommended dispatcher actions (e.g. "1. Send ambulance\\n2. ...")
- "language": string — primary language spoken
- "incident_type": string — refine the incident type if the transcript indicates otherwise

Prioritize life safety. Use VALSEA stress and urgency to inform priority and stress_level."""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    return _parse_json_response(raw)


def extract_disaster_data(text: str) -> dict:
    """Legacy text-only extraction (kept for /api/process-audio compatibility)."""
    if not GROQ_API_KEY or client is None:
        raise RuntimeError("GROQ_API_KEY is not configured. Add it to Backend/.env.")

    system_prompt = (
        "You are a disaster call analyst. "
        "You always respond with a raw JSON object only — no markdown, no code fences, no extra text."
    )

    user_prompt = f"""Analyze the following disaster call transcription and extract information as a JSON object.
The JSON must contain exactly these keys:
- "content": A concise summary of the disaster or situation.
- "priority": The priority of the situation. Must be exactly one of "High", "Medium", or "Low".
- "language": The language the caller was speaking.

Transcription:
\"{text}\""""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    return _parse_json_response(raw)
