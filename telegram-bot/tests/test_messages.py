from messages import format_success


def test_format_success_tier_a():
    text = format_success(
        caller_name="Priya",
        location="Batticaloa",
        api_data={"priority": "high"},
    )
    assert "HIGH" in text
    assert "Priya" in text
    assert "Batticaloa" in text
    assert "dashboard" in text.lower()


def test_format_success_tier_b():
    text = format_success(
        caller_name="Priya",
        location="Batticaloa",
        api_data={
            "priority": "critical",
            "urgency": 0.87,
            "stress": 0.72,
            "frustration": 0.65,
            "sentiment": "negative",
            "transcript": "Water is rising fast.",
            "action_items": "1. Deploy medical team\n2. Alert coordinator",
        },
    )
    assert "CRITICAL" in text
    assert "87%" in text
    assert "negative" in text
    assert "Deploy medical team" in text
    assert "Water is rising" in text
