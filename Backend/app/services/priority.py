"""Derive incident priority from voice prosody and optional Gemini suggestion."""

from __future__ import annotations

PRIORITY_ORDER = ("low", "medium", "high", "critical")


def _clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def score_from_prosody(
    *,
    urgency: float | None,
    stress: float | None,
    frustration: float | None,
) -> float:
    """Weighted composite 0–1 from Valsea prosody emotions."""
    u = _clamp01(urgency)
    s = _clamp01(stress)
    f = _clamp01(frustration)
    return u * 0.45 + s * 0.30 + f * 0.25


def priority_from_score(score: float) -> str:
    if score >= 0.80:
        return "critical"
    if score >= 0.60:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def merge_priority(
    prosody_priority: str,
    gemini_priority: str | None,
) -> str:
    """Take the higher of prosody-derived and Gemini-suggested priority."""
    if not gemini_priority or gemini_priority not in PRIORITY_ORDER:
        return prosody_priority
    pi = PRIORITY_ORDER.index(prosody_priority)
    gi = PRIORITY_ORDER.index(gemini_priority)
    return PRIORITY_ORDER[max(pi, gi)]
