import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import create_client, Client

from priority import urgency_to_priority

load_dotenv()

INCIDENT_SELECT = "*, users(name, contact_number)"
DEFAULT_FETCH_LIMIT = 200
MAX_FETCH_LIMIT = 500

ALLOWED_STATUSES = {"PENDING", "IN_PROGRESS", "RESOLVED"}
ALLOWED_INCIDENT_TYPES = {"MEDICAL", "DISASTER"}


def normalize_supabase_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip().strip('"').strip("'")
    url = re.sub(r"/rest/v1/?$", "", url.rstrip("/"))
    return url


def normalize_supabase_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return key.strip().strip('"').strip("'")


url = normalize_supabase_url(os.environ.get("SUPABASE_URL"))
key = normalize_supabase_key(os.environ.get("SUPABASE_KEY"))

supabase: Optional[Client]

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set in Backend/.env")
    supabase = None
else:
    supabase = create_client(url, key)


def insert_incident(data: dict):
    if not supabase:
        raise Exception("Supabase client is not initialized. Check Backend/.env")

    caller_name = data.get("caller_name", "Unknown Caller")
    user_response = (
        supabase.table("users")
        .select("id")
        .eq("telegram_id", "SYSTEM_DEFAULT")
        .limit(1)
        .execute()
    )
    rows = user_response.data or []
    user_id = None
    if rows and isinstance(rows[0], dict):
        raw_id = rows[0].get("id")
        user_id = raw_id if isinstance(raw_id, str) else None

    incident_payload = {
        "user_id": user_id,
        "incident_type": data.get("incident_type", "DISASTER"),
        "urgency_score": data.get("urgency_score", 0.5),
        "transcript": data.get("transcript", ""),
        "status": "PENDING",
        "structured_data": {
            "location": data.get("location", "Unknown"),
            "caller_name": caller_name,
            "stress": data.get("stress", 0),
            "frustration": data.get("frustration", 0),
            "sentiment": data.get("sentiment", "neutral"),
            "action_items": data.get("action_items", ""),
            "content": data.get("content", ""),
        },
    }

    response = supabase.table("incidents").insert(incident_payload).execute()
    return response.data


def _table_missing_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "pgrst205" in msg or "could not find the table" in msg


def _warn_tables_missing() -> None:
    print(
        "Warning: database tables missing. "
        "Run supabase_schema.sql in Supabase SQL Editor "
        "or: python Backend/setup_schema.py (with DATABASE_URL set)."
    )


def fetch_incidents(
    status: Optional[str] = None,
    incident_type: Optional[str] = None,
    limit: Optional[int] = None,
    since: Optional[str] = None,
):
    """Fetch incidents from Supabase with optional filters.

    Filters are applied server-side via PostgREST so the polling dashboard
    never has to over-fetch:
      - status:        PENDING | IN_PROGRESS | RESOLVED
      - incident_type: MEDICAL | DISASTER
      - limit:         capped at MAX_FETCH_LIMIT (defaults to DEFAULT_FETCH_LIMIT)
      - since:         ISO timestamp; returns rows with created_at > since
    """
    if not supabase:
        return []

    if status and status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    if incident_type and incident_type not in ALLOWED_INCIDENT_TYPES:
        raise ValueError(f"Invalid incident_type: {incident_type}")

    effective_limit = min(limit or DEFAULT_FETCH_LIMIT, MAX_FETCH_LIMIT)

    try:
        query = (
            supabase.table("incidents")
            .select(INCIDENT_SELECT)
            .order("created_at", desc=True)
            .limit(effective_limit)
        )
        if status:
            query = query.eq("status", status)
        if incident_type:
            query = query.eq("incident_type", incident_type)
        if since:
            query = query.gt("created_at", since)

        response = query.execute()
        return response.data or []
    except Exception as exc:
        if _table_missing_error(exc):
            _warn_tables_missing()
            return []
        raise


def fetch_incident_by_id(incident_id: str):
    """Fetch a single incident by its full UUID. Returns None when not found."""
    if not supabase:
        return None
    try:
        response = (
            supabase.table("incidents")
            .select(INCIDENT_SELECT)
            .eq("id", incident_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as exc:
        if _table_missing_error(exc):
            _warn_tables_missing()
            return None
        raise


def serialize_incident(row):
    """Normalize a raw Supabase row into the exact shape the frontend expects.

    The frontend's `IncidentCard.jsx` reads:
      id, incident_type, urgency_score, transcript, status, created_at,
      users.{name, contact_number}, structured_data.{location, stress,
      frustration, sentiment, action_items, caller_name}, priority

    This helper guarantees:
      - `structured_data` is always a dict (never null), with the keys the
        card destructures present (defaulted to safe values).
      - `users` is either a dict with `name`/`contact_number`, or null.
      - `priority` is computed server-side from urgency_score + incident_type.
    """
    if row is None:
        return None

    structured: dict[str, Any] = (row.get("structured_data") or {}).copy()
    structured.setdefault("location", "Unknown")
    structured.setdefault("caller_name", "Unknown Caller")
    structured.setdefault("stress", 0)
    structured.setdefault("frustration", 0)
    structured.setdefault("sentiment", "neutral")
    structured.setdefault("action_items", "")
    structured.setdefault("content", "")

    raw_users = row.get("users")
    users = raw_users if isinstance(raw_users, dict) else None
    urgency_score = row.get("urgency_score")
    incident_type = row.get("incident_type")

    return {
        "id": row.get("id"),
        "user_id": row.get("user_id"),
        "agent_id": row.get("agent_id"),
        "incident_type": row.get("incident_type") or "DISASTER",
        "urgency_score": row.get("urgency_score") or 0,
        "status": row.get("status") or "PENDING",
        "transcript": row.get("transcript") or "",
        "created_at": row.get("created_at"),
        "structured_data": structured,
        "users": users,
        "priority": urgency_to_priority(
            urgency_score if isinstance(urgency_score, (int, float)) else None,
            incident_type if isinstance(incident_type, str) else None,
        ),
    }
