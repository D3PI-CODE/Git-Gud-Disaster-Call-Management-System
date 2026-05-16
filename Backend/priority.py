from typing import Optional


def urgency_to_priority(
    urgency_score: Optional[float], incident_type: Optional[str] = None
) -> str:
    score = float(urgency_score or 0)
    if incident_type == "MEDICAL" or score >= 0.8:
        return "critical"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"
