"""
Gemini analysis: structured incident extraction using cleaned audio + VALSEA metrics.
"""

from __future__ import annotations

import json
import os
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Default to a current flash model; override via GEMINI_MODEL in .env
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not set in .env")


def _mime_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "ogg": "audio/ogg",
        "opus": "audio/ogg",
        "webm": "audio/webm",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "flac": "audio/flac",
    }.get(ext, "audio/ogg")


def analyze_incident(
    audio_bytes: bytes,
    filename: str,
    valsea: dict[str, Any],
    *,
    caller_name_hint: str = "",
    contact_number: str = "",
    incident_type: str = "disaster",
    location_hint: str = "",
) -> dict[str, Any]:
    """
    Send denoised/clarified context and original audio to Gemini for structured analysis.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key is not initialized.")

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        generation_config={"response_mime_type": "application/json"},
    )

    clarified = valsea.get("clarified_transcript") or valsea.get("raw_transcript") or ""
    prompt = f"""You are an emergency dispatch analyst for ResQNet (Sri Lanka disaster management).

Analyze the attached voice recording together with the VALSEA speech intelligence outputs below.
The transcript has already been denoised/clarified by VALSEA.

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

Return strict JSON with exactly these keys:
- "caller_name": string — name stated by the caller in the audio; use submitted hint only if audio confirms or is silent
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
- "incident_type": string — refine "disaster" or "medical" if the audio indicates otherwise

Prioritize life safety. Use VALSEA stress and urgency to inform priority and stress_level."""

    mime = _mime_type(filename)
    parts: list[Any] = [
        {"mime_type": mime, "data": audio_bytes},
        prompt,
    ]

    response = model.generate_content(parts)

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        print(f"Error parsing Gemini response: {exc}")
        print(f"Raw response: {response.text}")
        raise RuntimeError("Failed to parse structured JSON from Gemini response.") from exc

    return data


def extract_disaster_data(text: str) -> dict:
    """Legacy text-only extraction (kept for /api/process-audio compatibility)."""
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key is not initialized.")

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        generation_config={"response_mime_type": "application/json"},
    )

    prompt = f"""
    Analyze the following disaster call transcription and extract the information into strict JSON format.
    The JSON must contain the following keys exactly:
    - "incident_type": Must be exactly one of "MEDICAL" or "DISASTER".
    - "urgency_score": A float between 0.0 and 1.0 indicating urgency.
    - "location": An estimated location of the incident, or "Unknown" if not mentioned.
    - "stress": A float between 0.0 and 1.0 indicating caller stress level.
    - "frustration": A float between 0.0 and 1.0 indicating caller frustration.
    - "sentiment": Must be exactly one of "positive", "neutral", or "negative".
    - "action_items": A short string containing a numbered list of suggested actions.
    - "content": A concise summary of the disaster or situation.

    Transcription:
    "{text}"
    """

    response = model.generate_content(prompt)
    return json.loads(response.text)
