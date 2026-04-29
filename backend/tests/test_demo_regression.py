"""Pre-demo regression — only 3 critical items.

1. POST /api/webchat/message — French message reply + session persistence
2. Telegram voice transcription pipeline — code path import-clean + handler dispatch
3. WhatsApp webhook signature verification with [WEBHOOK][SIG-DEBUG] log line
"""
import os
import time
import uuid
import json
import subprocess
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://voice-travel-booking.preview.emergentagent.com").rstrip("/")
BACKEND_LOG = "/var/log/supervisor/backend.err.log"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ───────────────────────── 1. WEBCHAT ─────────────────────────
class TestWebchat:
    def test_webchat_first_message_french(self, session):
        sid = f"TEST_{uuid.uuid4().hex[:8]}"
        r = session.post(f"{BASE_URL}/api/webchat/message",
                         json={"session_id": sid, "message": "bonjour"}, timeout=60)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "session_id" in data, f"missing session_id in {data}"
        assert "response" in data, f"missing response in {data}"
        assert isinstance(data["response"], str)
        assert len(data["response"].strip()) > 0, f"empty response: {data}"
        assert data["session_id"] == sid
        # store for next test
        pytest.webchat_sid = sid
        pytest.webchat_first_state = data.get("state", "")

    def test_webchat_session_persists(self, session):
        sid = getattr(pytest, "webchat_sid", None)
        assert sid, "previous test must run first"
        # second message reusing same session_id
        r = session.post(f"{BASE_URL}/api/webchat/message",
                         json={"session_id": sid, "message": "Cotonou Paris"}, timeout=60)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data["session_id"] == sid

        # Verify state actually persisted via session GET endpoint
        g = session.get(f"{BASE_URL}/api/webchat/session/{sid}", timeout=30)
        assert g.status_code == 200
        gdata = g.json()
        assert gdata["session_id"] == sid
        # session state should be a dict (not empty {}) once messages flowed
        state_obj = gdata.get("state", {})
        assert isinstance(state_obj, dict)
        assert state_obj, f"session state not persisted: {gdata}"
        assert "phone" in state_obj or "state" in state_obj, f"unexpected session shape: {state_obj}"


# ───────────────────────── 2. TELEGRAM / WHISPER PIPELINE ─────────────────────────
class TestWhisperPipeline:
    def test_whisper_module_imports_clean(self):
        # Must be import-clean (no startup errors)
        from services import whisper as w
        assert hasattr(w, "transcribe_audio")
        assert hasattr(w, "_convert_ogg_to_mp3")
        assert hasattr(w, "_download_telegram_audio")
        assert hasattr(w, "_transcribe_bytes")
        # signature accepts audio_id
        import inspect
        sig = inspect.signature(w.transcribe_audio)
        assert "audio_id" in sig.parameters

    def test_openai_api_key_present(self):
        from services.whisper import _get_api_key
        key = _get_api_key()
        assert key, "Neither OPENAI_API_KEY nor EMERGENT_LLM_KEY set"
        assert len(key) > 10

    def test_openai_client_initializes_cleanly(self):
        import openai
        from services.whisper import _get_api_key
        key = _get_api_key()
        # Should NOT raise
        client = openai.OpenAI(api_key=key)
        assert client is not None

    def test_ffmpeg_available(self):
        # whisper pipeline calls subprocess "ffmpeg" — verify it exists on PATH
        import shutil
        path = shutil.which("ffmpeg")
        assert path, "ffmpeg binary not found on PATH — OGG->MP3 conversion will fail"

    def test_telegram_handler_dispatches_text(self, session):
        phone = "+22990TGTEST1"
        # cleanup
        session.delete(f"{BASE_URL}/api/test/session/{phone}", timeout=30)
        r = session.post(f"{BASE_URL}/api/test/simulate",
                         json={"phone": phone, "channel": "telegram",
                               "chat_id": 99999, "message": "bonjour"}, timeout=60)
        assert r.status_code == 200, f"simulate failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("status") == "processed"
        assert data.get("channel") == "telegram"
        assert data.get("phone") == phone


# ───────────────────────── 3. WEBHOOK SIGNATURE + SIG-DEBUG ─────────────────────────
class TestWebhookSignature:
    def test_get_webhook_verification_returns_challenge(self, session):
        r = session.get(
            f"{BASE_URL}/api/webhook",
            params={"hub.mode": "subscribe",
                    "hub.verify_token": "travelioo_verify_2024",
                    "hub.challenge": "test123"},
            timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        assert r.text == "test123", f"Expected 'test123', got {r.text!r}"

    def test_post_webhook_wrong_signature_returns_403_and_emits_sig_debug_log(self, session):
        # mark log offset
        try:
            offset = os.path.getsize(BACKEND_LOG)
        except OSError:
            offset = 0

        marker = f"SIGTEST_{uuid.uuid4().hex[:8]}"
        payload = {"object": "whatsapp_business_account", "entry": [], "marker": marker}
        body = json.dumps(payload)
        r = session.post(
            f"{BASE_URL}/api/webhook",
            data=body,
            headers={"Content-Type": "application/json",
                     "x-hub-signature-256": "sha256=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"},
            timeout=30)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:200]}"
        body_resp = r.json()
        assert "error" in body_resp

        # give logger a moment to flush
        time.sleep(1.5)

        # Tail the log starting from offset and search for SIG-DEBUG line with required fields
        new_log = ""
        try:
            with open(BACKEND_LOG, "r", errors="ignore") as f:
                f.seek(offset)
                new_log = f.read()
        except Exception as e:
            pytest.fail(f"Could not read backend log: {e}")

        assert "[WEBHOOK][SIG-DEBUG]" in new_log, \
            f"[WEBHOOK][SIG-DEBUG] line NOT found in new backend log output. Snippet:\n{new_log[-2000:]}"
        # Validate the 3 required fields are emitted in the same line
        sig_debug_lines = [ln for ln in new_log.splitlines() if "[WEBHOOK][SIG-DEBUG]" in ln]
        assert sig_debug_lines, "no SIG-DEBUG lines isolated"
        target = sig_debug_lines[-1]
        for field in ("secret_first10=", "sig_received_first10=", "sig_expected_first10="):
            assert field in target, f"missing field {field} in SIG-DEBUG line:\n{target}"
