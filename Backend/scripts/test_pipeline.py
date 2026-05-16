"""
Integration test for VALSEA → Gemini → /incident pipeline.
Run from Backend/:  python scripts/test_pipeline.py
"""

from __future__ import annotations

import json
import sys
import wave
from io import BytesIO
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def make_silent_wav(seconds: float = 1.0) -> bytes:
    """Minimal valid WAV (smoke test only — APIs may reject or return empty)."""
    buf = BytesIO()
    rate = 16000
    nframes = int(rate * seconds)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def download_sample_speech() -> tuple[bytes, str] | None:
    try:
        import urllib.request

        url = "https://www2.cs.uic.edu/~i101/SoundFiles/ImperialMarch60.wav"
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read(), "sample.wav"
    except Exception as exc:
        print(f"  [skip] Could not download sample audio: {exc}")
        return None


def test_imports() -> bool:
    print("1. Import check...")
    try:
        from pipeline import process_incident_audio  # noqa: F401
        from valsea import VALSEA_API_KEY  # noqa: F401
        from gemini import GEMINI_API_KEY  # noqa: F401

        print("   OK — modules load")
        return True
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return False


def test_env() -> bool:
    print("2. Environment check...")
    from gemini import GEMINI_API_KEY
    from valsea import VALSEA_API_KEY

    ok = True
    if not VALSEA_API_KEY:
        print("   FAIL — VALSEA_API_KEY missing")
        ok = False
    else:
        print("   OK — VALSEA_API_KEY set")
    if not GEMINI_API_KEY:
        print("   FAIL — GEMINI_API_KEY missing")
        ok = False
    else:
        print("   OK — GEMINI_API_KEY set")
    return ok


def test_health(base_url: str) -> bool:
    print(f"3. Health endpoint ({base_url}/health)...")
    try:
        import urllib.request

        with urllib.request.urlopen(f"{base_url}/health", timeout=10) as resp:
            body = json.loads(resp.read().decode())
        if body.get("status") == "ok":
            print("   OK — server responding")
            return True
        print(f"   FAIL — unexpected body: {body}")
        return False
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return False


def _test_audio_bytes() -> tuple[bytes, str]:
    sample = download_sample_speech()
    if sample:
        audio_bytes, filename = sample
        print(f"   Using downloaded sample ({len(audio_bytes)} bytes)")
        return audio_bytes, filename
    audio_bytes, filename = make_silent_wav(2.0), "silent.wav"
    print("   Using generated silent WAV (transcription may be empty)")
    return audio_bytes, filename


def test_valsea_only() -> bool:
    print("4. VALSEA modules (transcribe, clarify, prosody, sentiment — ~30–60s)...")
    from valsea import process_audio

    audio_bytes, filename = _test_audio_bytes()
    try:
        result = process_audio(audio_bytes, filename)
        print("   OK — VALSEA completed")
        print(f"   stress={result.stress} urgency={result.urgency} tone={result.voice_tone}")
        transcript = result.clarified_transcript or result.raw_transcript or ""
        print(f"   transcript (first 120 chars): {transcript[:120]!r}")
        return True
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return False


def test_gemini_only() -> bool:
    print("5. Gemini analysis (needs valid GEMINI_API_KEY — ~10–30s)...")
    from gemini import analyze_incident
    from valsea import process_audio

    audio_bytes, filename = _test_audio_bytes()
    try:
        valsea = process_audio(audio_bytes, filename).to_dict()
        data = analyze_incident(
            audio_bytes,
            filename,
            valsea,
            caller_name_hint="Test User",
            contact_number="0770000000",
            incident_type="disaster",
            location_hint="Colombo",
        )
        print("   OK — Gemini completed")
        print(f"   priority={data.get('priority')} caller={data.get('caller_name')}")
        return True
    except Exception as exc:
        err = str(exc)
        if "404" in err and "models/" in err:
            print("   FAIL — model not found. Set GEMINI_MODEL=gemini-2.0-flash in .env")
        elif "leaked" in err.lower():
            print("   FAIL — API key revoked (reported as leaked). Generate a new key in Google AI Studio.")
        elif "quota" in err.lower() or "ResourceExhausted" in err:
            print("   FAIL — Gemini quota exceeded. Enable billing or use a fresh API key.")
        else:
            print(f"   FAIL — {exc}")
        return False


def test_pipeline_live() -> bool:
    print("6. Full pipeline (VALSEA + Gemini — may take 60–120s)...")
    from pipeline import process_incident_audio

    audio_bytes, filename = _test_audio_bytes()
    try:
        result = process_incident_audio(
            audio_bytes,
            filename,
            caller_name_hint="Test User",
            contact_number="0770000000",
            incident_type="disaster",
            location_hint="Colombo",
            source="test",
        )
        print("   OK — pipeline completed")
        print(f"   id:       {result.get('id')}")
        print(f"   priority: {result.get('priority')}")
        record = result.get("record", {})
        print(f"   caller:   {record.get('caller_name')}")
        print(f"   location: {record.get('location')}")
        return True
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return False


def test_incident_endpoint(base_url: str) -> bool:
    print(f"7. POST /incident ({base_url})...")
    try:
        import urllib.request

        sample = download_sample_speech()
        if not sample:
            audio_bytes, filename = make_silent_wav(1.0), "silent.wav"
        else:
            audio_bytes, filename = sample

        boundary = "----ResQNetTestBoundary"
        parts = []
        for name, value in [
            ("caller_name", "Integration Test"),
            ("contact_number", "0771111111"),
            ("incident_type", "medical"),
            ("location", "Kandy"),
        ]:
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            )
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        )
        body = b"".join(
            [p.encode() if isinstance(p, str) else p for p in parts[:-1]]
            + [parts[-1].encode(), audio_bytes, f"\r\n--{boundary}--\r\n".encode()]
        )

        req = urllib.request.Request(
            f"{base_url}/incident",
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
        print(f"   OK — status {resp.status}, priority={data.get('priority')}, id={str(data.get('id', ''))[:8]}...")
        return True
    except Exception as exc:
        print(f"   FAIL — {exc}")
        if hasattr(exc, "read"):
            try:
                print(f"   Response: {exc.read().decode()[:500]}")
            except Exception:
                pass
        return False


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    print("=== ResQNet pipeline integration test ===\n")

    results = [
        test_imports(),
        test_env(),
        test_health(base_url),
    ]

    if all(results[:2]):
        results.append(test_valsea_only())
    else:
        print("4. Skipped — fix imports/env first")
        results.append(False)

    if results[-1]:
        results.append(test_gemini_only())
    else:
        print("5. Skipped — VALSEA failed")
        results.append(False)

    if results[2] and results[-1]:
        results.append(test_pipeline_live())
    else:
        print("6. Skipped — prior steps failed")
        results.append(False)

    if results[2]:
        results.append(test_incident_endpoint(base_url))
    else:
        print("7. Skipped — start server: python main.py")
        results.append(False)

    print("\n=== Summary ===")
    names = ["imports", "env", "health", "valsea", "gemini", "pipeline", "endpoint"]
    for name, ok in zip(names, results):
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
