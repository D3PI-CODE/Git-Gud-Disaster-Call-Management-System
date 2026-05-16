from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from valsea import transcribe_audio
from gemini import extract_disaster_data
from supabase_client import insert_incident, fetch_incidents, supabase
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
    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return result.user


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
def list_incidents(authorization: Optional[str] = Header(default=None)):
    require_agent(authorization)
    incidents = fetch_incidents()
    for row in incidents:
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
        .select("id, urgency_score, incident_type, status, created_at")
        .ilike("id", f"{ref_id}%")
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    row = result.data[0]
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
