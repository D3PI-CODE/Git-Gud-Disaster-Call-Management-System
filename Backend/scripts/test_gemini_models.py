"""Quick test: try alternative Gemini models when the default hits 429."""
from __future__ import annotations

import os
import sys
import wave
from io import BytesIO
from pathlib import Path

# Add Backend/ to sys.path
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")

import google.generativeai as genai

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not set")
    sys.exit(1)

genai.configure(api_key=api_key)


def make_silent_wav(seconds: float = 1.0) -> bytes:
    buf = BytesIO()
    rate = 16000
    nframes = int(rate * seconds)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


audio_bytes = make_silent_wav(1.0)

MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

print("=== Gemini model quota probe ===\n")
for model_name in MODELS:
    print(f"  {model_name} ... ", end="", flush=True)
    try:
        model = genai.GenerativeModel(
            model_name,
            generation_config={"response_mime_type": "application/json"},
        )
        resp = model.generate_content(
            [{"mime_type": "audio/wav", "data": audio_bytes}, 'Return JSON: {"test":"ok"}']
        )
        print(f"OK  -> {resp.text[:80].strip()}")
    except Exception as exc:
        err = str(exc)
        if "429" in err or "quota" in err.lower() or "ResourceExhausted" in err:
            print("FAIL (429 quota exceeded)")
        elif "404" in err:
            print("FAIL (404 model not found)")
        elif "leaked" in err.lower() or "revoked" in err.lower():
            print("FAIL (API key revoked/leaked)")
        else:
            print(f"FAIL ({err[:120]})")

print("\nDone.")
