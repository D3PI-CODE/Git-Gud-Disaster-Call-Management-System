import json
import os
import re
import time
from pathlib import Path
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


class ClaimError(Exception):
    """Raised by claim_incident() when the database refuses to assign a case.

    `reason` is one of:
      - "ALREADY_CLAIMED"     -> another agent won the race (HTTP 409)
      - "INCIDENT_NOT_FOUND"  -> bad incident_id (HTTP 404)
      - "AGENT_NOT_REGISTERED"-> JWT subject has no row in `agents` (HTTP 403)
      - "UNKNOWN"             -> postgres raised something we don't recognize
    """

    def __init__(self, reason: str, message: str = ""):
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


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


def fetch_agent_incidents(
    agent_id: str,
    limit: Optional[int] = None,
    since: Optional[str] = None,
):
    """Return the set of incidents visible to a specific agent.

    Visibility rule (matches the SELECT RLS policy in supabase_schema.sql):
      a) status = 'PENDING' AND agent_id IS NULL   (the claimable queue)
      b) agent_id = <this agent>                   (their active workload)

    Incidents that are IN_PROGRESS for a different agent are intentionally
    excluded — agents never see each other's in-flight work.

    The backend uses the service-role key so RLS is bypassed; we therefore
    encode the same predicate explicitly here. The PostgREST `or=...` filter
    nests an `and(...)` for the first branch so a single round-trip returns
    both buckets ordered by urgency.
    """
    if not supabase:
        return []
    if not agent_id:
        raise ValueError("agent_id is required")

    effective_limit = min(limit or DEFAULT_FETCH_LIMIT, MAX_FETCH_LIMIT)

    try:
        query = (
            supabase.table("incidents")
            .select(INCIDENT_SELECT)
            .or_(
                f"and(status.eq.PENDING,agent_id.is.null),"
                f"agent_id.eq.{agent_id}"
            )
            .order("urgency_score", desc=True)
            .order("created_at", desc=True)
            .limit(effective_limit)
        )
        if since:
            query = query.gt("created_at", since)
        response = query.execute()
        return response.data or []
    except Exception as exc:
        if _table_missing_error(exc):
            _warn_tables_missing()
            return []
        raise


_CLAIM_REASONS = {
    "ALREADY_CLAIMED",
    "INCIDENT_NOT_FOUND",
    "AGENT_NOT_REGISTERED",
}

_DEBUG_LOG_PATH = Path("/Users/d3pi/.cursor/debug-logs/debug-1a86c0.log")


def _agent_debug_log(
    location: str,
    message: str,
    data: dict,
    *,
    hypothesis_id: str = "H1",
) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "1a86c0",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass
    # #endregion


def _exception_blob(exc: Exception) -> str:
    haystacks: list[str] = [str(exc)]
    for attr in ("message", "details", "hint", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, str):
            haystacks.append(value)
    return " | ".join(haystacks).upper()


def _is_rpc_missing_error(exc: Exception) -> bool:
    blob = _exception_blob(exc)
    return "PGRST202" in blob or "COULD NOT FIND THE FUNCTION" in blob


def _parse_claim_error(exc: Exception) -> ClaimError:
    """Map an exception raised by supabase.rpc('claim_incident', ...) onto a
    typed ClaimError. supabase-py surfaces Postgres RAISE EXCEPTION messages
    through the exception's str()/`.message`/`.details` attributes depending
    on the underlying transport; we scan all of them so we are resilient to
    version drift in the client library."""
    blob = _exception_blob(exc)
    for token in _CLAIM_REASONS:
        if token in blob:
            return ClaimError(token, str(exc))
    return ClaimError("UNKNOWN", str(exc))


def _claim_incident_direct(incident_id: str, agent_id: str) -> dict:
    """Service-role conditional update when `claim_incident` RPC is not deployed.

    Uses PostgREST filters so only PENDING + unassigned rows are updated. Less
    strict than FOR UPDATE but unblocks the dashboard until the SQL function
    is applied via supabase_schema.sql.
    """
    agent_resp = (
        supabase.table("agents").select("id").eq("id", agent_id).limit(1).execute()
    )
    if not agent_resp.data:
        raise ClaimError("AGENT_NOT_REGISTERED", f"Agent {agent_id} not registered")

    response = (
        supabase.table("incidents")
        .update({"status": "IN_PROGRESS", "agent_id": agent_id})
        .eq("id", incident_id)
        .eq("status", "PENDING")
        .is_("agent_id", "null")
        .execute()
    )
    rows = response.data or []
    if rows:
        return rows[0]

    check = (
        supabase.table("incidents")
        .select("id, status, agent_id")
        .eq("id", incident_id)
        .limit(1)
        .execute()
    )
    if not check.data:
        raise ClaimError("INCIDENT_NOT_FOUND", f"Incident {incident_id} not found")

    existing = check.data[0]
    existing_status = existing.get("status")
    existing_agent = existing.get("agent_id")

    # Idempotent: same agent clicking Accept again on a case they already own.
    if (
        existing_status == "IN_PROGRESS"
        and existing_agent
        and str(existing_agent) == str(agent_id)
    ):
        _agent_debug_log(
            "supabase_client.py:_claim_incident_direct",
            "direct_claim_idempotent",
            {
                "incident_id": incident_id,
                "agent_id": agent_id,
                "status": existing_status,
            },
        )
        return fetch_incident_by_id(incident_id) or existing

    raise ClaimError("ALREADY_CLAIMED", "Incident is no longer claimable")


def claim_incident(incident_id: str, agent_id: str) -> dict:
    """Atomically assign `incident_id` to `agent_id`.

    Delegates to the `public.claim_incident(uuid, uuid)` PL/pgSQL function,
    which:
      1. Locks the target row with SELECT ... FOR UPDATE.
      2. Verifies status = 'PENDING' AND agent_id IS NULL while holding the
         lock (no TOCTOU window).
      3. Updates status -> 'IN_PROGRESS' and agent_id -> the claimant.

    If two agents race for the same case, Postgres serializes them through
    the row lock; the second transaction wakes up after the first commits,
    observes the now-claimed state, and we raise ClaimError("ALREADY_CLAIMED").
    The fastest agent always wins; nobody ever sees a partial assignment.
    """
    if not supabase:
        raise ClaimError("UNKNOWN", "Supabase client is not initialized")
    if not incident_id or not agent_id:
        raise ClaimError(
            "INCIDENT_NOT_FOUND" if not incident_id else "AGENT_NOT_REGISTERED",
            "Missing incident_id or agent_id",
        )

    try:
        response = supabase.rpc(
            "claim_incident",
            {"p_incident_id": incident_id, "p_agent_id": agent_id},
        ).execute()
    except Exception as exc:
        if _is_rpc_missing_error(exc):
            _agent_debug_log(
                "supabase_client.py:claim_incident",
                "rpc_missing_fallback_direct",
                {"incident_id": incident_id, "agent_id": agent_id},
            )
            row = _claim_incident_direct(incident_id, agent_id)
            _agent_debug_log(
                "supabase_client.py:claim_incident",
                "direct_claim_ok",
                {"incident_id": incident_id, "status": row.get("status")},
            )
            return row
        parsed = _parse_claim_error(exc)
        _agent_debug_log(
            "supabase_client.py:claim_incident",
            "rpc_claim_failed",
            {"reason": parsed.reason, "message": parsed.message[:200]},
        )
        raise parsed from exc

    rows = response.data or []
    if not rows:
        # Function returned an empty set without raising — treat as a race
        # we couldn't classify so the caller can retry safely.
        raise ClaimError("ALREADY_CLAIMED", "Claim returned no row")

    row = rows[0] if isinstance(rows, list) else rows
    if not isinstance(row, dict):
        raise ClaimError("UNKNOWN", "Unexpected claim response shape")
    return row


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
