"""Tests for the messages module."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import messages


def test_priority_icons_complete():
    for level in ("critical", "high", "medium", "low"):
        assert level in messages.PRIORITY_ICONS, f"Missing icon for priority: {level}"


def test_status_labels_complete():
    for status in ("PENDING", "IN_PROGRESS", "RESOLVED"):
        assert status in messages.STATUS_LABELS, f"Missing label for status: {status}"


def test_report_success_format():
    result = messages.REPORT_SUCCESS.format(
        icon="🔴", priority="CRITICAL", ref_id="abc12345", phone="0771234567"
    )
    assert "abc12345" in result
    assert "CRITICAL" in result
    assert "0771234567" in result


def test_ask_voice_format():
    result = messages.ASK_VOICE.format(phone="0771234567")
    assert "0771234567" in result


def test_status_report_format():
    result = messages.STATUS_REPORT.format(
        ref_id="abc12345",
        priority_icon="🔴",
        priority="CRITICAL",
        status_label="🟡 Open — awaiting agent",
        created_at="2026-05-17 04:00",
    )
    assert "abc12345" in result
    assert "CRITICAL" in result
