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

def insert_disaster_report(data: dict):
    if not supabase:
        raise Exception("Supabase client is not initialized.")
    try:
        response = supabase.table("disaster_reports").insert(data).execute()
        return response.data
    except Exception as e:
        print(f"Error inserting into Supabase: {e}")
        raise