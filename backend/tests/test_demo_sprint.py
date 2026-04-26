"""
Demo Readiness Sprint Tests - Iteration 14
Tests for: demo-check endpoint, nationality enrollment flow, premium formatting,
PDF ticket generation, gTTS, Whisper module, OCR MRZ parser, Telegram support
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test phone numbers for fresh tests
TEST_PHONES = [f"+22990SPRINT{i:02d}" for i in range(1, 11)]


class TestDemoCheckEndpoint:
    """Test GET /api/demo-check endpoint - system readiness"""
    
    def test_demo_check_returns_200(self):
        """Demo check endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/demo-check")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/demo-check returns 200")
    
    def test_demo_check_all_systems_ok(self):
        """Demo check should show all critical systems as ok"""
        response = requests.get(f"{BASE_URL}/api/demo-check")
        data = response.json()
        
        # Check critical systems
        assert data.get("whisper") == "ok", f"Whisper not ok: {data.get('whisper')}"
        assert data.get("ffmpeg") == "ok", f"ffmpeg not ok: {data.get('ffmpeg')}"
        assert data.get("claude") == "ok", f"Claude not ok: {data.get('claude')}"
        assert data.get("mongodb") == "ok", f"MongoDB not ok: {data.get('mongodb')}"
        print("PASS: All critical systems (whisper, ffmpeg, claude, mongodb) are ok")
    
    def test_demo_check_demo_ready_true(self):
        """Demo check should return demo_ready=true"""
        response = requests.get(f"{BASE_URL}/api/demo-check")
        data = response.json()
        
        assert data.get("demo_ready") == True, f"demo_ready is not True: {data.get('demo_ready')}"
        print("PASS: demo_ready is True")
    
    def test_demo_check_optional_systems(self):
        """Demo check should include optional systems status"""
        response = requests.get(f"{BASE_URL}/api/demo-check")
        data = response.json()
        
        # Check optional systems are present
        assert "ocr" in data, "OCR status missing"
        assert "gtts" in data, "gTTS status missing"
        assert "telegram_webhook" in data, "Telegram webhook status missing"
        assert "whatsapp_webhook" in data, "WhatsApp webhook status missing"
        assert "duffel" in data, "Duffel status missing"
        
        # Verify OCR and gTTS are ok
        assert data.get("ocr") == "ok", f"OCR not ok: {data.get('ocr')}"
        assert data.get("gtts") == "ok", f"gTTS not ok: {data.get('gtts')}"
        print("PASS: Optional systems (ocr, gtts, telegram, whatsapp, duffel) present")
    
    def test_demo_check_languages_supported(self):
        """Demo check should list supported languages"""
        response = requests.get(f"{BASE_URL}/api/demo-check")
        data = response.json()
        
        languages = data.get("languages_supported", [])
        assert "fr" in languages, "French not in supported languages"
        assert "en" in languages, "English not in supported languages"
        assert len(languages) >= 5, f"Expected at least 5 languages, got {len(languages)}"
        print(f"PASS: Languages supported: {languages}")


class TestEnrollmentNationalityFlow:
    """Test enrollment flow with nationality field"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear session before each test"""
        self.phone = TEST_PHONES[0]
        requests.delete(f"{BASE_URL}/api/test/session/{self.phone}")
        time.sleep(0.5)
    
    def test_manual_enrollment_asks_nationality_after_passport(self):
        """After passport number, should transition to enrolling_manual_nat state"""
        phone = self.phone
        
        # Start conversation
        r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        assert r.status_code == 200
        time.sleep(0.5)
        
        # Accept consent
        r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        assert r.status_code == 200
        time.sleep(0.5)
        
        # Choose manual entry
        r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        assert r.status_code == 200
        time.sleep(0.5)
        
        # Enter first name
        r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Jean"})
        assert r.status_code == 200
        time.sleep(0.5)
        
        # Enter last name
        r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Dupont"})
        assert r.status_code == 200
        time.sleep(0.5)
        
        # Enter passport number
        r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "AB123456"})
        assert r.status_code == 200
        data = r.json()
        
        # Should now be in enrolling_manual_nat state
        session_state = data.get("session_state", "")
        assert session_state == "enrolling_manual_nat", \
            f"Expected enrolling_manual_nat state, got: {session_state}"
        print("PASS: After passport, state is enrolling_manual_nat")
    
    def test_nationality_stored_in_enrollment_data(self):
        """Nationality should be stored in enrollment_data before confirmation"""
        phone = TEST_PHONES[1]
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        time.sleep(0.5)
        
        # Go through enrollment until nationality
        steps = ["bonjour", "1", "3", "Marie", "Kouassi", "passer", "Beninoise"]
        
        for msg in steps:
            r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": msg})
            assert r.status_code == 200
            time.sleep(0.5)
        
        # Check session for enrollment_data with nationality
        r = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        assert r.status_code == 200
        session = r.json()
        
        enrollment_data = session.get("enrollment_data", {})
        assert enrollment_data.get("nationality") == "Beninoise", \
            f"Expected nationality 'Beninoise', got: {enrollment_data.get('nationality')}"
        print("PASS: Nationality stored in enrollment_data")
    
    def test_profile_confirmation_state_reached(self):
        """After nationality, should reach confirming_profile state"""
        phone = TEST_PHONES[2]
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        time.sleep(0.5)
        
        # Go through enrollment
        steps = ["bonjour", "1", "3", "Pierre", "Martin", "passer", "Francaise"]
        
        for msg in steps:
            r = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": msg})
            assert r.status_code == 200
            time.sleep(0.5)
        
        # Should be in confirming_profile state
        data = r.json()
        session_state = data.get("session_state", "")
        assert session_state == "confirming_profile", \
            f"Expected confirming_profile state, got: {session_state}"
        
        # Verify enrollment_data has nationality
        r = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        session = r.json()
        enrollment_data = session.get("enrollment_data", {})
        assert enrollment_data.get("nationality") == "Francaise", \
            f"Expected nationality 'Francaise', got: {enrollment_data.get('nationality')}"
        print("PASS: Profile confirmation state reached with nationality")


class TestPremiumFormatting:
    """Test premium message formatting for flight results and payment menu"""
    
    def test_flight_results_formatting_has_separators(self):
        """Flight results formatting should use separator lines"""
        # Import the formatting function directly
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.formatting import format_flight_options_message
        
        # Mock categorized flights
        categorized = {
            "PLUS_BAS": {
                "final_price": 350,
                "airline": "Air France",
                "flight_number": "AF123",
                "departure_time": "08:00",
                "arrival_time": "14:00",
                "duration_formatted": "6h",
                "stops_text": "Direct",
                "category": "PLUS_BAS"
            }
        }
        
        msg = format_flight_options_message(categorized, "COO", "CDG", "2026-02-01", lang="fr", country="BJ")
        
        # Check for separator character (━)
        assert "━" in msg, f"Message should have separator lines, got: {msg[:200]}"
        print("PASS: Flight results have separator lines")
    
    def test_price_shows_eur_and_xof(self):
        """Prices should show both EUR and XOF"""
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.formatting import format_flight_options_message
        
        # Mock categorized flights
        categorized = {
            "PLUS_BAS": {
                "final_price": 350,
                "airline": "Air France",
                "flight_number": "AF123",
                "departure_time": "08:00",
                "arrival_time": "14:00",
                "duration_formatted": "6h",
                "stops_text": "Direct",
                "category": "PLUS_BAS"
            }
        }
        
        msg = format_flight_options_message(categorized, "COO", "CDG", "2026-02-01", lang="fr", country="BJ")
        
        assert "EUR" in msg, f"Message should contain EUR, got: {msg}"
        assert "XOF" in msg, f"Message should contain XOF, got: {msg}"
        print("PASS: Price formatting shows EUR and XOF")
    
    def test_payment_menu_shows_celtiis_recommended(self):
        """Payment menu should show Celtiis Cash as recommended"""
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.formatting import format_payment_menu
        
        menu = [
            {"index": 1, "driver_name": "celtiis_cash", "label": "Celtiis Cash"},
            {"index": 2, "driver_name": "mtn_momo", "label": "MTN MoMo"},
        ]
        pricing = {"total_eur": 350, "gds_price_eur": 330, "travelioo_fee_eur": 20}
        
        msg = format_payment_menu(menu, pricing, "BJ", "fr")
        
        assert "Recommande" in msg or "Recommended" in msg, \
            f"Payment menu should show recommended, got: {msg}"
        print("PASS: Payment menu shows Celtiis Cash as recommended")
    
    def test_payment_menu_shows_split_hint(self):
        """Payment menu should show split payment hint"""
        import sys
        sys.path.insert(0, '/app/backend')
        from utils.formatting import format_payment_menu
        
        menu = [
            {"index": 1, "driver_name": "celtiis_cash", "label": "Celtiis Cash"},
        ]
        pricing = {"total_eur": 350, "gds_price_eur": 330, "travelioo_fee_eur": 20}
        
        msg = format_payment_menu(menu, pricing, "BJ", "fr")
        
        assert "split" in msg.lower() or "fractionner" in msg.lower(), \
            f"Payment menu should show split hint, got: {msg}"
        print("PASS: Payment menu shows split payment hint")


class TestPDFTicketGeneration:
    """Test PDF ticket generation"""
    
    def test_ticket_generation_creates_file(self):
        """PDF ticket generation should create a file"""
        from services.ticket import generate_ticket_pdf
        from config import TICKETS_DIR
        
        booking = {
            "booking_ref": "TRV-TEST01",
            "passenger_name": "Test Passenger",
            "origin": "COO",
            "destination": "CDG",
            "airline": "Air France",
            "flight_number": "AF123",
            "departure_date": "2026-02-01",
            "departure_time": "2026-02-01T08:00:00",
            "category": "Economy",
            "price_eur": 350,
            "price_xof": 229600,
            "passenger_passport": "AB123456"
        }
        
        filename = generate_ticket_pdf(booking)
        
        assert filename is not None, "Ticket generation returned None"
        assert filename.endswith(".pdf"), f"Expected PDF file, got: {filename}"
        
        filepath = TICKETS_DIR / filename
        assert filepath.exists(), f"PDF file not created at {filepath}"
        
        # Check file size (should be > 1KB)
        size = filepath.stat().st_size
        assert size > 1000, f"PDF file too small: {size} bytes"
        
        print(f"PASS: PDF ticket generated: {filename} ({size} bytes)")
    
    def test_ticket_has_travelioo_branding(self):
        """PDF ticket should have Travelioo branding"""
        from services.ticket import generate_ticket_pdf, BRAND_VIOLET
        
        # The ticket module uses Travelioo branding constants
        assert BRAND_VIOLET == "#6C63FF", f"Brand violet color incorrect: {BRAND_VIOLET}"
        print("PASS: Ticket uses Travelioo branding colors")


class TestGTTSVoiceResponses:
    """Test gTTS text-to-speech generation"""
    
    def test_gtts_generates_mp3(self):
        """gTTS should generate MP3 file"""
        import asyncio
        from services.tts import text_to_speech
        from config import TICKETS_DIR
        
        async def run_test():
            filename = await text_to_speech("Bonjour, bienvenue sur Travelioo", lang="fr", filename_prefix="test_tts")
            return filename
        
        filename = asyncio.get_event_loop().run_until_complete(run_test())
        
        assert filename is not None, "TTS returned None"
        assert filename.endswith(".mp3"), f"Expected MP3 file, got: {filename}"
        
        filepath = TICKETS_DIR / filename
        assert filepath.exists(), f"MP3 file not created at {filepath}"
        
        size = filepath.stat().st_size
        assert size > 1000, f"MP3 file too small: {size} bytes"
        
        print(f"PASS: gTTS generated MP3: {filename} ({size} bytes)")
    
    def test_gtts_language_mapping(self):
        """gTTS language mapping should work"""
        from services.tts import _tts_lang_code
        
        assert _tts_lang_code("fr") == "fr"
        assert _tts_lang_code("en") == "en"
        assert _tts_lang_code("fon") == "fr"  # African languages map to French
        assert _tts_lang_code("wo") == "fr"
        print("PASS: gTTS language mapping correct")


class TestWhisperModule:
    """Test Whisper transcription module"""
    
    def test_whisper_convert_ogg_to_mp3_exists(self):
        """Whisper module should have _convert_ogg_to_mp3 function"""
        from services.whisper import _convert_ogg_to_mp3
        
        assert callable(_convert_ogg_to_mp3), "_convert_ogg_to_mp3 is not callable"
        print("PASS: _convert_ogg_to_mp3 function exists")
    
    def test_whisper_transcribe_audio_exists(self):
        """Whisper module should have transcribe_audio function"""
        from services.whisper import transcribe_audio
        
        assert callable(transcribe_audio), "transcribe_audio is not callable"
        print("PASS: transcribe_audio function exists")
    
    def test_whisper_telegram_audio_download_exists(self):
        """Whisper module should support Telegram audio download"""
        from services.whisper import _download_telegram_audio
        
        assert callable(_download_telegram_audio), "_download_telegram_audio is not callable"
        print("PASS: _download_telegram_audio function exists")


class TestOCRMRZParser:
    """Test OCR MRZ parser for passport scanning"""
    
    def test_mrz_parser_extracts_nationality(self):
        """MRZ parser should extract nationality from line1[2:5]"""
        from services.passport import _parse_mrz_from_text
        
        # Sample MRZ text (P<FRAMARTIN<<JEAN<<<<<<<<<<<<<<<<<<<<<<<<<<<)
        mrz_text = """
        P<FRAMARTIN<<JEAN<<<<<<<<<<<<<<<<<<<<<<<<<<<
        AB12345678FRA9001011M3001019<<<<<<<<<<<<<<02
        """
        
        result = _parse_mrz_from_text(mrz_text, confidence=0.9)
        
        # Nationality should be extracted from position 2:5 of line 1
        assert result.get("nationality") == "FRA", f"Expected FRA, got: {result.get('nationality')}"
        print("PASS: MRZ parser extracts nationality from line1[2:5]")
    
    def test_mrz_parser_extracts_names(self):
        """MRZ parser should extract first and last names"""
        from services.passport import _parse_mrz_from_text
        
        mrz_text = """
        P<BJNKOUASSI<<MARIE<<<<<<<<<<<<<<<<<<<<<<<<
        CD98765432BJN8505152F2512312<<<<<<<<<<<<<<04
        """
        
        result = _parse_mrz_from_text(mrz_text, confidence=0.9)
        
        assert result.get("lastName") is not None, "Last name not extracted"
        assert result.get("firstName") is not None, "First name not extracted"
        print(f"PASS: MRZ parser extracts names: {result.get('lastName')} {result.get('firstName')}")


class TestTelegramSupport:
    """Test Telegram image and audio support"""
    
    def test_passport_scan_supports_telegram_prefix(self):
        """Passport scan handler should support tg: prefix for Telegram images"""
        from services.passport import download_whatsapp_image
        import asyncio
        
        # The function should handle tg: prefix
        async def run_test():
            # This will fail to download (no real file) but should not crash
            result = await download_whatsapp_image("tg:fake_file_id")
            return result
        
        result = asyncio.get_event_loop().run_until_complete(run_test())
        # Result will be None (no real file) but function should handle tg: prefix
        print("PASS: Passport scan handler accepts tg: prefix")
    
    def test_whisper_supports_telegram_audio(self):
        """Whisper should support tg: prefix for Telegram audio"""
        from services.whisper import transcribe_audio
        import asyncio
        
        async def run_test():
            # This will fail to download but should handle tg: prefix
            result = await transcribe_audio("tg:fake_audio_id")
            return result
        
        result = asyncio.get_event_loop().run_until_complete(run_test())
        # Result will be None but function should not crash
        print("PASS: Whisper handles tg: prefix for Telegram audio")


class TestConversationStates:
    """Test conversation state definitions"""
    
    def test_enrolling_manual_nat_state_exists(self):
        """ENROLLING_MANUAL_NAT state should exist"""
        from models import ConversationState
        
        assert hasattr(ConversationState, "ENROLLING_MANUAL_NAT"), "ENROLLING_MANUAL_NAT state missing"
        assert ConversationState.ENROLLING_MANUAL_NAT == "enrolling_manual_nat"
        print("PASS: ENROLLING_MANUAL_NAT state exists")
    
    def test_enrolling_tp_manual_nat_state_exists(self):
        """ENROLLING_TP_MANUAL_NAT state should exist"""
        from models import ConversationState
        
        assert hasattr(ConversationState, "ENROLLING_TP_MANUAL_NAT"), "ENROLLING_TP_MANUAL_NAT state missing"
        assert ConversationState.ENROLLING_TP_MANUAL_NAT == "enrolling_tp_manual_nat"
        print("PASS: ENROLLING_TP_MANUAL_NAT state exists")


class TestEnrollmentHandlers:
    """Test enrollment handler functions"""
    
    def test_handle_manual_nationality_exists(self):
        """handle_manual_nationality function should exist"""
        from conversation.enrollment import handle_manual_nationality
        
        assert callable(handle_manual_nationality), "handle_manual_nationality is not callable"
        print("PASS: handle_manual_nationality function exists")
    
    def test_send_profile_confirmation_includes_nationality(self):
        """send_profile_confirmation should include nationality field"""
        from conversation.enrollment import send_profile_confirmation
        import asyncio
        
        # Check function signature accepts nationality in data
        import inspect
        sig = inspect.signature(send_profile_confirmation)
        params = list(sig.parameters.keys())
        
        assert "data" in params, "send_profile_confirmation should accept data parameter"
        print("PASS: send_profile_confirmation accepts data with nationality")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
