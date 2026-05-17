"""
VALSEA API integration: transcription, clarification (denoise), prosody, sentiment.
Docs: https://valsea.ai/docs/api
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

VALSEA_API_KEY = os.getenv("VALSEA_API_KEY")
VALSEA_BASE_URL = os.getenv("VALSEA_BASE_URL", "https://api.valsea.ai").rstrip("/")
VALSEA_LANGUAGE = os.getenv("VALSEA_LANGUAGE", "english")
PROSODY_POLL_INTERVAL = float(os.getenv("VALSEA_PROSODY_POLL_INTERVAL", "1.5"))
PROSODY_POLL_TIMEOUT = float(os.getenv("VALSEA_PROSODY_POLL_TIMEOUT", "90"))


class ValseaError(Exception):
    pass


@dataclass
class ValseaAnalysis:
    """Aggregated output from VALSEA modules for downstream Gemini / DB use."""

    raw_transcript: str = ""
    clarified_transcript: str = ""
    semantic_tags: list[dict[str, Any]] = field(default_factory=list)
    detected_languages: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    sentiment_confidence: float = 0.0
    emotions: dict[str, float] = field(default_factory=dict)
    stress: float = 0.0
    urgency: float = 0.0
    frustration: float = 0.0
    politeness: float = 0.0
    hesitation: float = 0.0
    voice_tone: str = "neutral"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_transcript": self.raw_transcript,
            "clarified_transcript": self.clarified_transcript,
            "semantic_tags": self.semantic_tags,
            "detected_languages": self.detected_languages,
            "sentiment": self.sentiment,
            "sentiment_confidence": self.sentiment_confidence,
            "emotions": self.emotions,
            "stress": self.stress,
            "urgency": self.urgency,
            "frustration": self.frustration,
            "politeness": self.politeness,
            "hesitation": self.hesitation,
            "voice_tone": self.voice_tone,
        }


def _headers(json_body: bool = False) -> dict[str, str]:
    if not VALSEA_API_KEY:
        raise ValseaError("VALSEA_API_KEY is not set.")
    headers = {"Authorization": f"Bearer {VALSEA_API_KEY}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _raise_for_status(response: requests.Response, context: str) -> None:
    if response.ok:
        return
    detail = response.text[:500] if response.text else response.reason
    raise ValseaError(f"{context} failed ({response.status_code}): {detail}")


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.ogg",
    language: str | None = None,
) -> dict[str, Any]:
    """
    Transcribe audio with accent-aware correction (noise handling via enable_correction).
    Returns verbose JSON when available.
    """
    lang = language or VALSEA_LANGUAGE
    files = {"file": (filename, audio_bytes)}
    data = {
        "model": "valsea-transcribe",
        "language": lang,
        "response_format": "verbose_json",
        "enable_correction": "true",
        "enable_tags": "true",
    }
    response = requests.post(
        f"{VALSEA_BASE_URL}/v1/audio/transcriptions",
        headers=_headers(),
        files=files,
        data=data,
        timeout=120,
    )
    _raise_for_status(response, "VALSEA transcription")
    return response.json()


def denoise_transcript(text: str, language: str | None = None) -> str:
    """
    Clarify noisy / colloquial speech into clean text (VALSEA denoise equivalent).
    """
    if not text.strip():
        return text

    payload = {
        "model": "valsea-clarify",
        "text": text,
        "response_format": "json",
    }
    if language:
        payload["language"] = language

    response = requests.post(
        f"{VALSEA_BASE_URL}/v1/clarifications",
        headers=_headers(json_body=True),
        json=payload,
        timeout=60,
    )
    _raise_for_status(response, "VALSEA clarification")
    return response.json().get("clarified_text", text)


def analyze_sentiment(transcript: str, semantic_tags: list | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": "valsea-sentiment",
        "transcript": transcript,
        "response_format": "verbose_json",
    }
    if semantic_tags:
        payload["semantic_tags"] = semantic_tags

    response = requests.post(
        f"{VALSEA_BASE_URL}/v1/sentiment",
        headers=_headers(json_body=True),
        json=payload,
        timeout=60,
    )
    _raise_for_status(response, "VALSEA sentiment")
    return response.json()


def _submit_prosody_job(
    audio_bytes: bytes,
    filename: str,
    language: str | None = None,
) -> str:
    files = {"file": (filename, audio_bytes)}
    data = {
        "model": "valsea-prosody",
        "granularity": "utterance",
        "response_format": "verbose_json",
    }
    if language:
        data["language"] = language

    response = requests.post(
        f"{VALSEA_BASE_URL}/v1/prosody",
        headers=_headers(),
        files=files,
        data=data,
        timeout=60,
    )
    _raise_for_status(response, "VALSEA prosody submit")
    body = response.json()
    job_id = body.get("job_id")
    if not job_id:
        raise ValseaError("VALSEA prosody response missing job_id")
    return job_id


def _poll_prosody_job(job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + PROSODY_POLL_TIMEOUT
    status_url = f"{VALSEA_BASE_URL}/v1/prosody/{job_id}"
    result_url = f"{VALSEA_BASE_URL}/v1/prosody/{job_id}/result"

    while time.monotonic() < deadline:
        status_resp = requests.get(status_url, headers=_headers(), timeout=30)
        _raise_for_status(status_resp, "VALSEA prosody status")
        status = status_resp.json().get("status", "")

        if status == "completed":
            result_resp = requests.get(result_url, headers=_headers(), timeout=30)
            _raise_for_status(result_resp, "VALSEA prosody result")
            return result_resp.json()
        if status == "failed":
            raise ValseaError(f"VALSEA prosody job {job_id} failed")

        time.sleep(PROSODY_POLL_INTERVAL)

    raise ValseaError(f"VALSEA prosody job {job_id} timed out after {PROSODY_POLL_TIMEOUT}s")


def analyze_prosody(
    audio_bytes: bytes,
    filename: str = "audio.ogg",
    language: str | None = None,
) -> dict[str, Any]:
    lang = language or VALSEA_LANGUAGE
    job_id = _submit_prosody_job(audio_bytes, filename, lang)
    return _poll_prosody_job(job_id)


def _infer_voice_tone(emotions: dict[str, float], sentiment: str) -> str:
    if not emotions:
        return sentiment if sentiment else "neutral"

    dominant = max(emotions.items(), key=lambda item: item[1])
    label, score = dominant
    if score >= 0.55:
        return label
    if emotions.get("stress", 0) >= 0.5 or emotions.get("urgency", 0) >= 0.5:
        return "stressed"
    return sentiment if sentiment else "neutral"


def process_audio(
    audio_bytes: bytes,
    filename: str = "audio.ogg",
    language: str | None = None,
) -> ValseaAnalysis:
    """
    Full VALSEA pipeline: transcribe → clarify (denoise) → prosody → sentiment.
    """
    lang = language or VALSEA_LANGUAGE
    result = ValseaAnalysis()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tx_future = pool.submit(transcribe_audio, audio_bytes, filename, lang)
        prosody_future = pool.submit(analyze_prosody, audio_bytes, filename, lang)
        transcription = tx_future.result()
        prosody = prosody_future.result()

    result.raw_transcript = transcription.get("text") or transcription.get("raw_transcript") or ""
    result.semantic_tags = transcription.get("semantic_tags") or []
    result.detected_languages = transcription.get("detected_languages") or []

    pre_clarified = transcription.get("clarified_text") or ""
    source_for_clarify = pre_clarified or result.raw_transcript
    result.clarified_transcript = denoise_transcript(source_for_clarify, lang)
    emotions = prosody.get("emotions") or {}
    raw_emotions = {k: float(v) for k, v in emotions.items()}
    # VALSEA prosody returns emotions on a 0–10 integer scale; normalize to 0.0–1.0
    # so all downstream thresholds and LLM prompts operate on a consistent scale.
    if raw_emotions and max(raw_emotions.values()) > 1.0:
        result.emotions = {k: round(v / 10.0, 3) for k, v in raw_emotions.items()}
    else:
        result.emotions = raw_emotions
    result.stress = result.emotions.get("stress", 0.0)
    result.urgency = result.emotions.get("urgency", 0.0)
    result.frustration = result.emotions.get("frustration", 0.0)
    result.politeness = result.emotions.get("politeness", 0.0)
    result.hesitation = result.emotions.get("hesitation", 0.0)

    transcript_for_sentiment = result.clarified_transcript or result.raw_transcript
    if transcript_for_sentiment.strip():
        sentiment_data = analyze_sentiment(transcript_for_sentiment, result.semantic_tags)
        result.sentiment = sentiment_data.get("sentiment", "neutral")
        result.sentiment_confidence = float(sentiment_data.get("confidence", 0.0))

    result.voice_tone = _infer_voice_tone(result.emotions, result.sentiment)
    return result
