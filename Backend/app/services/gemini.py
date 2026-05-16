"""Google Gemini — structured incident extraction from transcript + context."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    pass


@dataclass
class GeminiExtraction:
    summary: str
    topics: list[str]
    key_points: list[str]
    action_items: list[str]
    suggested_priority: str | None
    raw_response: dict[str, Any]


_PROMPT_TEMPLATE = """You are an emergency dispatch analyst for a disaster call management system.

Analyze this emergency voice report and return ONLY valid JSON (no markdown fences) with this exact shape:
{{
  "summary": "2-3 sentence incident summary",
  "topics": ["topic1", "topic2"],
  "key_points": ["main fact 1", "main fact 2"],
  "action_items": ["immediate action 1", "immediate action 2"],
  "suggested_priority": "critical|high|medium|low"
}}

Caller: {caller_name}
Location: {location}
Transcript:
{transcript}

Voice tone scores (0-1): urgency={urgency:.2f}, stress={stress:.2f}, frustration={frustration:.2f}
Sentiment: {sentiment}

Rules:
- topics: 2-5 short labels (e.g. "flood", "medical", "evacuation")
- key_points: 3-6 factual bullets from the call
- action_items: concrete dispatch steps for responders
- suggested_priority: weigh life threat, scale, and voice urgency
"""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


class GeminiAnalyzer:
    def __init__(self, *, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name)
        self._model_name = model_name

    async def extract(
        self,
        *,
        transcript: str,
        caller_name: str,
        location: str,
        urgency: float,
        stress: float,
        frustration: float,
        sentiment: str,
    ) -> GeminiExtraction:
        prompt = _PROMPT_TEMPLATE.format(
            caller_name=caller_name,
            location=location,
            transcript=transcript,
            urgency=urgency,
            stress=stress,
            frustration=frustration,
            sentiment=sentiment,
        )

        try:
            response = await self._model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            raise GeminiError(f"Gemini request failed: {exc}") from exc

        raw_text = (response.text or "").strip()
        if not raw_text:
            raise GeminiError("Gemini returned empty response")

        try:
            data = json.loads(_strip_json_fence(raw_text))
        except json.JSONDecodeError as exc:
            raise GeminiError(f"Invalid JSON from Gemini: {raw_text[:200]}") from exc

        priority = (data.get("suggested_priority") or "").lower().strip()
        if priority not in ("critical", "high", "medium", "low"):
            priority = None

        def _str_list(key: str) -> list[str]:
            val = data.get(key) or []
            if not isinstance(val, list):
                return []
            return [str(x).strip() for x in val if str(x).strip()]

        return GeminiExtraction(
            summary=str(data.get("summary") or "").strip(),
            topics=_str_list("topics"),
            key_points=_str_list("key_points"),
            action_items=_str_list("action_items"),
            suggested_priority=priority,
            raw_response=data,
        )
