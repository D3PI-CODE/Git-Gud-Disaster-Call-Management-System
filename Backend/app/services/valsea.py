"""VALSEA API client: transcription, prosody, sentiment, formatting."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ValseaError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class TranscriptionResult:
    text: str
    clarified_text: str | None
    detected_languages: list[str]
    semantic_tags: list[dict[str, Any]] | None


@dataclass
class ProsodyResult:
    frustration: float
    stress: float
    politeness: float
    hesitation: float
    urgency: float
    job_id: str | None
    raw_predictions: list[dict[str, Any]] | None


@dataclass
class SentimentResult:
    sentiment: str
    confidence: float | None
    emotions: list[str] | None
    reasoning: str | None


class ValseaClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.valsea.ai",
        language: str = "english",
        prosody_poll_interval_sec: float = 2.0,
        prosody_max_wait_sec: float = 90.0,
        timeout: float = 120.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._language = language
        self._poll_interval = prosody_poll_interval_sec
        self._prosody_max_wait = prosody_max_wait_sec
        self._timeout = timeout

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> TranscriptionResult:
        url = f"{self._base_url}/v1/audio/transcriptions"
        data = {
            "model": "valsea-transcribe",
            "language": self._language,
            "response_format": "verbose_json",
            "enable_correction": "true",
            "enable_tags": "true",
        }
        files = {"file": (filename, audio_bytes, content_type)}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                headers=self._headers(),
                data=data,
                files=files,
            )

        if not response.is_success:
            raise ValseaError(
                f"Transcription failed: {response.text}",
                status_code=response.status_code,
            )

        body = response.json()
        text = (body.get("text") or body.get("clarified_text") or "").strip()
        if not text:
            raise ValseaError("Transcription returned empty text")

        langs = body.get("detected_languages") or []
        if isinstance(langs, str):
            langs = [langs]

        tags = body.get("semantic_tags")
        if tags is not None and not isinstance(tags, list):
            tags = None

        return TranscriptionResult(
            text=text,
            clarified_text=body.get("clarified_text"),
            detected_languages=list(langs),
            semantic_tags=tags,
        )

    async def analyze_prosody(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> ProsodyResult:
        submit_url = f"{self._base_url}/v1/prosody"
        data = {"model": "valsea-prosody"}
        files = {"file": (filename, audio_bytes, content_type)}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            submit = await client.post(
                submit_url,
                headers=self._headers(),
                data=data,
                files=files,
            )
            if submit.status_code not in (200, 202):
                raise ValseaError(
                    f"Prosody submit failed: {submit.text}",
                    status_code=submit.status_code,
                )

            body = submit.json()
            job_id = body.get("job_id")
            if not job_id:
                emotions = body.get("emotions") or {}
                return self._prosody_from_emotions(emotions, job_id=None, raw=None)

            deadline = time.monotonic() + self._prosody_max_wait
            while time.monotonic() < deadline:
                status_resp = await client.get(
                    f"{submit_url}/{job_id}",
                    headers=self._headers(),
                )
                if status_resp.status_code == 404:
                    raise ValseaError("Prosody job not found", status_code=404)

                status_body = status_resp.json()
                status = (status_body.get("status") or "").lower()

                if status == "completed":
                    result_resp = await client.get(
                        f"{submit_url}/{job_id}/result",
                        headers=self._headers(),
                    )
                    if result_resp.status_code == 409:
                        await asyncio.sleep(self._poll_interval)
                        continue
                    if not result_resp.is_success:
                        raise ValseaError(
                            f"Prosody result failed: {result_resp.text}",
                            status_code=result_resp.status_code,
                        )
                    result = result_resp.json()
                    emotions = result.get("emotions") or status_body.get("emotions") or {}
                    raw = result.get("raw_predictions")
                    return self._prosody_from_emotions(
                        emotions,
                        job_id=job_id,
                        raw=raw if isinstance(raw, list) else None,
                    )

                if status == "failed":
                    raise ValseaError("Prosody analysis job failed")

                await asyncio.sleep(self._poll_interval)

        raise ValseaError("Prosody analysis timed out")

    @staticmethod
    def _prosody_from_emotions(
        emotions: dict[str, Any],
        *,
        job_id: str | None,
        raw: list[dict[str, Any]] | None,
    ) -> ProsodyResult:
        def _f(key: str) -> float:
            try:
                return float(emotions.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0.0

        return ProsodyResult(
            frustration=_f("frustration"),
            stress=_f("stress"),
            politeness=_f("politeness"),
            hesitation=_f("hesitation"),
            urgency=_f("urgency"),
            job_id=job_id,
            raw_predictions=raw,
        )

    async def analyze_sentiment(self, transcript: str) -> SentimentResult:
        url = f"{self._base_url}/v1/sentiment"
        payload = {
            "model": "valsea-sentiment",
            "transcript": transcript,
            "response_format": "verbose_json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                headers=self._headers(json_body=True),
                json=payload,
            )

        if not response.is_success:
            raise ValseaError(
                f"Sentiment failed: {response.text}",
                status_code=response.status_code,
            )

        body = response.json()
        sentiment = (body.get("sentiment") or "neutral").lower()
        if sentiment not in ("positive", "neutral", "negative"):
            sentiment = "neutral"

        emotions = body.get("emotions")
        if emotions is not None and not isinstance(emotions, list):
            emotions = None

        confidence = body.get("confidence")
        try:
            confidence_f = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_f = None

        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence_f,
            emotions=emotions,
            reasoning=body.get("reasoning"),
        )

    async def format_action_items(self, transcript: str) -> str:
        url = f"{self._base_url}/v1/formatting"
        payload = {
            "model": "valsea-format",
            "transcript": transcript,
            "output_type": "action_items",
            "response_format": "json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                headers=self._headers(json_body=True),
                json=payload,
            )

        if not response.is_success:
            logger.warning("VALSEA formatting failed: %s", response.text)
            return ""

        body = response.json()
        for key in ("formatted_text", "text", "output", "result"):
            if body.get(key):
                return str(body[key]).strip()
        return ""
