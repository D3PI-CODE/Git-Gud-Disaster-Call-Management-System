from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from gemini import extract_disaster_data
from pipeline import process_incident_audio
from supabase_client import insert_disaster_report, supabase
from valsea import ValseaError, transcribe_audio

app = FastAPI(title="Disaster Call Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/incident")
async def create_incident(
    audio: UploadFile = File(...),
    caller_name: str = Form("Unknown"),
    contact_number: str = Form(""),
    telegram_id: str = Form(""),
    incident_type: str = Form("disaster"),
    location: str = Form(""),
):
    """
    Primary endpoint for Telegram bot and web frontend.
    Runs VALSEA → Gemini pipeline; returns structured record for DB layer.
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file.")

        filename = audio.filename or "report.ogg"
        source = "web" if location else "telegram"

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

        # Response shape expected by bot.py and AudioRecorder.jsx
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


@app.post("/api/process-audio")
async def process_audio_legacy(file: UploadFile = File(...)):
    """Legacy endpoint — text-only Gemini path after VALSEA transcription."""
    try:
        audio_bytes = await file.read()
        transcription_payload = transcribe_audio(audio_bytes, file.filename or "audio.wav")
        text = (
            transcription_payload.get("clarified_text")
            or transcription_payload.get("text")
            or ""
        )
        extracted_data = extract_disaster_data(text)
        db_response = insert_disaster_report(extracted_data)
        return {
            "status": "success",
            "message": "Audio processed and data saved successfully.",
            "data": {
                "transcription": text,
                "extracted_data": extracted_data,
                "db_response": db_response,
            },
        }
    except ValseaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/incident/status/{ref_id}")
async def get_incident_status(ref_id: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    result = (
        supabase.table("incidents")
        .select("id, priority, status, created_at")
        .ilike("id", f"{ref_id}%")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result.data[0]


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
