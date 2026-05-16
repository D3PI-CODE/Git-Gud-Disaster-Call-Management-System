from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from valsea import transcribe_audio
from gemini import extract_disaster_data
from supabase_client import insert_disaster_report, supabase

app = FastAPI(title="Disaster Call Management System API")

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...)):
    try:
        # 1. Read audio bytes
        audio_bytes = await file.read()
        
        # 2. Transcribe using Valsea (Mocked)
        transcription = transcribe_audio(audio_bytes)
        
        # 3. Extract structured JSON using Gemini
        extracted_data = extract_disaster_data(transcription)
        
        # 4. Insert into Supabase
        db_response = insert_disaster_report(extracted_data)
        
        return {
            "status": "success",
            "message": "Audio processed and data saved successfully.",
            "data": {
                "transcription": transcription,
                "extracted_data": extracted_data,
                "db_response": db_response
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/incident/status/{ref_id}")
async def get_incident_status(ref_id: str):
    result = supabase.table("incidents") \
        .select("id, priority, status, created_at") \
        .ilike("id", f"{ref_id}%") \
        .limit(1) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    return result.data[0]

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
