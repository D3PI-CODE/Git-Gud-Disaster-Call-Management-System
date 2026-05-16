import os
import json
from dotenv import load_dotenv
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not set in .env")

def extract_disaster_data(text: str) -> dict:
    """
    Uses Gemini 1.5 Flash to extract structured JSON data from text.
    """
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key is not initialized.")

    # Using response_mime_type to force JSON output
    model = GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt = f"""
    Analyze the following disaster call transcription and extract the information into strict JSON format.
    The JSON must contain the following keys exactly:
    - "incident_type": Must be exactly one of "MEDICAL" or "DISASTER".
    - "urgency_score": A float between 0.0 and 1.0 indicating urgency.
    - "location": An estimated location of the incident, or "Unknown" if not mentioned.
    - "stress": A float between 0.0 and 1.0 indicating caller stress level.
    - "frustration": A float between 0.0 and 1.0 indicating caller frustration.
    - "sentiment": Must be exactly one of "positive", "neutral", or "negative".
    - "action_items": A short string containing a numbered list of suggested actions.
    - "content": A concise summary of the disaster or situation.

    Transcription:
    "{text}"
    """
    
    response = model.generate_content(prompt)
    
    try:
        data = json.loads(response.text)
        return data
    except json.JSONDecodeError as e:
        print(f"Error parsing Gemini response to JSON: {e}")
        print(f"Raw response: {response.text}")
        raise Exception("Failed to parse structured JSON from Gemini response.")
