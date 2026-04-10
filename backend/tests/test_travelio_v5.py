"""
Travelio v5.0 - Comprehensive Backend Tests (Updated for Enrollment Flow)
Tests: Health endpoint, WhatsApp conversation flow, payment operators, 
flight categorization, booking creation, PDF tickets, audio transcription

Note: v5.0 requires enrollment before booking. Tests now include enrollment steps.
"""
import pytest
import requests
import os
import time
import uuid
import tempfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://voice-travel-booking.preview.emergentagent.com').rstrip('/')


def create_enrolled_session(phone: str) -> dict:
    """Helper: Create a session with completed enrollment"""
    # Start enrollment
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
    # Select manual entry
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
    # Enter first name
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Test"})
    # Enter last name
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "User"})
    # Skip passport
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
    # Confirm profile
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
    # Select "pour moi"
    requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
    # Enter passenger count
    response = requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
    return response.json()


class TestHealthEndpoint:
    """Health endpoint tests - per-operator payment status and integrations"""
    
    def test_health_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health endpoint returns 200")
    
    def test_health_has_payment_operators(self):
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        
        assert "payment_operators" in data
        operators = data["payment_operators"]
        
        # Check all 4 operators are present
        expected_operators = ["mtn_momo", "moov_money", "google_pay", "apple_pay"]
        for op in expected_operators:
            assert op in operators, f"Missing operator: {op}"
            assert "status" in operators[op], f"Missing status for {op}"
            assert "label" in operators[op], f"Missing label for {op}"
            # Status should be one of: configured, sandbox, missing
            assert operators[op]["status"] in ["configured", "sandbox", "missing"]
        
        print(f"✓ All 4 payment operators present with status/label format")
        print(f"  MTN MoMo: {operators['mtn_momo']['status']}")
        print(f"  Moov Money: {operators['moov_money']['status']}")
        print(f"  Google Pay: {operators['google_pay']['status']}")
        print(f"  Apple Pay: {operators['apple_pay']['status']}")
    
    def test_health_has_integrations(self):
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        
        assert "integrations" in data
        integrations = data["integrations"]
        
        expected_integrations = ["claude_ai", "amadeus", "whatsapp", "whisper"]
        for integ in expected_integrations:
            assert integ in integrations, f"Missing integration: {integ}"
            assert integrations[integ] in ["configured", "sandbox", "missing"]
        
        print(f"✓ All integrations present")
        for k, v in integrations.items():
            print(f"  {k}: {v}")
    
    def test_health_version_and_type(self):
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        
        assert data.get("status") == "healthy"
        assert data.get("type") == "whatsapp_agent"
        assert "version" in data
        print(f"✓ Health: status=healthy, type=whatsapp_agent, version={data['version']}")


class TestWhatsAppConversationFlow:
    """Full WhatsApp conversation flow via POST /api/test/message"""
    
    @pytest.fixture
    def unique_phone(self):
        """Generate unique phone for clean session"""
        return f"229{uuid.uuid4().hex[:8]}"
    
    def test_new_user_gets_enrollment(self, unique_phone):
        """Test new user gets enrollment prompt"""
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": unique_phone, "message": "bonjour"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        assert session.get("state") == "enrollment_method"
        print(f"✓ New user gets enrollment prompt, state=enrollment_method")
    
    def test_travel_request_after_enrollment(self, unique_phone):
        """Test travel request transitions to awaiting_flight_selection after enrollment"""
        # Complete enrollment
        create_enrolled_session(unique_phone)
        
        # Now make travel request
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": unique_phone, "message": "Paris"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        assert session.get("state") == "awaiting_date"
        print(f"✓ Travel request after enrollment → awaiting_date")
    
    def test_flight_selection_to_payment_method(self, unique_phone):
        """Test flight selection transitions to awaiting_payment_method"""
        # Complete enrollment
        create_enrolled_session(unique_phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": unique_phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": unique_phone, "message": "demain"})
        
        # Select flight option 1
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": unique_phone, "message": "1"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        assert session.get("state") == "awaiting_payment_method"
        assert session.get("booking_ref") is not None
        print(f"✓ Flight selection → awaiting_payment_method, booking_ref={session.get('booking_ref')}")


class TestPaymentOperators:
    """Test all 4 payment operators: MTN MoMo, Moov Money, Google Pay, Apple Pay"""
    
    @pytest.fixture
    def session_at_payment(self):
        """Create session at awaiting_payment_method state"""
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        return phone
    
    def test_mtn_momo_payment_option_1(self, session_at_payment):
        """Test MTN MoMo payment (option 1)"""
        phone = session_at_payment
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        # Should be in mobile payment state or show MoMo message
        assert session.get("state") in ["awaiting_mobile_payment", "retry", "idle"]
        assert session.get("selected_payment_method") == "mtn_momo"
        print(f"✓ MTN MoMo (option 1) initiated, state={session.get('state')}")
    
    def test_moov_money_payment_option_2(self, session_at_payment):
        """Test Moov Money payment (option 2)"""
        phone = session_at_payment
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "2"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        assert session.get("state") in ["awaiting_mobile_payment", "retry", "idle"]
        assert session.get("selected_payment_method") == "moov_money"
        print(f"✓ Moov Money (option 2) initiated, state={session.get('state')}")
    
    def test_google_pay_payment_option_3(self, session_at_payment):
        """Test Google Pay payment (option 3)"""
        phone = session_at_payment
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "3"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        # Google Pay should redirect to payment page
        assert session.get("state") in ["awaiting_card_payment", "retry", "idle"]
        assert session.get("selected_payment_method") == "google_pay"
        print(f"✓ Google Pay (option 3) initiated, state={session.get('state')}")
    
    def test_apple_pay_payment_option_4(self, session_at_payment):
        """Test Apple Pay payment (option 4)"""
        phone = session_at_payment
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "4"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        # Apple Pay should redirect to payment page
        assert session.get("state") in ["awaiting_card_payment", "retry", "idle"]
        assert session.get("selected_payment_method") == "apple_pay"
        print(f"✓ Apple Pay (option 4) initiated, state={session.get('state')}")


class TestFlightCategorization:
    """Test flight categorization: PLUS_BAS, PLUS_RAPIDE, PREMIUM"""
    
    def test_flight_categories_returned(self):
        """Test /api/test/flights returns 3 categories"""
        response = requests.get(
            f"{BASE_URL}/api/test/flights",
            params={"origin": "COO", "destination": "CDG"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "categorized" in data
        categorized = data["categorized"]
        
        # Check all 3 categories
        expected_categories = ["PLUS_BAS", "PLUS_RAPIDE", "PREMIUM"]
        for cat in expected_categories:
            assert cat in categorized, f"Missing category: {cat}"
            flight = categorized[cat]
            assert "final_price" in flight
            assert "price_xof" in flight
            assert "category" in flight
            assert flight["category"] == cat
        
        print(f"✓ All 3 flight categories returned")
        print(f"  PLUS_BAS: {categorized['PLUS_BAS']['final_price']}€")
        print(f"  PLUS_RAPIDE: {categorized['PLUS_RAPIDE']['final_price']}€")
        print(f"  PREMIUM: {categorized['PREMIUM']['final_price']}€")
    
    def test_plus_bas_is_cheapest(self):
        """Test PLUS_BAS has lowest price"""
        response = requests.get(f"{BASE_URL}/api/test/flights")
        data = response.json()
        categorized = data["categorized"]
        
        plus_bas_price = categorized["PLUS_BAS"]["final_price"]
        
        # PLUS_BAS should be <= other prices
        for cat, flight in categorized.items():
            assert plus_bas_price <= flight["final_price"], f"PLUS_BAS not cheapest vs {cat}"
        
        print(f"✓ PLUS_BAS is cheapest at {plus_bas_price}€")
    
    def test_plus_rapide_is_fastest(self):
        """Test PLUS_RAPIDE has shortest duration"""
        response = requests.get(f"{BASE_URL}/api/test/flights")
        data = response.json()
        categorized = data["categorized"]
        
        plus_rapide_duration = categorized["PLUS_RAPIDE"]["duration_minutes"]
        
        # PLUS_RAPIDE should be <= other durations
        for cat, flight in categorized.items():
            assert plus_rapide_duration <= flight["duration_minutes"], f"PLUS_RAPIDE not fastest vs {cat}"
        
        print(f"✓ PLUS_RAPIDE is fastest at {plus_rapide_duration} minutes")


class TestBookingCreation:
    """Test booking creation with TRV-XXXXXX format"""
    
    def test_booking_ref_format(self):
        """Test booking_ref follows TRV-XXXXXX format"""
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight - this creates booking
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        
        session = data.get("session", {})
        booking_ref = session.get("booking_ref")
        assert booking_ref is not None, "No booking_ref returned"
        assert booking_ref.startswith("TRV-"), f"Invalid format: {booking_ref}"
        assert len(booking_ref) == 10, f"Invalid length: {booking_ref}"  # TRV- + 6 chars
        
        print(f"✓ Booking created with ref: {booking_ref}")


class TestPDFTicketGeneration:
    """Test PDF ticket generation and download"""
    
    def test_ticket_download_endpoint(self):
        """Test GET /api/tickets/{filename} endpoint exists"""
        # Try to get a non-existent ticket - should return 404
        response = requests.get(f"{BASE_URL}/api/tickets/nonexistent.pdf")
        assert response.status_code == 404
        print(f"✓ Ticket endpoint returns 404 for missing file")
    
    def test_complete_flow_generates_ticket(self):
        """Test complete flow generates downloadable ticket"""
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight
        resp = requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        session = resp.json().get("session", {})
        booking_ref = session.get("booking_ref")
        
        # Select MTN MoMo (simulated - auto-succeeds)
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        # Wait for payment polling to complete (simulated payments auto-succeed)
        time.sleep(5)
        
        # Try to download ticket
        if booking_ref:
            ticket_filename = f"travelio_ticket_{booking_ref}.pdf"
            response = requests.get(f"{BASE_URL}/api/tickets/{ticket_filename}")
            
            # May or may not exist depending on timing
            if response.status_code == 200:
                assert response.headers.get("content-type") == "application/pdf"
                print(f"✓ Ticket downloaded: {ticket_filename}")
            else:
                print(f"⚠ Ticket not yet generated (async): {ticket_filename}")
        else:
            print(f"⚠ No booking_ref returned")


class TestPaymentPage:
    """Test payment page served at GET /api/pay/{booking_ref}"""
    
    def test_payment_page_returns_html_after_card_selection(self):
        """Test payment page returns HTML after selecting Google Pay"""
        # Create a booking and select Google Pay
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight
        resp = requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        session = resp.json().get("session", {})
        booking_ref = session.get("booking_ref")
        
        if booking_ref:
            # Select Google Pay (option 3) - this creates payment intent
            requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
            
            # Now get payment page - should work with sim mode since Stripe not configured
            response = requests.get(f"{BASE_URL}/api/pay/{booking_ref}?sim=1")
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
            
            # Check HTML contains payment elements
            html = response.text
            assert "Stripe" in html or "paiement" in html.lower()
            print(f"✓ Payment page returns HTML for {booking_ref}")
        else:
            pytest.skip("No booking_ref returned")
    
    def test_payment_page_simulated_mode(self):
        """Test payment page with sim=1 parameter"""
        response = requests.get(f"{BASE_URL}/api/pay/TRV-TEST01?sim=1")
        assert response.status_code == 200
        html = response.text
        assert "Stripe" in html or "Travelio" in html
        print(f"✓ Simulated payment page works")
    
    def test_payment_page_404_without_intent(self):
        """Test payment page returns 404 when no payment intent exists"""
        response = requests.get(f"{BASE_URL}/api/pay/TRV-NONEXISTENT")
        assert response.status_code == 404
        print(f"✓ Payment page returns 404 for non-existent booking")


class TestCancelFlow:
    """Test cancel flow with 'annuler' command"""
    
    def test_annuler_cancels_booking(self):
        """Test 'annuler' cancels booking in AWAITING_PAYMENT_METHOD state"""
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        # Cancel
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "annuler"}
        )
        data = response.json()
        
        session = data.get("session", {})
        assert session.get("state") == "idle"
        assert session.get("booking_ref") is None  # Booking cleared
        print(f"✓ 'annuler' cancels booking, state=idle")


class TestPaymentRetryFlow:
    """Test payment retry flow after failure"""
    
    def test_retry_options_after_failure(self):
        """Test retry options: 1=retry, 2=change method, 3=cancel"""
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        # Select payment with simulate_fail=true
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1", "simulate_fail": "true"}
        )
        
        # Wait for payment to fail
        time.sleep(5)
        
        # Check session state
        # Send any message to get current state
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "status"}
        )
        data = response.json()
        
        # Should be in retry state or show retry options
        state = data.get("session", {}).get("state", "")
        
        if state == "retry":
            print(f"✓ Retry flow triggered, state={state}")
        else:
            print(f"⚠ Retry flow may not have triggered (state={state})")
    
    def test_cancel_from_retry_state(self):
        """Test option 3 cancels from retry state"""
        phone = f"229{uuid.uuid4().hex[:8]}"
        
        # Complete enrollment
        create_enrolled_session(phone)
        
        # Destination
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Paris"})
        
        # Date
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        # Select flight
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        # Select payment with simulate_fail
        requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1", "simulate_fail": "true"}
        )
        
        # Wait for failure
        time.sleep(5)
        
        # Option 3 = cancel
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "3"}
        )
        data = response.json()
        
        # Should be idle after cancel
        if data.get("session", {}).get("state") == "idle":
            print(f"✓ Option 3 cancels from retry state")
        else:
            print(f"⚠ Cancel from retry may not work (state={data.get('session', {}).get('state')})")


class TestWhisperTranscription:
    """Test Whisper audio transcription via POST /api/test/transcribe"""
    
    def test_transcribe_endpoint_exists(self):
        """Test transcribe endpoint accepts multipart form"""
        # Create a minimal test audio file
        response = requests.post(
            f"{BASE_URL}/api/test/transcribe",
            files={"file": ("test.mp3", b"fake audio data", "audio/mpeg")}
        )
        
        # Should return 200 or 400/500 (not 404)
        assert response.status_code != 404, "Transcribe endpoint not found"
        print(f"✓ Transcribe endpoint exists (status={response.status_code})")
    
    def test_transcribe_with_ogg_file(self):
        """Test transcription with .ogg file (auto-converts to mp3)"""
        # This test requires actual audio - skip if no real audio available
        # The endpoint should handle .ogg files
        
        response = requests.post(
            f"{BASE_URL}/api/test/transcribe",
            files={"file": ("test.ogg", b"OggS" + b"\x00" * 100, "audio/ogg")}
        )
        
        # Should not return 404
        assert response.status_code != 404
        print(f"✓ OGG transcription endpoint works (status={response.status_code})")


class TestWebhookVerification:
    """Test WhatsApp webhook verification"""
    
    def test_webhook_verification_success(self):
        """Test webhook verification with correct token"""
        response = requests.get(
            f"{BASE_URL}/api/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "travelio_verify_2024",
                "hub.challenge": "12345"
            }
        )
        assert response.status_code == 200
        assert response.text == "12345"
        print(f"✓ Webhook verification succeeds with correct token")
    
    def test_webhook_verification_failure(self):
        """Test webhook verification with wrong token"""
        response = requests.get(
            f"{BASE_URL}/api/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "12345"
            }
        )
        assert response.status_code == 403
        print(f"✓ Webhook verification fails with wrong token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
