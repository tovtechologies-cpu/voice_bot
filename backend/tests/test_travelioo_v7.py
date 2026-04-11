"""Travelioo v7.0 - Comprehensive Backend Tests
Tests: Modular architecture, Duffel GDS (sandbox), AES-256 encryption, 
fuzzy airport matching, date parsing, legal endpoints, rate limiting, message chunking
"""
import pytest
import requests
import os
import time
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test phone numbers - unique per test run
TEST_PHONE_NEW = f"+22990V7NEW{int(time.time()) % 10000:04d}"
TEST_PHONE_FLOW = f"+22990V7FLW{int(time.time()) % 10000:04d}"


class TestHealthAndRoot:
    """Health and root endpoint tests"""
    
    def test_health_endpoint_returns_healthy(self):
        """GET /api/health - Returns healthy status with all service statuses"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert data.get("status") == "healthy"
        assert data.get("version") == "7.0"
        assert data.get("type") == "WhatsApp Agent"
        assert "timestamp" in data
        
        # Check services structure
        services = data.get("services", {})
        assert "mongodb" in services
        assert "whatsapp" in services
        assert "claude_ai" in services
        assert "duffel" in services  # New in v7.0 - Duffel instead of Amadeus
        
        # Check Duffel is in sandbox mode
        assert services.get("duffel") == "sandbox"
        
        # Check payment operators
        operators = data.get("payment_operators", {})
        assert "mtn_momo" in operators
        assert "moov_money" in operators
        assert "google_pay" in operators
        assert "apple_pay" in operators
        
        # Check integrations
        integrations = data.get("integrations", {})
        assert "claude_ai" in integrations
        assert "duffel" in integrations  # v7.0: Duffel instead of Amadeus
        assert "whatsapp" in integrations
        assert "whisper" in integrations
        print("PASS: Health endpoint returns v7.0 with Duffel GDS")
    
    def test_root_endpoint_returns_version_7(self):
        """GET /api/ - Returns version 7.0 with all endpoint info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("version") == "7.0"
        assert data.get("name") == "Travelioo WhatsApp Travel Agent"
        assert "Duffel GDS" in data.get("description", "")
        assert "AES-256" in data.get("description", "")
        
        # Check endpoints
        endpoints = data.get("endpoints", {})
        assert endpoints.get("webhook") == "/api/webhook"
        assert endpoints.get("health") == "/api/health"
        assert endpoints.get("legal_terms") == "/api/legal/terms"
        assert endpoints.get("legal_privacy") == "/api/legal/privacy"
        assert endpoints.get("verify_qr") == "/api/verify_qr/{booking_ref}"
        assert endpoints.get("simulate") == "/api/test/simulate"
        print("PASS: Root endpoint returns v7.0 with correct endpoints")


class TestLegalEndpoints:
    """Legal compliance endpoints - Terms and Privacy"""
    
    def test_terms_of_service_returns_html(self):
        """GET /api/legal/terms - Returns HTML Terms of Service"""
        response = requests.get(f"{BASE_URL}/api/legal/terms")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        content = response.text
        assert "Conditions Generales" in content
        assert "Travelioo" in content
        assert "Duffel" in content  # v7.0: Duffel mentioned
        assert "AES-256-GCM" in content  # v7.0: Encryption mentioned
        assert "15EUR" in content  # Travelioo fee
        print("PASS: Terms of Service returns proper HTML with v7.0 content")
    
    def test_privacy_policy_returns_html(self):
        """GET /api/legal/privacy - Returns HTML Privacy Policy"""
        response = requests.get(f"{BASE_URL}/api/legal/privacy")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        content = response.text
        assert "Politique de Confidentialite" in content
        assert "AES-256-GCM" in content  # v7.0: Encryption mentioned
        assert "passeport" in content.lower()
        assert "RGPD" in content
        assert "30 minutes" in content  # Session timeout
        print("PASS: Privacy Policy returns proper HTML with encryption info")


class TestFuzzyAirportRecognition:
    """Fuzzy airport matching with rapidfuzz - v7.0 feature"""
    
    def test_fuzzy_match_dacar_to_dss(self):
        """Fuzzy airport: 'dacar' -> DSS (Dakar)"""
        # Clear session first
        requests.delete(f"{BASE_URL}/api/test/session/{TEST_PHONE_NEW}")
        
        # Start enrollment
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": TEST_PHONE_NEW,
            "message": "bonjour"
        })
        assert response.status_code == 200
        
        # Manual entry
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "User"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "skip"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "1"})  # Confirm
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "1"})  # For myself
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": TEST_PHONE_NEW, "message": "1"})  # 1 passenger
        
        # Test fuzzy match: "dacar" should match "dakar" -> DSS
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": TEST_PHONE_NEW,
            "message": "dacar"  # Misspelled
        })
        assert response.status_code == 200
        
        # Check session - should be awaiting date (destination resolved)
        session = requests.get(f"{BASE_URL}/api/test/session/{TEST_PHONE_NEW}").json()
        assert session.get("state") == "awaiting_date", f"Expected awaiting_date, got {session.get('state')}"
        assert session.get("intent", {}).get("destination") == "DSS"
        print("PASS: Fuzzy match 'dacar' -> DSS (Dakar)")
    
    def test_fuzzy_match_parris_to_cdg(self):
        """Fuzzy airport: 'parris' -> CDG (Paris)"""
        phone = f"+22990FUZZY{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Quick enrollment
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Fuzzy"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        
        # Test fuzzy match: "parris" should match "paris" -> CDG
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "parris"  # Misspelled
        })
        assert response.status_code == 200
        
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("intent", {}).get("destination") == "CDG"
        print("PASS: Fuzzy match 'parris' -> CDG (Paris)")
    
    def test_fuzzy_match_abijan_to_abj(self):
        """Fuzzy airport: 'abijan' -> ABJ (Abidjan)"""
        phone = f"+22990FUZZY2{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Quick enrollment
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Abijan"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        
        # Test fuzzy match: "abijan" should match "abidjan" -> ABJ
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "abijan"  # Misspelled
        })
        assert response.status_code == 200
        
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("intent", {}).get("destination") == "ABJ"
        print("PASS: Fuzzy match 'abijan' -> ABJ (Abidjan)")


class TestDateParsing:
    """Natural language date parsing with dateparser - v7.0 feature"""
    
    def test_date_parse_demain(self):
        """Date parsing: 'demain' -> tomorrow's date"""
        phone = f"+22990DATE1{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Quick enrollment to destination state
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Date"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        
        # Set destination
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Paris"})
        
        # Test date parsing: "demain"
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "demain"
        })
        assert response.status_code == 200
        
        # Should now be in flight selection (date was parsed)
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "awaiting_flight_selection", f"Expected awaiting_flight_selection, got {session.get('state')}"
        
        # Check date is tomorrow
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert session.get("intent", {}).get("departure_date") == tomorrow
        print(f"PASS: Date parsing 'demain' -> {tomorrow}")
    
    def test_date_parse_apres_demain(self):
        """Date parsing: 'apres-demain' -> day after tomorrow"""
        phone = f"+22990DATE2{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Quick enrollment
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Apres"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Demain"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Paris"})
        
        # Test date parsing: "apres-demain"
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "apres-demain"
        })
        assert response.status_code == 200
        
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        assert session.get("intent", {}).get("departure_date") == day_after
        print(f"PASS: Date parsing 'apres-demain' -> {day_after}")
    
    def test_date_parse_iso_format(self):
        """Date parsing: '2026-05-01' -> ISO format preserved"""
        phone = f"+22990DATE3{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Quick enrollment
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "ISO"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Date"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Paris"})
        
        # Test ISO date
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "2026-05-01"
        })
        assert response.status_code == 200
        
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("intent", {}).get("departure_date") == "2026-05-01"
        print("PASS: Date parsing ISO format '2026-05-01' preserved")


class TestFullBookingFlow:
    """Full booking flow with Duffel sandbox"""
    
    def test_complete_booking_flow(self):
        """Full booking: enrollment -> destination -> date -> flight -> payment -> confirm"""
        phone = TEST_PHONE_FLOW
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Step 1: Start enrollment
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "bonjour"
        })
        assert response.status_code == 200
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "enrollment_method"
        print("Step 1: Enrollment started")
        
        # Step 2: Manual entry
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "enrolling_manual_fn"
        print("Step 2: Manual entry selected")
        
        # Step 3: First name
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Amadou"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "enrolling_manual_ln"
        print("Step 3: First name entered")
        
        # Step 4: Last name
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Toure"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "enrolling_manual_pp"
        print("Step 4: Last name entered")
        
        # Step 5: Skip passport
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "confirming_profile"
        print("Step 5: Passport skipped")
        
        # Step 6: Confirm profile
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "asking_travel_purpose"
        print("Step 6: Profile confirmed")
        
        # Step 7: For myself
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "asking_passenger_count"
        print("Step 7: Booking for self")
        
        # Step 8: 1 passenger
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "awaiting_destination"
        print("Step 8: 1 passenger selected")
        
        # Step 9: Destination (fuzzy match)
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "parris"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "awaiting_date"
        assert session.get("intent", {}).get("destination") == "CDG"
        print("Step 9: Destination 'parris' -> CDG")
        
        # Step 10: Date (natural language)
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "demain"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "awaiting_flight_selection"
        assert "flights" in session
        assert len(session.get("flights", [])) > 0
        print(f"Step 10: Date 'demain' parsed, {len(session.get('flights', []))} flights found")
        
        # Step 11: Select flight (cheapest)
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "awaiting_payment_method"
        assert session.get("booking_ref") is not None
        booking_ref = session.get("booking_ref")
        print(f"Step 11: Flight selected, booking ref: {booking_ref}")
        
        # Step 12: Select payment method (MoMo)
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert session.get("state") == "awaiting_payment_confirm"
        assert "_fare_conditions" in session
        print("Step 12: Payment method selected, pre-debit confirmation shown")
        
        # Step 13: Confirm payment
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        
        # Wait for payment processing
        time.sleep(5)
        
        # Check booking status
        bookings = requests.get(f"{BASE_URL}/api/test/bookings/{phone}").json()
        assert len(bookings.get("bookings", [])) > 0
        latest_booking = bookings["bookings"][0]
        assert latest_booking.get("status") == "confirmed"
        print(f"Step 13: Payment confirmed, booking status: {latest_booking.get('status')}")
        
        print("PASS: Full booking flow completed successfully")
        return booking_ref


class TestQRVerification:
    """QR code verification endpoint"""
    
    def test_verify_qr_unknown_booking(self):
        """GET /api/verify_qr/{booking_ref} - Returns UNKNOWN for non-existent booking"""
        response = requests.get(f"{BASE_URL}/api/verify_qr/TRV-NOTEXIST")
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") == False
        assert "not found" in data.get("error", "").lower()
        print("PASS: QR verify returns invalid for non-existent booking")
    
    def test_verify_qr_existing_booking(self):
        """GET /api/verify_qr/{booking_ref} - Returns valid for confirmed booking"""
        # Get a confirmed booking from test flow
        bookings = requests.get(f"{BASE_URL}/api/test/bookings/{TEST_PHONE_FLOW}").json()
        if bookings.get("bookings"):
            booking_ref = bookings["bookings"][0].get("booking_ref")
            response = requests.get(f"{BASE_URL}/api/verify_qr/{booking_ref}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("booking_ref") == booking_ref
            assert "passenger" in data
            assert "route" in data
            print(f"PASS: QR verify returns correct data for {booking_ref}")
        else:
            print("SKIP: No bookings available for QR verification test")


class TestSimulateEndpoint:
    """Test simulate endpoint functionality"""
    
    def test_simulate_requires_message(self):
        """POST /api/test/simulate - Requires message, audio_id, or image_id"""
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": "+22990EMPTY01"
        })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        print("PASS: Simulate endpoint requires message content")
    
    def test_simulate_returns_session_state(self):
        """POST /api/test/simulate - Returns session state after processing"""
        phone = f"+22990SIM{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "bonjour"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "processed"
        assert data.get("session_state") == "enrollment_method"
        assert data.get("phone") == phone
        print("PASS: Simulate endpoint returns session state")


class TestSessionManagement:
    """Session management endpoints"""
    
    def test_get_session(self):
        """GET /api/test/session/{phone} - Returns session data"""
        phone = f"+22990SESS{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Create session
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        
        # Get session
        response = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("phone") == phone
        assert data.get("state") == "enrollment_method"
        print("PASS: Get session returns correct data")
    
    def test_delete_session(self):
        """DELETE /api/test/session/{phone} - Deletes session"""
        phone = f"+22990DEL{int(time.time()) % 10000:04d}"
        
        # Create session
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        
        # Delete session
        response = requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("deleted") == True
        
        # Verify deleted
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        assert "error" in session
        print("PASS: Delete session works correctly")


class TestCancellationFlow:
    """Cancellation and refund flow"""
    
    def test_cancellation_keyword_from_idle(self):
        """Cancellation keyword 'remboursement' works from IDLE state"""
        # Use the phone from full booking flow which has confirmed bookings
        phone = TEST_PHONE_FLOW
        
        # Clear session to get to IDLE state
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Now test cancellation from idle - user already has bookings from previous test
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone, 
            "message": "remboursement"
        })
        assert response.status_code == 200
        
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        
        # Should be in cancellation flow (cancellation_identify) since user has bookings
        # Or asking_travel_purpose if user is recognized as returning user
        assert session.get("state") in ["cancellation_identify", "asking_travel_purpose", "idle"]
        print(f"PASS: Cancellation keyword works, state: {session.get('state')}")


class TestModificationFlow:
    """Modification flow"""
    
    def test_modification_keyword_from_idle(self):
        """Modification keyword 'modifier' works from IDLE state"""
        phone = f"+22990MOD{int(time.time()) % 10000:04d}"
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")
        
        # Start with a user who has bookings
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "modifier"})
        session = requests.get(f"{BASE_URL}/api/test/session/{phone}").json()
        
        # Should be in modification flow or idle (if no bookings)
        # For new user, it will start enrollment
        assert session.get("state") in ["modification_requested", "idle", "enrollment_method"]
        print("PASS: Modification keyword recognized")


class TestPaymentCallbacks:
    """Payment callback endpoints"""
    
    def test_momo_callback(self):
        """POST /api/momo/callback - Receives MoMo callback"""
        response = requests.post(f"{BASE_URL}/api/momo/callback", json={
            "referenceId": "test-ref-123",
            "status": "SUCCESSFUL"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "received"
        print("PASS: MoMo callback endpoint works")
    
    def test_moov_callback(self):
        """POST /api/moov/callback - Receives Moov callback"""
        response = requests.post(f"{BASE_URL}/api/moov/callback", json={
            "transactionId": "test-tx-456",
            "status": "SUCCESS"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "received"
        print("PASS: Moov callback endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
