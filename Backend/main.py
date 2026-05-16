from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from gemini import extract_disaster_data
from auth_routes import router as auth_router
from priority import urgency_to_priority
from pipeline import process_incident_audio
from supabase_client import fetch_incidents, insert_incident, supabase
from valsea import ValseaError, transcribe_audio

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
    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return result.user


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

        return {
            "id": result["id"],
            "priority": result["priority"],
            "status": "open",
            "record": result["record"],
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
def list_incidents(authorization: Optional[str] = Header(default=None)):
    require_agent(authorization)
    incidents = fetch_incidents()
    for row in incidents:
        if not row.get("priority"):
            row["priority"] = urgency_to_priority(
                row.get("urgency_score"),
                row.get("incident_type"),
            )
    return incidents


@app.get("/incident/status/{ref_id}")
async def get_incident_status(ref_id: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    result = (
        supabase.table("incidents")
        .select("id, priority, urgency_score, incident_type, status, created_at")
        .ilike("id", f"{ref_id}%")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    row = result.data[0]
    if not row.get("priority"):
        row["priority"] = urgency_to_priority(
            row.get("urgency_score"),
            row.get("incident_type"),
        )
    return row


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
