"""Unit tests for the incident API client (mocked)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.incident_api import BackendError, fetch_incident_status, submit_incident


@pytest.mark.asyncio
async def test_submit_incident_success(dummy_audio_bytes):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"id": "test-uuid", "priority": "high"})

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock()
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("clients.incident_api.aiohttp.ClientSession", return_value=mock_session):
        result = await submit_incident(
            dummy_audio_bytes,
            caller_name="Test User",
            contact_number="0771234567",
            telegram_id="999",
            incident_type="disaster",
        )

    assert result["id"] == "test-uuid"
    assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_submit_incident_backend_error(dummy_audio_bytes):
    mock_resp = MagicMock()
    mock_resp.status = 502
    mock_resp.json = AsyncMock(return_value={"detail": "VALSEA timeout"})

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock()
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("clients.incident_api.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(BackendError) as exc_info:
            await submit_incident(
                dummy_audio_bytes,
                caller_name="Test",
                contact_number="",
                telegram_id="999",
                incident_type="disaster",
            )

    assert exc_info.value.status == 502


@pytest.mark.asyncio
async def test_fetch_incident_status_found():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"id": "abc", "priority": "medium", "status": "PENDING", "created_at": "2026-05-17T00:00:00Z"}
    )

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("clients.incident_api.aiohttp.ClientSession", return_value=mock_session):
        result = await fetch_incident_status("abc12345")

    assert result is not None
    assert result["priority"] == "medium"


@pytest.mark.asyncio
async def test_fetch_incident_status_not_found():
    mock_resp = MagicMock()
    mock_resp.status = 404

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("clients.incident_api.aiohttp.ClientSession", return_value=mock_session):
        result = await fetch_incident_status("nonexistent")

    assert result is None
