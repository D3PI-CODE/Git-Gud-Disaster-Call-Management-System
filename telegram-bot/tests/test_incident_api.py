"""Unit tests for multipart field contract (no live backend required)."""

import pytest
import httpx
import respx

from clients.incident_api import IncidentApiError, submit_incident


@pytest.mark.asyncio
@respx.mock
async def test_submit_incident_multipart_fields():
    route = respx.post("http://localhost:8000/incident").mock(
        return_value=httpx.Response(200, json={"priority": "high"})
    )

    result = await submit_incident(
        api_url="http://localhost:8000",
        caller_name="Priya Nair",
        location="Batticaloa",
        audio_bytes=b"fake-ogg-bytes",
        filename="voice.ogg",
        mime_type="audio/ogg",
        timeout_seconds=30.0,
    )

    assert result["priority"] == "high"
    assert route.called
    request = route.calls.last.request
    # httpx encodes multipart; field names must match web client
    content = request.content.decode("latin-1", errors="replace")
    assert "caller_name" in content or b"caller_name" in request.content
    assert "location" in content or b"location" in request.content
    assert "audio" in content or b"audio" in request.content


@pytest.mark.asyncio
@respx.mock
async def test_submit_incident_error_detail():
    respx.post("http://localhost:8000/incident").mock(
        return_value=httpx.Response(422, json={"detail": "Invalid audio format"})
    )

    with pytest.raises(IncidentApiError, match="Invalid audio format"):
        await submit_incident(
            api_url="http://localhost:8000",
            caller_name="Test",
            location="Test",
            audio_bytes=b"x",
        )
