from app.services.priority import (
    merge_priority,
    priority_from_score,
    score_from_prosody,
)


def test_score_from_prosody_weighted():
    score = score_from_prosody(urgency=1.0, stress=0.0, frustration=0.0)
    assert score == 0.45


def test_priority_from_score_buckets():
    assert priority_from_score(0.85) == "critical"
    assert priority_from_score(0.65) == "high"
    assert priority_from_score(0.40) == "medium"
    assert priority_from_score(0.10) == "low"


def test_merge_priority_takes_higher():
    assert merge_priority("low", "critical") == "critical"
    assert merge_priority("high", "medium") == "high"
    assert merge_priority("medium", None) == "medium"
