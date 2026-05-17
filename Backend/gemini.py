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

from dotenv import load_dotenv
from groq import Groq

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


def _require_client() -> Groq:
    if not GROQ_API_KEY or client is None:
        raise RuntimeError("GROQ_API_KEY is not configured. Add it to Backend/.env.")
    return client


def analyze_incident(
    _audio_bytes: bytes,  # accepted for API compatibility — not forwarded (text-only)
    _filename: str,  # accepted for API compatibility — not forwarded
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
    groq_client = _require_client()

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

VALSEA voice metrics (all on 0.0–1.0 scale — already normalised):
- Stress:      {valsea.get("stress", 0):.3f}  (vocal stress / physical tension in voice)
- Urgency:     {valsea.get("urgency", 0):.3f}  (perceived urgency in speech prosody)
- Frustration: {valsea.get("frustration", 0):.3f}
- Politeness:  {valsea.get("politeness", 0):.3f}
- Hesitation:  {valsea.get("hesitation", 0):.3f}
- Inferred voice tone: {valsea.get("voice_tone", "neutral")}
- Text sentiment: {valsea.get("sentiment", "neutral")} (confidence {valsea.get("sentiment_confidence", 0):.2f})

VALSEA clarified transcript:
\"\"\"{clarified}\"\"\"

Return ONLY a raw JSON object with exactly these keys:
- "caller_name": string — name stated by the caller; use submitted hint only if transcript confirms or is silent
- "location": string — place/area mentioned (city, district, landmark); "unknown" if not stated
- "main_points": array of strings — 3–6 bullet points summarizing the emergency
- "content": string — one concise sentence (max 20 words) capturing the core incident type and location, suitable for list views and push notifications
- "summary": string — one full paragraph incident summary for dispatchers, including context, severity indicators, and caller details
- "stress_level": string — one of "low", "moderate", "high", "critical" based on VALSEA metrics and transcript severity
- "tone": string — single precise emotional tone word describing the caller (choose from: panicked, frantic, distressed, fearful, anxious, worried, upset, frustrated, confused, urgent, calm, neutral — pick the best match)
- "priority": string — exactly one of "critical", "high", "medium", "low" for dispatch triage
- "sentiment": string — exactly one of "positive", "neutral", "negative"
- "urgency": number — 0.0 to 1.0; MUST synthesize three signals:
    1. VALSEA urgency ({valsea.get("urgency", 0):.3f}) and stress ({valsea.get("stress", 0):.3f}) — use as baseline
    2. Caller vocal tone: panicked/screaming=0.85–1.0; distressed/frantic=0.65–0.84; anxious/worried=0.40–0.64; calm/neutral=0.10–0.39
    3. Transcript incident severity: deaths/casualties/building collapse/drowning=+0.15; active fire/flooding/medical emergency=+0.10; property damage=+0.05; informational=0
    Add signals together and clamp to [0.05, 0.98]. Return a SPECIFIC decimal like 0.73, never exactly 0.0 or 1.0.
- "stress": number — 0.0 to 1.0; start from VALSEA stress ({valsea.get("stress", 0):.3f}), adjust slightly for vocal distress cues; return a specific decimal like 0.61
- "frustration": number — 0.0 to 1.0; start from VALSEA frustration ({valsea.get("frustration", 0):.3f}); return a specific decimal
- "transcript": string — best transcript of what the caller said (prefer clarified text)
- "action_items": string — numbered list of recommended dispatcher actions (e.g. "1. Send ambulance\\n2. ...")
- "language": string — primary language spoken
- "incident_type": string — refine the incident type if the transcript clearly indicates otherwise

Prioritize life safety. urgency, stress, and frustration MUST be specific non-zero decimals that reflect the actual severity — do NOT default to 0."""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    return _parse_json_response(raw)


def extract_disaster_data(text: str) -> dict:
    """Legacy text-only extraction (kept for /api/process-audio compatibility)."""
    groq_client = _require_client()

    system_prompt = (
        "You are an emergency incident parser. "
        "Return only raw JSON with no markdown or extra text."
    )
    user_prompt = f"""Analyze the following disaster call transcription and extract strict JSON.
Return ONLY a JSON object with exactly these keys:
- "incident_type": exactly one of "MEDICAL" or "DISASTER"
- "urgency_score": number from 0.0 to 1.0
- "location": string, or "Unknown" if absent
- "stress": number from 0.0 to 1.0
- "frustration": number from 0.0 to 1.0
- "sentiment": exactly one of "positive", "neutral", "negative"
- "action_items": string containing a numbered list of suggested actions
- "content": concise summary of the incident

Transcription:
"{text}"
"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    return _parse_json_response(raw)
