"""Live integration tests — require a running backend at API_URL."""

import json
import sys
import os
import wave
from io import BytesIO

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import API_URL


def _make_wav(seconds: float = 0.5) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


@pytest.fixture
def backend_available() -> bool:
    """Skip tests if the backend is not reachable."""
    try:
        import urllib.request
        urllib.request.urlopen(f"{API_URL}/health", timeout=5)
        return True
    except Exception:
        return False


def test_health_endpoint(backend_available):
    if not backend_available:
        pytest.skip("Backend not running at " + API_URL)

    import urllib.request
    with urllib.request.urlopen(f"{API_URL}/health", timeout=10) as resp:
        data = json.loads(resp.read().decode())
    assert data["status"] == "ok", f"Unexpected health response: {data}"


def test_incident_endpoint_reachable(backend_available):
    """Smoke test: POST to /incident and verify we get a structured response.

    Uses a silent WAV so VALSEA/Gemini may return minimal data, but the
    endpoint itself must be reachable and return HTTP 200.
    """
    if not backend_available:
        pytest.skip("Backend not running at " + API_URL)

    import urllib.request
    import urllib.error

    audio_bytes = _make_wav(0.5)
    boundary = "ResQNetTestBoundary"

    parts: list[bytes] = []
    for name, value in [
        ("caller_name", "IntegrationTest"),
        ("contact_number", "0770000000"),
        ("telegram_id", "test_integration_000"),
        ("incident_type", "disaster"),
    ]:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )

    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="test.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n".encode()
    )
    body = b"".join(parts) + audio_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{API_URL}/incident",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
        assert "id" in data, "Response missing 'id' field"
        assert "priority" in data, "Response missing 'priority' field"
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()[:500]
        pytest.fail(f"HTTP {exc.code}: {body_text}")
