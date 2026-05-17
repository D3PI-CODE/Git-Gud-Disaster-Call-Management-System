"""Simulate the exact bot multipart POST to /incident."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import wave
from io import BytesIO

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def make_wav(seconds: float = 0.5) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


audio_bytes = make_wav()
boundary = "ResQNetBotBoundary"

parts: list[bytes] = []
for name, value in [
    ("caller_name", "BotUser"),
    ("contact_number", "0771234567"),
    ("telegram_id", "123456789"),
    ("incident_type", "medical"),
]:
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n".encode()
    )

parts.append(
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="audio"; filename="voice.wav"\r\n'
    f"Content-Type: audio/wav\r\n\r\n".encode()
)
body = b"".join(parts) + audio_bytes + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{BASE_URL}/incident",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)

print(f"POST {BASE_URL}/incident")
print(f"Fields: caller_name=BotUser, contact_number=0771234567, telegram_id=123456789, incident_type=medical")
print(f"Audio: silent WAV ({len(audio_bytes)} bytes)\n")

try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode()
        data = json.loads(raw)
        print(f"HTTP {resp.status} OK")
        print(json.dumps(data, indent=2)[:1200])
except urllib.error.HTTPError as exc:
    body_text = exc.read().decode()[:800]
    print(f"HTTP {exc.code} {exc.reason}")
    print(f"Response body: {body_text}")
except Exception as exc:
    print(f"Connection error: {exc}")
