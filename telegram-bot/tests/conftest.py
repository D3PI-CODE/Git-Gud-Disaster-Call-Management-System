"""Shared pytest fixtures for telegram-bot tests."""

import pytest


@pytest.fixture
def api_url() -> str:
    import os
    return os.getenv("API_URL", "http://localhost:8000")


@pytest.fixture
def dummy_audio_bytes() -> bytes:
    """Minimal valid WAV for smoke tests."""
    import wave
    from io import BytesIO

    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 8000)
    return buf.getvalue()
