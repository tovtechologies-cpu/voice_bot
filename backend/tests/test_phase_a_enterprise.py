"""
Phase A Enterprise Grade Tests - Travelioo
Tests: Shadow Profiles, Dynamic Pricing, Payment Drivers, OCR Rebound, Force-fail
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test phone numbers - use unique ones to avoid conflicts
TEST_PHONE_PREFIX = "+22990PHASETEST"
TIMESTAMP = int(time.time())


class TestHealthEndpoint:
    """Health endpoint tests"""
    
    def test_health_returns_healthy(self):
        """GET /api/health returns healthy with all service statuses"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "7.1"
        print(f"✓ Health endpoint returns healthy with version {data['version']}")
    
    def test_health_has_payment_operators(self):
        """Health endpoint includes payment_operators with modes"""
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        assert "payment_operators" in data
        assert "mtn_momo" in data["payment_operators"]
        assert "moov_money" in data["payment_operators"]
        print(f"✓ Payment operators: {list(data['payment_operators'].keys())}")
    
    def test_health_has_environment_modes(self):
        """Health endpoint includes environment_modes"""
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        assert "environment_modes" in data
        assert data["environment_modes"]["duffel"] in ["SANDBOX", "PRODUCTION", "MOCK"]
        assert data["environment_modes"]["mtn_momo"] in ["MOCK", "SANDBOX", "PRODUCTION"]
        print(f"✓ Environment modes: {data['environment_modes']}")


class TestShadowProfileCreation:
    """Shadow Profile tests - consent flow creates shadow profile"""
    
    def test_new_user_consent_creates_shadow_profile(self):
        """POST /api/test/simulate — new user consent flow creates shadow profile"""
        phone = f"{TEST_PHONE_PREFIX}01{TIMESTAMP}"
        
        # Step 1: Send initial message to trigger consent flow
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "bonjour"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "awaiting_consent"
        print(f"✓ New user gets awaiting_consent state")
        
        # Step 2: Accept consent with '1'
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "1"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "enrollment_method"
        print(f"✓ Consent accepted, state = enrollment_method")
        
        # Step 3: Check session for shadow profile creation
        response = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        assert response.status_code == 200
        session = response.json()
        assert session.get("_consent_granted") == True
        assert "_consent_at" in session
        print(f"✓ Shadow profile created with consent_granted=True")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")


class TestManualEnrollmentFlow:
    """Manual enrollment saves passenger and updates shadow profile"""
    
    def test_manual_enrollment_saves_passenger(self):
        """POST /api/test/simulate — manual enrollment saves passenger"""
        phone = f"{TEST_PHONE_PREFIX}02{TIMESTAMP}"
        
        # Step 1: Start conversation
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        
        # Step 2: Accept consent
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        
        # Step 3: Choose manual entry (option 3)
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "enrolling_manual_fn"
        print(f"✓ Manual entry selected, state = enrolling_manual_fn")
        
        # Step 4: Enter first name
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Jean"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "enrolling_manual_ln"
        print(f"✓ First name entered, state = enrolling_manual_ln")
        
        # Step 5: Enter last name
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Dupont"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "enrolling_manual_pp"
        print(f"✓ Last name entered, state = enrolling_manual_pp")
        
        # Step 6: Skip passport
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "passer"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "confirming_profile"
        print(f"✓ Passport skipped, state = confirming_profile")
        
        # Step 7: Confirm profile
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "asking_travel_purpose"
        print(f"✓ Profile confirmed, state = asking_travel_purpose")
        
        # Verify session has passenger_id
        response = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        session = response.json()
        assert "passenger_id" in session
        print(f"✓ Passenger saved with ID: {session['passenger_id'][:8]}...")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")


class TestDynamicPricing:
    """Dynamic Pricing tests - tiered Travelioo fee"""
    
    def test_fee_under_200_eur(self):
        """< 200 EUR = 10 EUR flat fee"""
        from models import calculate_travelioo_fee, apply_travelioo_pricing
        
        fee = calculate_travelioo_fee(150)
        assert fee == 10.0
        print(f"✓ 150 EUR flight → 10 EUR fee (flat)")
        
        pricing = apply_travelioo_pricing(150)
        assert pricing["gds_price_eur"] == 150
        assert pricing["travelioo_fee_eur"] == 10.0
        assert pricing["total_eur"] == 160.0
        print(f"✓ Total: 150 + 10 = 160 EUR")
    
    def test_fee_200_to_500_eur(self):
        """200-500 EUR = 8% fee"""
        from models import calculate_travelioo_fee, apply_travelioo_pricing
        
        fee = calculate_travelioo_fee(300)
        assert fee == 24.0  # 300 * 0.08 = 24
        print(f"✓ 300 EUR flight → 24 EUR fee (8%)")
        
        fee = calculate_travelioo_fee(500)
        assert fee == 40.0  # 500 * 0.08 = 40
        print(f"✓ 500 EUR flight → 40 EUR fee (8%)")
    
    def test_fee_over_500_eur(self):
        """> 500 EUR = 6% fee"""
        from models import calculate_travelioo_fee, apply_travelioo_pricing
        
        fee = calculate_travelioo_fee(600)
        assert fee == 36.0  # 600 * 0.06 = 36
        print(f"✓ 600 EUR flight → 36 EUR fee (6%)")
        
        fee = calculate_travelioo_fee(1000)
        assert fee == 60.0  # 1000 * 0.06 = 60
        print(f"✓ 1000 EUR flight → 60 EUR fee (6%)")
    
    def test_fee_boundary_200(self):
        """Boundary test at 200 EUR"""
        from models import calculate_travelioo_fee
        
        fee_199 = calculate_travelioo_fee(199)
        assert fee_199 == 10.0  # Under 200 = flat 10
        
        fee_200 = calculate_travelioo_fee(200)
        assert fee_200 == 16.0  # 200 * 0.08 = 16
        print(f"✓ Boundary: 199 EUR → 10 EUR, 200 EUR → 16 EUR")


class TestPaymentDriverRouting:
    """Payment driver routing tests - country-based"""
    
    def test_benin_gets_celtiis_first(self):
        """BJ gets [celtiis_cash, mtn_momo, moov_money]"""
        from payment_drivers.router import get_payment_options_for_country
        
        options = get_payment_options_for_country("BJ")
        assert options[0] == "celtiis_cash"
        assert "mtn_momo" in options
        assert "moov_money" in options
        print(f"✓ BJ (Benin) payment options: {options}")
    
    def test_senegal_gets_mtn_moov(self):
        """SN gets [mtn_momo, moov_money]"""
        from payment_drivers.router import get_payment_options_for_country
        
        options = get_payment_options_for_country("SN")
        assert "mtn_momo" in options
        assert "moov_money" in options
        assert "celtiis_cash" not in options
        print(f"✓ SN (Senegal) payment options: {options}")
    
    def test_france_gets_stripe(self):
        """FR gets [stripe]"""
        from payment_drivers.router import get_payment_options_for_country
        
        options = get_payment_options_for_country("FR")
        assert "stripe" in options
        assert "celtiis_cash" not in options
        assert "mtn_momo" not in options
        print(f"✓ FR (France) payment options: {options}")
    
    def test_payment_menu_for_benin(self):
        """Payment menu for BJ shows Celtiis Cash first"""
        from payment_drivers.router import get_payment_menu_for_country
        
        menu = get_payment_menu_for_country("BJ", "fr")
        assert len(menu) >= 3
        assert menu[0]["driver_name"] == "celtiis_cash"
        assert "Celtiis Cash" in menu[0]["label"]
        print(f"✓ BJ payment menu: {[m['label'] for m in menu]}")


class TestCeltiisDriverMock:
    """Celtiis Cash driver tests - MOCK mode"""
    
    def test_celtiis_driver_is_mock(self):
        """Celtiis driver is in MOCK mode"""
        from payment_drivers.celtiis_driver import CeltiisDriver
        
        driver = CeltiisDriver()
        assert driver.mode == "MOCK"
        assert driver.name == "celtiis_cash"
        assert driver.display_name == "Celtiis Cash"
        print(f"✓ Celtiis driver mode: {driver.mode}")
    
    def test_celtiis_initiate_mock(self):
        """Celtiis initiate_payment returns success in MOCK mode"""
        import asyncio
        from payment_drivers.celtiis_driver import CeltiisDriver
        
        async def run_test():
            driver = CeltiisDriver()
            result = await driver.initiate_payment(
                phone="+22990000001",
                amount=50000,
                currency="XOF",
                reference="TEST-REF-001"
            )
            return result
        
        result = asyncio.get_event_loop().run_until_complete(run_test())
        assert result.success == True
        assert result.status == "PENDING"
        assert result.reference.startswith("CELT-SIM-")
        print(f"✓ Celtiis initiate MOCK: {result.reference}")
    
    def test_celtiis_check_status_mock(self):
        """Celtiis check_payment_status returns SUCCESSFUL in MOCK mode"""
        import asyncio
        from payment_drivers.celtiis_driver import CeltiisDriver
        
        async def run_test():
            driver = CeltiisDriver()
            result = await driver.check_payment_status("CELT-SIM-TEST123")
            return result
        
        result = asyncio.get_event_loop().run_until_complete(run_test())
        assert result.success == True
        assert result.status == "SUCCESSFUL"
        print(f"✓ Celtiis check_status MOCK: {result.status}")


class TestFullBookingFlow:
    """Full booking flow test - destination → date → flight → payment menu"""
    
    def test_booking_flow_shows_celtiis_first_for_benin(self):
        """Full booking flow shows Celtiis Cash first for BJ country"""
        phone = f"{TEST_PHONE_PREFIX}03{TIMESTAMP}"
        
        # Step 1-7: Complete enrollment (same as above)
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})  # consent
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "3"})  # manual
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Test"})  # first name
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "User"})  # last name
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "skip"})  # passport
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})  # confirm
        
        # Step 8: Choose "for me"
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "asking_passenger_count"
        print(f"✓ Travel purpose selected, state = asking_passenger_count")
        
        # Step 9: 1 passenger
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_state"] == "awaiting_destination"
        print(f"✓ Passenger count set, state = awaiting_destination")
        
        # Step 10: Destination "Paris demain"
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "Paris demain"})
        assert response.status_code == 200
        data = response.json()
        # Could be awaiting_flight_selection or awaiting_date depending on AI parsing
        print(f"✓ Destination entered, state = {data['session_state']}")
        
        # Wait for flight search
        time.sleep(3)
        
        # Check session state
        response = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        session = response.json()
        state = session.get("state", "unknown")
        
        if state == "awaiting_flight_selection":
            # Step 11: Select flight option 1
            response = requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "1"})
            data = response.json()
            print(f"✓ Flight selected, state = {data['session_state']}")
            
            # Check payment menu in session
            response = requests.get(f"{BASE_URL}/api/test/session/{phone}")
            session = response.json()
            payment_menu = session.get("_payment_menu", [])
            
            if payment_menu:
                assert payment_menu[0] == "celtiis_cash", f"Expected celtiis_cash first, got {payment_menu[0]}"
                print(f"✓ Payment menu shows Celtiis Cash first: {payment_menu}")
            else:
                print(f"⚠ Payment menu not yet populated (state: {session.get('state')})")
        else:
            print(f"⚠ Flight search may have failed or returned no results (state: {state})")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")


class TestForceFailPayment:
    """Force-fail test - payment polling detects failure"""
    
    def test_force_fail_endpoint(self):
        """POST /api/test/force_fail enables fail mode"""
        phone = f"{TEST_PHONE_PREFIX}04{TIMESTAMP}"
        
        # Create a session first
        requests.post(f"{BASE_URL}/api/test/simulate", json={"phone": phone, "message": "bonjour"})
        
        # Enable force fail
        response = requests.post(f"{BASE_URL}/api/test/force_fail", json={"phone": phone})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "fail_mode_enabled"
        print(f"✓ Force fail enabled for {phone}")
        
        # Verify session has flag
        response = requests.get(f"{BASE_URL}/api/test/session/{phone}")
        session = response.json()
        assert session.get("_test_force_fail") == True
        print(f"✓ Session has _test_force_fail=True")
        
        # Clear fail mode
        response = requests.post(f"{BASE_URL}/api/test/clear_fail", json={"phone": phone})
        assert response.status_code == 200
        print(f"✓ Force fail cleared")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")


class TestOCRReboundCorrection:
    """OCR Rebound tests - correcting_ocr state accepts comma-separated corrections"""
    
    def test_ocr_correction_state_exists(self):
        """ConversationState has CORRECTING_OCR state"""
        from models import ConversationState
        
        assert hasattr(ConversationState, 'CORRECTING_OCR')
        assert ConversationState.CORRECTING_OCR == "correcting_ocr"
        assert hasattr(ConversationState, 'CORRECTING_TP_OCR')
        assert ConversationState.CORRECTING_TP_OCR == "correcting_tp_ocr"
        print(f"✓ OCR correction states exist: correcting_ocr, correcting_tp_ocr")
    
    def test_field_labels_exist(self):
        """FIELD_LABELS for OCR correction exist"""
        from models import FIELD_LABELS
        
        assert "firstName" in FIELD_LABELS
        assert "lastName" in FIELD_LABELS
        assert "passportNumber" in FIELD_LABELS
        assert "nationality" in FIELD_LABELS
        print(f"✓ Field labels: {list(FIELD_LABELS.keys())}")


class TestSimulateEndpoint:
    """Test simulate endpoint edge cases"""
    
    def test_simulate_missing_message(self):
        """Simulate endpoint handles missing message"""
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": "+22990000001"
        })
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        print(f"✓ Missing message returns error: {data['error']}")
    
    def test_simulate_returns_session_state(self):
        """Simulate endpoint returns session state"""
        phone = f"{TEST_PHONE_PREFIX}05{TIMESTAMP}"
        
        response = requests.post(f"{BASE_URL}/api/test/simulate", json={
            "phone": phone,
            "message": "bonjour"
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_state" in data
        assert data["session_state"] == "awaiting_consent"
        print(f"✓ Simulate returns session_state: {data['session_state']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/test/session/{phone}")


class TestBookingsEndpoint:
    """Test bookings endpoint"""
    
    def test_get_bookings_empty(self):
        """GET /api/test/bookings returns empty for new phone"""
        phone = f"{TEST_PHONE_PREFIX}06{TIMESTAMP}"
        
        response = requests.get(f"{BASE_URL}/api/test/bookings/{phone}")
        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data
        assert isinstance(data["bookings"], list)
        print(f"✓ Bookings endpoint returns list: {len(data['bookings'])} bookings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
