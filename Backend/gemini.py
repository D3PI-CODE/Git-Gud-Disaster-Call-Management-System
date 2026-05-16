import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not set in .env")

def extract_disaster_data(text: str) -> dict:
    """
    Uses Gemini 1.5 Flash to extract structured JSON data from text.
    """
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key is not initialized.")

    # Using response_mime_type to force JSON output
    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt = f"""
    Analyze the following disaster call transcription and extract the information into strict JSON format.
    The JSON must contain the following keys exactly:
    - "content": A concise summary of the disaster or situation.
    - "priority": The priority of the situation. Must be exactly one of "High", "Medium", or "Low".
    - "language": The language the caller was speaking.

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
