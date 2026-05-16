import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set in .env")
    supabase: Client = None
else:
    supabase: Client = create_client(url, key)

def insert_incident(data: dict):
    if not supabase:
        raise Exception("Supabase client is not initialized.")
    
    # We will try to fetch the default user "Unknown Caller"
    user_response = supabase.table("users").select("id").eq("telegram_id", "SYSTEM_DEFAULT").execute()
    user_id = user_response.data[0]["id"] if user_response.data else None

    # Construct the incident payload
    incident_payload = {
        "user_id": user_id,
        "incident_type": data.get("incident_type", "DISASTER"),
        "urgency_score": data.get("urgency_score", 0.5),
        "transcript": data.get("transcript", ""),
        "status": "PENDING",
        "structured_data": {
            "location": data.get("location", "Unknown"),
            "stress": data.get("stress", 0),
            "frustration": data.get("frustration", 0),
            "sentiment": data.get("sentiment", "neutral"),
            "action_items": data.get("action_items", ""),
            "content": data.get("content", "")
        }
    }

    try:
        response = supabase.table("incidents").insert(incident_payload).execute()
        return response.data
    except Exception as e:
        print(f"Error inserting into Supabase: {e}")
        raise