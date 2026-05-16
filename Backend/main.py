from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from valsea import transcribe_audio
from gemini import extract_disaster_data
from supabase_client import (
    insert_incident,
    fetch_incidents,
    fetch_incident_by_id,
    serialize_incident,
    supabase,
)
from priority import urgency_to_priority
from auth_routes import router as auth_router

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
    transcription = transcribe_audio(audio_bytes)
    extracted_data = extract_disaster_data(transcription)
    extracted_data["transcript"] = transcription
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
            "transcription": transcription,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/incident")
async def process_incident(
    audio: UploadFile = File(...),
    caller_name: str = Form("Unknown"),
    location: str = Form("Unknown"),
    authorization: Optional[str] = Header(default=None),
):
    require_agent(authorization)
    try:
        return await _process_audio_upload(audio, caller_name, location)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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

    result = (
        supabase.table("incidents")
        .select("id, urgency_score, incident_type, status, created_at")
        .ilike("id", f"{ref_id}%")
        .limit(1)
        .execute()
    )

    rows = result.data or []
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
