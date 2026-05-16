import os
import re
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def normalize_supabase_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip().strip('"').strip("'")
    url = re.sub(r"/rest/v1/?$", "", url.rstrip("/"))
    return url


def normalize_supabase_key(key: str | None) -> str | None:
    if not key:
        return None
    return key.strip().strip('"').strip("'")


url = normalize_supabase_url(os.environ.get("SUPABASE_URL"))
key = normalize_supabase_key(os.environ.get("SUPABASE_KEY"))

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set in Backend/.env")
    supabase: Client | None = None
else:
    supabase: Client = create_client(url, key)


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
    user_id = user_response.data[0]["id"] if user_response.data else None

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


def fetch_incidents():
    if not supabase:
        return []
    try:
        response = (
            supabase.table("incidents")
            .select("*, users(name, contact_number)")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        if _table_missing_error(exc):
            print(
                "Warning: database tables missing. "
                "Run supabase_schema.sql in Supabase SQL Editor "
                "or: python Backend/setup_schema.py (with DATABASE_URL set)."
            )
            return []
        raise
