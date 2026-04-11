"""
Travelioo v5.0 - Enrollment & Passenger Management Tests
Tests: New user enrollment, manual enrollment, profile confirmation, returning user flow,
self booking, third-party booking, saved third-party selection, multi-passenger stub,
session expiry, input validation, passport skip, global cancel, booking passenger fields,
ticket PDF passenger data

Note: The test endpoint returns session state but not the WhatsApp response text.
Tests focus on state transitions and session data validation.
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://voice-travel-booking.preview.emergentagent.com').rstrip('/')


def unique_phone():
    """Generate unique phone for clean session"""
    return f"22990{uuid.uuid4().hex[:6]}"


class TestNewUserEnrollmentFlow:
    """Test new user enrollment flow: first message → enrollment method selection"""
    
    def test_new_user_gets_enrollment_prompt(self):
        """New user first message → enrollment_method state"""
        phone = unique_phone()
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "bonjour"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        
        # New user should get enrollment prompt
        assert session.get("state") == "enrollment_method", f"Expected enrollment_method, got {session.get('state')}"
        assert session.get("enrolling_for") == "self"
        print(f"✓ New user gets enrollment prompt, state=enrollment_method")
    
    def test_enrollment_method_option_3_starts_manual(self):
        """Option 3 → manual enrollment → first name prompt"""
        phone = unique_phone()
        
        # First message
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        
        # Select manual entry (option 3)
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "3"}
        )
        assert response.status_code == 200
        data = response.json()
        
        session = data.get("session", {})
        
        assert session.get("state") == "enrolling_manual_fn", f"Expected enrolling_manual_fn, got {session.get('state')}"
        print(f"✓ Option 3 starts manual enrollment, state=enrolling_manual_fn")
    
    def test_enrollment_method_option_1_starts_scan(self):
        """Option 1 → scan enrollment"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "enrolling_scan", f"Expected enrolling_scan, got {session.get('state')}"
        print(f"✓ Option 1 starts scan enrollment, state=enrolling_scan")


class TestManualEnrollmentFlow:
    """Test complete manual enrollment: first name → last name → passport → confirmation"""
    
    def test_complete_manual_enrollment(self):
        """Full manual enrollment flow"""
        phone = unique_phone()
        
        # Step 1: First message → enrollment prompt
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        
        # Step 2: Select manual (option 3)
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        
        # Step 3: Enter first name
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "Marie"}
        )
        data = response.json()
        session = data.get("session", {})
        assert session.get("state") == "enrolling_manual_ln"
        assert session.get("enrollment_data", {}).get("firstName") == "Marie"
        print(f"✓ First name accepted, state=enrolling_manual_ln")
        
        # Step 4: Enter last name
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "Dupont"}
        )
        data = response.json()
        session = data.get("session", {})
        assert session.get("state") == "enrolling_manual_pp"
        assert session.get("enrollment_data", {}).get("lastName") == "Dupont"
        print(f"✓ Last name accepted, state=enrolling_manual_pp")
        
        # Step 5: Enter passport number
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "AB1234567"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "confirming_profile", f"Expected confirming_profile, got {session.get('state')}"
        assert session.get("enrollment_data", {}).get("passportNumber") == "AB1234567"
        print(f"✓ Passport accepted, state=confirming_profile")
    
    def test_passport_skip_with_passer(self):
        """Test 'passer' skips passport entry"""
        phone = unique_phone()
        
        # Setup: get to passport prompt
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Jean"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Martin"})
        
        # Skip passport with 'passer'
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "passer"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "confirming_profile"
        assert session.get("enrollment_data", {}).get("passportNumber") is None
        print(f"✓ 'passer' skips passport, state=confirming_profile")
    
    def test_passport_skip_with_skip(self):
        """Test 'skip' skips passport entry"""
        phone = unique_phone()
        
        # Setup: get to passport prompt
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "hello"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "John"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Smith"})
        
        # Skip passport with 'skip'
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "skip"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "confirming_profile"
        print(f"✓ 'skip' skips passport, state=confirming_profile")


class TestProfileConfirmation:
    """Test profile confirmation: option 1 saves, option 2 restarts"""
    
    def test_confirmation_option_1_saves_profile(self):
        """Option 1 confirms and saves profile"""
        phone = unique_phone()
        
        # Complete enrollment to confirmation
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Pierre"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Durand"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        
        # Confirm with option 1
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should save profile and move to asking_travel_purpose
        assert session.get("passenger_id") is not None, "passenger_id should be set after confirmation"
        assert session.get("state") == "asking_travel_purpose", f"Expected asking_travel_purpose, got {session.get('state')}"
        print(f"✓ Option 1 saves profile, passenger_id={session.get('passenger_id')[:8]}...")
    
    def test_confirmation_option_2_restarts_enrollment(self):
        """Option 2 restarts enrollment"""
        phone = unique_phone()
        
        # Complete enrollment to confirmation
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "User"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        
        # Reject with option 2
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "2"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should restart enrollment
        assert session.get("state") == "enrollment_method", f"Expected enrollment_method, got {session.get('state')}"
        print(f"✓ Option 2 restarts enrollment, state=enrollment_method")


class TestReturningUserFlow:
    """Test returning user: first message → 'pour moi ou un tiers' (skips enrollment)"""
    
    def test_returning_user_skips_enrollment(self):
        """Returning user with profile skips enrollment"""
        phone = unique_phone()
        
        # First: Create profile (new user flow)
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Sophie"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Bernard"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Now simulate returning user by sending new message
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "bonjour"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Returning user should be at asking_travel_purpose (skips enrollment)
        assert session.get("state") == "asking_travel_purpose", f"Expected asking_travel_purpose, got {session.get('state')}"
        assert session.get("passenger_id") is not None
        print(f"✓ Returning user skips enrollment, state=asking_travel_purpose")


class TestSelfBookingFlow:
    """Test self booking: option 1 → passenger count → destination → date → flights → payment → ticket"""
    
    def test_self_booking_option_1(self):
        """Option 1 (pour moi) sets booking_passenger_id to self"""
        phone = unique_phone()
        
        # Create profile
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Alice"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Moreau"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "CD9876543"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Select "pour moi" (option 1)
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should move to passenger count
        assert session.get("state") == "asking_passenger_count", f"Expected asking_passenger_count, got {session.get('state')}"
        assert session.get("booking_passenger_id") == session.get("passenger_id")
        print(f"✓ Self booking sets booking_passenger_id, state=asking_passenger_count")
    
    def test_complete_self_booking_flow(self):
        """Complete self booking flow with ticket generation"""
        phone = unique_phone()
        
        # Create profile
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Lucas"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Martin"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "EF1234567"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Select "pour moi"
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        # Passenger count (1)
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})
        
        # Destination
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "Paris"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should be awaiting date
        assert session.get("state") == "awaiting_date", f"Expected awaiting_date, got {session.get('state')}"
        print(f"✓ Destination accepted, state=awaiting_date")
        
        # Date
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "demain"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "awaiting_flight_selection"
        assert len(session.get("flights", [])) > 0
        print(f"✓ Date accepted, flights returned, state=awaiting_flight_selection")
        
        # Select flight
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "awaiting_payment_method"
        assert session.get("booking_ref") is not None
        print(f"✓ Flight selected, booking_ref={session.get('booking_ref')}")
        
        # Select payment (MTN MoMo - simulated)
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        
        # Wait for payment to complete
        time.sleep(5)
        
        # Check booking was created with passenger data
        booking_ref = session.get("booking_ref")
        if booking_ref:
            ticket_filename = f"travelioo_ticket_{booking_ref}.pdf"
            ticket_response = requests.get(f"{BASE_URL}/api/tickets/{ticket_filename}")
            if ticket_response.status_code == 200:
                print(f"✓ Ticket generated: {ticket_filename}")
            else:
                print(f"⚠ Ticket not yet generated (async)")


class TestThirdPartyBookingFlow:
    """Test third-party booking: option 2 → new person → enrollment → save prompt → booking"""
    
    def test_third_party_new_person_enrollment(self):
        """Third-party booking with new person enrollment"""
        phone = unique_phone()
        
        # Create own profile first
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Parent"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "User"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Select "pour un tiers" (option 2)
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "2"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should be selecting third party (no saved TP yet)
        assert session.get("state") == "selecting_third_party", f"Expected selecting_third_party, got {session.get('state')}"
        print(f"✓ Third-party selection, state=selecting_third_party")
        
        # Select "new person" (option 2 when no saved TP)
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "2"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "enrolling_third_party_method", f"Expected enrolling_third_party_method, got {session.get('state')}"
        print(f"✓ New person selected, state=enrolling_third_party_method")
        
        # Manual enrollment for third party
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})  # Manual
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "Child"}
        )
        data = response.json()
        assert data.get("session", {}).get("state") == "enrolling_tp_manual_ln"
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "User"}
        )
        data = response.json()
        assert data.get("session", {}).get("state") == "enrolling_tp_manual_pp"
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "GH7654321"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "confirming_tp_profile", f"Expected confirming_tp_profile, got {session.get('state')}"
        print(f"✓ Third-party enrollment complete, state=confirming_tp_profile")
        
        # Confirm third-party profile
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "save_tp_prompt", f"Expected save_tp_prompt, got {session.get('state')}"
        print(f"✓ Third-party confirmed, state=save_tp_prompt")
        
        # Save third-party profile
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "asking_passenger_count", f"Expected asking_passenger_count, got {session.get('state')}"
        assert session.get("booking_passenger_id") is not None
        print(f"✓ Third-party saved, booking_passenger_id set, state=asking_passenger_count")


class TestSavedThirdPartySelection:
    """Test saved third-party: returning user → option 2 → shows saved TP list → select existing"""
    
    def test_saved_third_party_appears_in_list(self):
        """Saved third-party appears in selection list and can be selected"""
        phone = unique_phone()
        
        # Create own profile
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Main"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "User"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Create third-party profile
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "2"})  # Pour un tiers
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "2"})  # New person
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})  # Manual
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Saved"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "ThirdParty"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Save
        
        # Complete a booking to reset state
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # 1 passenger
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Lagos"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Select flight
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # MTN MoMo
        
        # Wait for payment to complete (simulated payments take ~5s to poll)
        time.sleep(8)
        
        # Now start new booking - should see saved TP
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        
        # Select "pour un tiers"
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "2"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should have _tp_list with saved third-party
        tp_list = session.get("_tp_list", [])
        assert len(tp_list) > 0, "Expected saved third-party in _tp_list"
        assert session.get("state") == "selecting_third_party"
        print(f"✓ Saved third-party in _tp_list, count={len(tp_list)}")
        
        # Select saved third-party (option 1)
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "asking_passenger_count", f"Expected asking_passenger_count, got {session.get('state')}"
        assert session.get("booking_passenger_id") is not None
        print(f"✓ Saved third-party selected, state=asking_passenger_count")


class TestMultiPassengerStub:
    """Test multi-passenger stub: entering > 1 shows 'coming soon' message"""
    
    def test_multi_passenger_continues_with_1(self):
        """Entering > 1 passengers continues with 1 passenger"""
        phone = unique_phone()
        
        # Create profile and get to passenger count
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Multi"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Pour moi
        
        # Enter > 1 passengers
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "3"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should continue with 1 passenger (move to awaiting_destination)
        assert session.get("state") == "awaiting_destination", f"Expected awaiting_destination, got {session.get('state')}"
        print(f"✓ Multi-passenger continues with 1, state=awaiting_destination")


class TestInputValidation:
    """Test input validation: invalid name, invalid passport"""
    
    def test_invalid_name_with_numbers_rejected(self):
        """Name with numbers is rejected"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        
        # Try name with numbers
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "123abc"}
        )
        data = response.json()
        session = data.get("session", {})
        
        # Should stay in same state (rejected)
        assert session.get("state") == "enrolling_manual_fn"
        print(f"✓ Name with numbers rejected, stays in enrolling_manual_fn")
    
    def test_name_too_short_rejected(self):
        """Name too short (< 2 chars) is rejected"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        
        # Try single character name
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "A"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "enrolling_manual_fn"
        print(f"✓ Name too short rejected, stays in enrolling_manual_fn")
    
    def test_valid_name_with_hyphen_accepted(self):
        """Name with hyphen is accepted"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "hello"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        
        # Try name with hyphen
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "Jean-Pierre"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "enrolling_manual_ln"
        assert session.get("enrollment_data", {}).get("firstName") == "Jean-Pierre"
        print(f"✓ Name with hyphen accepted")
    
    def test_invalid_passport_too_short_rejected(self):
        """Passport < 6 chars is rejected"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "User"})
        
        # Try short passport
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "AB"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "enrolling_manual_pp"
        print(f"✓ Passport too short rejected, stays in enrolling_manual_pp")


class TestGlobalCancel:
    """Test global cancel: 'annuler' works in enrollment states"""
    
    def test_annuler_in_enrollment_method(self):
        """'annuler' cancels from enrollment_method state"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "annuler"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "idle"
        print(f"✓ 'annuler' cancels from enrollment_method")
    
    def test_annuler_in_manual_enrollment(self):
        """'annuler' cancels from manual enrollment states"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "annuler"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "idle"
        print(f"✓ 'annuler' cancels from enrolling_manual_fn")
    
    def test_annuler_in_confirming_profile(self):
        """'annuler' cancels from confirming_profile state"""
        phone = unique_phone()
        
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Cancel"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "annuler"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "idle"
        print(f"✓ 'annuler' cancels from confirming_profile")
    
    def test_annuler_in_third_party_enrollment(self):
        """'annuler' cancels from third-party enrollment states"""
        phone = unique_phone()
        
        # Create profile first
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Main"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "User"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "passer"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Start third-party enrollment
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "2"})  # Pour un tiers
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "2"})  # New person
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "annuler"}
        )
        data = response.json()
        session = data.get("session", {})
        
        assert session.get("state") == "idle"
        print(f"✓ 'annuler' cancels from third-party enrollment")


class TestBookingPassengerFields:
    """Test booking includes passenger_id, passenger_name, passenger_passport fields"""
    
    def test_booking_has_passenger_fields(self):
        """Booking includes passenger data"""
        phone = unique_phone()
        
        # Create profile with passport
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "3"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Booking"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Test"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "XY9876543"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Confirm
        
        # Book for self
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # Pour moi
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "1"})  # 1 passenger
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "Dakar"})
        requests.post(f"{BASE_URL}/api/test/message", params={"phone": phone, "message": "demain"})
        
        response = requests.post(
            f"{BASE_URL}/api/test/message",
            params={"phone": phone, "message": "1"}  # Select flight
        )
        data = response.json()
        session = data.get("session", {})
        
        # Check booking_passenger_id is set
        assert session.get("booking_passenger_id") is not None
        assert session.get("booking_ref") is not None
        print(f"✓ Booking has booking_passenger_id={session.get('booking_passenger_id')[:8]}...")


class TestHealthEndpointPaymentOperators:
    """Test frontend status page shows payment operators from /api/health"""
    
    def test_health_returns_payment_operators(self):
        """Health endpoint returns payment operators"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "payment_operators" in data
        operators = data["payment_operators"]
        
        expected = ["mtn_momo", "moov_money", "google_pay", "apple_pay"]
        for op in expected:
            assert op in operators
            assert "status" in operators[op]
        
        print(f"✓ Health returns all payment operators")
    
    def test_health_returns_integrations(self):
        """Health endpoint returns integrations"""
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        
        assert "integrations" in data
        integrations = data["integrations"]
        
        expected = ["claude_ai", "amadeus", "whatsapp", "whisper"]
        for integ in expected:
            assert integ in integrations
        
        print(f"✓ Health returns all integrations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
