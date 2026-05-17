import logging
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from auth_routes import router as auth_router
from gemini import extract_disaster_data
from pipeline import process_incident_audio
from priority import urgency_to_priority
from supabase_client import (
    fetch_incident_by_id,
    fetch_incidents,
    insert_incident,
    serialize_incident,
    supabase,
)
from valsea import ValseaError, transcribe_audio

logger = logging.getLogger(__name__)

app = FastAPI(title="Disaster Call Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


def require_agent(authorization: Optional[str] = Header(default=None)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        result = supabase.auth.get_user(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid session") from e
    if not result:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = result.user
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


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
    authorization: Optional[str] = Header(default=None),
):
    require_agent(authorization)
    upload = audio or file
    if not upload:
        raise HTTPException(status_code=400, detail="Missing audio file")
    try:
        return await _process_audio_upload(upload, caller_name, location)
    except ValseaError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
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


def _persist_incident(record: dict, user_id: Optional[str]) -> Optional[str]:
    """Insert the processed incident into Supabase and return the DB-generated UUID."""
    if not supabase:
        return None

    raw_type = (record.get("incident_type") or "disaster").upper()
    db_incident_type = raw_type if raw_type in ("MEDICAL", "DISASTER") else "DISASTER"

    structured_data: dict = dict(record.get("structured_data") or {})
    structured_data.setdefault("caller_name", record.get("caller_name") or "Unknown Caller")
    structured_data.setdefault("content", structured_data.get("summary", ""))

    db_payload = {
        "user_id": user_id,
        "incident_type": db_incident_type,
        "urgency_score": float(record.get("urgency_score") or record.get("urgency") or 0),
        "transcript": record.get("transcript") or "",
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
    contact_number: str = Form(""),
    telegram_id: str = Form(""),
    incident_type: str = Form("disaster"),
    location: str = Form(""),
):
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
    authorization: Optional[str] = Header(default=None),
):
    """Live feed for the agent dashboard.

    Returns a list of incidents normalized into the exact shape the frontend's
    `IncidentCard.jsx` consumes (caller info, structured analysis, transcript,
    server-computed priority).
    """
    require_agent(authorization)
    try:
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


@app.get("/api/incidents/{incident_id}")
def get_incident(
    incident_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """Fetch a single incident by full UUID for detail views."""
    require_agent(authorization)
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
        .select("id, urgency_score, incident_type, status, created_at")
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
    return {
        **row,
        "priority": urgency_to_priority(
            urgency_score if isinstance(urgency_score, (int, float)) else None,
            incident_type if isinstance(incident_type, str) else None,
        ),
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
