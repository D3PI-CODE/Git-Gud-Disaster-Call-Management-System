import logging
import os
import re
from typing import Any, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from auth_routes import router as auth_router
from gemini import extract_disaster_data
from pipeline import process_incident_audio
from priority import urgency_to_priority
from supabase_client import (
    ClaimError,
    ResolveError,
    insert_incident,
    fetch_incidents,
    fetch_agent_incidents,
    fetch_incident_by_id,
    claim_incident,
    resolve_incident,
    serialize_incident,
    supabase,
)
from priority import urgency_to_priority
from auth_routes import router as auth_router
from auth_guard import CurrentAgent, get_current_agent, resolve_agent_from_header
from valsea import ValseaError, transcribe_audio

logger = logging.getLogger(__name__)

_COMMON_SENTENCE_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "st.",
    "mt.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
    "a.m.",
    "p.m.",
}

app = FastAPI(title="Disaster Call Management System API")

# CORS: explicit allow-list so credentialed requests from Vite work.
# Note: when allow_credentials=True the wildcard "*" is invalid per spec,
# so we enumerate the dev origins. Add prod origins here when deploying.
_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "https://resqnetfrontend.vercel.app",
]
_extra = os.getenv("CORS_EXTRA_ORIGINS", "").strip()
if _extra:
    _ALLOWED_ORIGINS.extend(o.strip() for o in _extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRIAGE_WEBHOOK_SECRET = os.getenv("TRIAGE_WEBHOOK_SECRET", "").strip()

app.include_router(auth_router)


async def _process_audio_upload(
    audio: UploadFile,
    caller_name: str = "Unknown",
    location: str = "Unknown",
):
    audio_bytes = await audio.read()
    transcription_payload = transcribe_audio(audio_bytes, audio.filename or "audio.wav")
    text = (
        transcription_payload.get("clarified_text")
        or transcription_payload.get("text")
        or ""
    )
    extracted_data = extract_disaster_data(text)
    extracted_data["transcript"] = text
    extracted_data["caller_name"] = caller_name
    extracted_data["location"] = location

    db_response = insert_incident(extracted_data)
    priority = urgency_to_priority(
        extracted_data.get("urgency_score"),
        extracted_data.get("incident_type"),
    )

    return {
        "status": "success",
        "priority": priority,
        "message": "Audio processed and data saved successfully.",
        "data": {
            "transcription": text,
            "extracted_data": extracted_data,
            "db_response": db_response,
        },
    }


@app.post("/api/process-audio")
async def process_audio(
    file: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    caller_name: str = Form("Unknown"),
    location: str = Form("Unknown"),
    _agent: CurrentAgent = Depends(get_current_agent),
):
    upload = audio or file
    if not upload:
        raise HTTPException(status_code=400, detail="Missing audio file")
    try:
        return await _process_audio_upload(upload, caller_name, location)
    except ValseaError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class TriagePayload(BaseModel):
    """Webhook payload for /api/triage.

    All fields are optional so the endpoint can be called in three modes:
      1. Raw transcript only  -> Gemini fills in the structured fields.
      2. Pre-extracted metrics -> insert directly, skip Gemini.
      3. Hybrid               -> any provided fields override Gemini output.
    """

    transcript: Optional[str] = None
    caller_name: Optional[str] = Field(default="Unknown")
    location: Optional[str] = Field(default="Unknown")
    incident_type: Optional[str] = None  # "MEDICAL" | "DISASTER"
    urgency_score: Optional[float] = None
    stress: Optional[float] = None
    frustration: Optional[float] = None
    sentiment: Optional[str] = None
    action_items: Optional[str] = None
    content: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None


def _authorize_triage(
    webhook_secret: Optional[str],
    authorization: Optional[str],
) -> None:
    """Triage accepts EITHER a matching X-Webhook-Secret OR a valid agent JWT.

    If TRIAGE_WEBHOOK_SECRET is unset we run in open mode (useful for local
    dev / hackathon demos) so external services can POST without auth.
    """
    if TRIAGE_WEBHOOK_SECRET:
        if webhook_secret and webhook_secret == TRIAGE_WEBHOOK_SECRET:
            return
        # fall back to agent Bearer auth (raises 401 on failure)
        resolve_agent_from_header(authorization)
        return
    # open mode: no secret configured
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")


@app.post("/api/triage")
def triage_incident(
    payload: TriagePayload,
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    authorization: Optional[str] = Header(default=None),
):
    """Webhook entry point for the VALSEA -> Gemini -> Supabase pipeline.

    Receives a JSON body containing either a raw transcript or already-
    extracted disaster metrics, runs Gemini if needed, and inserts a new row
    into `incidents`. The Supabase Realtime publication on that table will
    then push the row to every subscribed dashboard within ~100ms.
    """
    _authorize_triage(x_webhook_secret, authorization)

    data: dict[str, Any] = payload.model_dump(exclude_none=True)

    # If the caller only sent a transcript (no urgency_score), run Gemini.
    if data.get("transcript") and data.get("urgency_score") is None:
        try:
            extracted = extract_disaster_data(data["transcript"])
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini extraction failed: {e}",
            ) from e
        # Caller-supplied fields take precedence over Gemini output.
        for key, value in extracted.items():
            data.setdefault(key, value)

    # Flatten an explicitly-provided structured_data dict (so callers can
    # send a fully-prebuilt payload from an external triage service).
    explicit_structured = data.pop("structured_data", None)
    if isinstance(explicit_structured, dict):
        for key, value in explicit_structured.items():
            data.setdefault(key, value)

    data.setdefault("transcript", data.get("content", ""))
    data.setdefault("incident_type", "DISASTER")
    data.setdefault("urgency_score", 0.5)

    try:
        db_response = insert_incident(data)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase insert failed: {e}",
        ) from e

    priority = urgency_to_priority(
        data.get("urgency_score"),
        data.get("incident_type"),
    )

    return {
        "status": "success",
        "priority": priority,
        "message": "Incident triaged and inserted; realtime listeners notified.",
        "data": {
            "extracted": data,
            "db_response": db_response,
        },
    }


@app.post("/api/triage/audio")
async def triage_audio(
    audio: UploadFile = File(...),
    caller_name: str = Form("Unknown"),
    location: str = Form("Unknown"),
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    authorization: Optional[str] = Header(default=None),
):
    """Multipart variant of /api/triage: accepts a raw audio file and runs
    the full VALSEA -> Gemini -> Supabase pipeline."""
    _authorize_triage(x_webhook_secret, authorization)
    try:
        return await _process_audio_upload(audio, caller_name, location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
def _upsert_telegram_user(telegram_id: str, name: str, contact_number: str) -> Optional[str]:
    """Upsert a Telegram caller into the users table and return their UUID."""
    if not supabase or not telegram_id:
        return None
    try:
        resp = supabase.table("users").upsert(
            {"telegram_id": telegram_id, "name": name or "Unknown", "contact_number": contact_number},
            on_conflict="telegram_id",
        ).execute()
        rows = resp.data or []
        if rows and isinstance(rows[0], dict):
            return rows[0].get("id")
    except Exception as exc:
        logger.warning("Could not upsert telegram user %s: %s", telegram_id, exc)
    return None


def _get_default_user_id() -> Optional[str]:
    """Return the UUID of the SYSTEM_DEFAULT sentinel user."""
    if not supabase:
        return None
    try:
        resp = (
            supabase.table("users")
            .select("id")
            .eq("telegram_id", "SYSTEM_DEFAULT")
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows and isinstance(rows[0], dict):
            return rows[0].get("id")
    except Exception as exc:
        logger.warning("Could not fetch SYSTEM_DEFAULT user: %s", exc)
    return None


def _extract_headline_text(text: Any) -> str:
    """Return a short headline when a safe sentence boundary exists."""
    summary = str(text or "").strip()
    if not summary:
        return ""

    parts = re.split(r"(?<=[.!?])\s+", summary)
    if len(parts) < 2:
        return summary

    first_sentence = parts[0].strip()
    last_token = first_sentence.lower().split()[-1] if first_sentence.split() else ""
    if last_token in _COMMON_SENTENCE_ABBREVIATIONS or re.search(r"\b[A-Za-z]\.$", first_sentence):
        return summary
    return first_sentence


def _persist_incident(record: dict, user_id: Optional[str]) -> Optional[str]:
    """Insert the processed incident into Supabase and return the DB-generated UUID."""
    if not supabase:
        return None

    raw_type = (record.get("incident_type") or "disaster").upper()
    db_incident_type = raw_type if raw_type in ("MEDICAL", "DISASTER") else "DISASTER"

    structured_data: dict = dict(record.get("structured_data") or {})
    structured_data.setdefault("caller_name", record.get("caller_name") or "Unknown Caller")
    # Only fall back to summary when content is genuinely absent (legacy records);
    # new records set content explicitly via build_structured_data.
    if not structured_data.get("content"):
        summary = structured_data.get("summary", "")
        structured_data["content"] = _extract_headline_text(summary)

    db_payload = {
        "user_id": user_id,
        "incident_type": db_incident_type,
        "urgency_score": float(record.get("urgency_score") or record.get("urgency") or 0),
        "transcript": record.get("transcript") or "",
        "location": record.get("location") or structured_data.get("location") or "Unknown",
        "status": "PENDING",
        "structured_data": structured_data,
    }

    try:
        db_resp = supabase.table("incidents").insert(db_payload).execute()
        rows = db_resp.data or []
        if rows and isinstance(rows[0], dict):
            return rows[0].get("id")
    except Exception as exc:
        logger.error("Supabase insert failed: %s", exc)
    return None


@app.post("/incident")
async def create_incident(
    audio: UploadFile = File(...),
    caller_name: str = Form("Unknown"),
    location: str = Form("Unknown"),
    contact_number: str = Form(""),
    telegram_id: str = Form(""),
    incident_type: str = Form("disaster"),
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    authorization: Optional[str] = Header(default=None),
):
    """Telegram / external ingest: VALSEA -> Gemini -> Supabase.

    Auth matches /api/triage: X-Webhook-Secret when TRIAGE_WEBHOOK_SECRET is set,
    else open mode for local dev (Telegram bot posts without a Bearer token).
    Agents may also call with Authorization: Bearer <jwt>.
    """
    _authorize_triage(x_webhook_secret, authorization)
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file.")

        filename = audio.filename or "report.ogg"
        source = "telegram" if telegram_id else ("web" if location else "telegram")

        result = process_incident_audio(
            audio_bytes,
            filename,
            caller_name_hint=caller_name,
            contact_number=contact_number,
            telegram_id=telegram_id,
            incident_type=incident_type,
            location_hint=location,
            source=source,
        )

        record = result["record"]

        # Persist to Supabase — this was the missing step
        user_id = (
            _upsert_telegram_user(telegram_id, caller_name, contact_number)
            if telegram_id
            else _get_default_user_id()
        )
        db_id = _persist_incident(record, user_id)
        if db_id:
            result["id"] = db_id  # Replace local uuid4 with actual DB id

        return {
            "id": result["id"],
            "priority": result["priority"],
            "status": "open",
            "record": record,
            "analysis": {
                "valsea": result["valsea"],
                "gemini": result["gemini"],
            },
        }
    except ValseaError as exc:
        raise HTTPException(status_code=502, detail=f"VALSEA processing failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/incidents")
def list_incidents(
    status: Optional[str] = Query(
        default=None,
        pattern="^(PENDING|IN_PROGRESS|RESOLVED)$",
        description="Filter by lifecycle status",
    ),
    incident_type: Optional[str] = Query(
        default=None,
        pattern="^(MEDICAL|DISASTER)$",
        description="Filter by incident type",
    ),
    limit: Optional[int] = Query(default=None, ge=1, le=500),
    since: Optional[str] = Query(
        default=None,
        description="ISO timestamp; return only incidents created after this time",
    ),
    scope: Optional[str] = Query(
        default=None,
        pattern="^(mine|all)$",
        description=(
            "'mine' -> return only PENDING+unassigned cases plus the caller's"
            " own IN_PROGRESS cases (the agent dashboard view)."
            " 'all' (default) -> unfiltered, intended for supervisors/audit."
        ),
    ),
    agent: CurrentAgent = Depends(get_current_agent),
):
    """Live feed for the agent dashboard.

    Returns a list of incidents normalized into the exact shape the frontend's
    `IncidentCard.jsx` consumes (caller info, structured analysis, transcript,
    server-computed priority).

    When `scope=mine` (the default for the agent dashboard) the response is
    constrained to:
      a) Cases that are PENDING and unassigned (claimable queue), AND
      b) Cases that are IN_PROGRESS and assigned to the JWT-resolved agent.
    Cases assigned to OTHER agents are NEVER returned in this mode.
    """
    try:
        if scope == "mine":
            rows = fetch_agent_incidents(
                agent_id=agent.agent_id,
                limit=limit,
                since=since,
            )
        else:
            rows = fetch_incidents(
                status=status,
                incident_type=incident_type,
                limit=limit,
                since=since,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return [serialize_incident(row) for row in rows]


_CLAIM_ERROR_HTTP_STATUS = {
    "ALREADY_CLAIMED": 409,
    "INCIDENT_NOT_FOUND": 404,
    "AGENT_NOT_REGISTERED": 403,
}

_RESOLVE_ERROR_HTTP_STATUS = {
    "NOT_OWNED_OR_NOT_ACTIVE": 409,
    "INCIDENT_NOT_FOUND": 404,
    "AGENT_NOT_REGISTERED": 403,
}


@app.post("/api/incidents/{incident_id}/claim")
def claim_incident_endpoint(
    incident_id: str,
    agent: CurrentAgent = Depends(get_current_agent),
):
    """Atomically assign a PENDING incident to the JWT-resolved agent.

    The `agent_id` written to `incidents.agent_id` is taken from the decoded
    JWT (never from the request body), so a client cannot impersonate another
    agent by hand-crafting the URL.

    Concurrency guarantee: this delegates to the `claim_incident()` PL/pgSQL
    function, which takes a `SELECT ... FOR UPDATE` row lock before checking
    the status / agent_id guard. If two agents POST here simultaneously for
    the same `incident_id`, Postgres serializes them through that lock:
      - The first transaction to acquire the lock flips the row to
        IN_PROGRESS and commits -> returns 200 with the updated incident.
      - The second transaction wakes up, observes the row is no longer
        PENDING+unassigned, and the function raises ALREADY_CLAIMED ->
        we return 409 here. The losing agent's dashboard then drops the
        card via the realtime UPDATE/DELETE handler.

    There is no time-of-check-to-time-of-use window: the lock is held for
    the entire status check + update, so it is impossible for two agents
    to both observe the row as claimable.

    Response shape (used by the frontend to immediately update local state
    so the agent doesn't need to refresh):
        {
          "status": "success",
          "incident": <serialized incident with status=IN_PROGRESS,
                       agent_id=<caller>>
        }
    """
    try:
        row = claim_incident(incident_id=incident_id, agent_id=agent.agent_id)
    except ClaimError as e:
        status_code = _CLAIM_ERROR_HTTP_STATUS.get(e.reason, 500)
        raise HTTPException(
            status_code=status_code,
            detail={"reason": e.reason, "message": e.message},
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Re-fetch through fetch_incident_by_id so the response includes the
    # joined `users(name, contact_number)` block and the normalized shape
    # the dashboard expects.
    enriched = fetch_incident_by_id(row.get("id")) or row
    return {
        "status": "success",
        "incident": serialize_incident(enriched),
    }


@app.post("/api/incidents/{incident_id}/resolve")
def resolve_incident_endpoint(
    incident_id: str,
    agent: CurrentAgent = Depends(get_current_agent),
):
    """Mark an IN_PROGRESS case owned by the caller as RESOLVED."""
    try:
        row = resolve_incident(incident_id=incident_id, agent_id=agent.agent_id)
    except ResolveError as e:
        status_code = _RESOLVE_ERROR_HTTP_STATUS.get(e.reason, 500)
        raise HTTPException(
            status_code=status_code,
            detail={"reason": e.reason, "message": e.message},
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    enriched = fetch_incident_by_id(row.get("id")) or row
    return {
        "status": "success",
        "incident": serialize_incident(enriched),
    }


@app.get("/api/incidents/{incident_id}")
def get_incident(
    incident_id: str,
    _agent: CurrentAgent = Depends(get_current_agent),
):
    """Fetch a single incident by full UUID for detail views."""
    try:
        row = fetch_incident_by_id(incident_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    return serialize_incident(row)


@app.get("/incident/status/{ref_id}")
async def get_incident_status(ref_id: str):
    """Public lookup used by the Telegram bot's /status command.

    Accepts a short reference (prefix of the UUID) rather than the full id.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    # PostgREST cannot pattern-match on UUID columns directly, so we fetch recent
    # incidents and do the prefix match in Python (acceptable for demo-scale data).
    result = (
        supabase.table("incidents")
        .select("id, urgency_score, incident_type, status, created_at, structured_data")
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )

    rows = [
        r for r in (result.data or [])
        if isinstance(r, dict) and str(r.get("id", "")).lower().startswith(ref_id.lower())
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="Incident not found")

    row = rows[0]
    if not isinstance(row, dict):
        raise HTTPException(status_code=404, detail="Incident not found")

    urgency_score = row.get("urgency_score")
    incident_type = row.get("incident_type")
    structured_data = row.get("structured_data") or {}

    # Prefer the priority that was computed by the full pipeline (stored in
    # structured_data.priority). Fall back to urgency_score-only derivation
    # for legacy rows that pre-date the structured pipeline.
    stored_priority = structured_data.get("priority") if isinstance(structured_data, dict) else None
    priority = (
        stored_priority
        if stored_priority in ("critical", "high", "medium", "low")
        else urgency_to_priority(
            urgency_score if isinstance(urgency_score, (int, float)) else None,
            incident_type if isinstance(incident_type, str) else None,
        )
    )
    return {
        **{key: value for key, value in row.items() if key != "structured_data"},
        "priority": priority,
    }


@app.get("/health")
def health():
    tables_ok = False
    if supabase:
        try:
            supabase.table("incidents").select("id").limit(1).execute()
            tables_ok = True
        except Exception:
            tables_ok = False
    return {"status": "ok", "supabase": bool(supabase), "tables_ready": tables_ok}


@app.get("/api/setup/status")
def setup_status():
    if not supabase:
        return {"ready": False, "message": "Supabase not configured"}
    try:
        supabase.table("incidents").select("id").limit(1).execute()
        return {"ready": True, "message": "Database schema is ready"}
    except Exception:
        return {
            "ready": False,
            "message": "Run supabase_schema.sql in Supabase Dashboard → SQL Editor",
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
