"""
Optional live integration test — skipped unless RUN_INTEGRATION=1 and API_URL is reachable.

Does not require Telegram; posts a minimal payload to POST /incident.
"""

import os

import httpx
import pytest

from clients.incident_api import submit_incident


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 and API_URL to run live backend test",
)
async def test_live_incident_endpoint():
    api_url = os.getenv("API_URL", "http://localhost:8000")
    # Minimal OGG-like bytes; backend may reject — we only verify reachability
    try:
        await submit_incident(
            api_url=api_url,
            caller_name="Integration Test",
            location="Test",
            audio_bytes=b"\x00" * 100,
            timeout_seconds=10.0,
        )
    except Exception as exc:
        # Backend reachable but validation error is acceptable for smoke test
        if "Could not reach server" in str(exc):
            pytest.fail(f"Backend not reachable at {api_url}: {exc}")
