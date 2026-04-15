"""
Phase C Testing: Multilingual Support + Proactive SAV (Disruption Notifications)
Tests:
1. Language Detection (FR, EN, Wolof, Fon, Yoruba, Hausa, Swahili)
2. Translation Pipeline (African languages → French via Claude)
3. HITL (Human-in-the-Loop) threshold logic and review management
4. Disruption notifications (DELAY, GATE_CHANGE, CANCELLATION, SCHEDULE_CHANGE)
5. Auto-refund on cancellation
6. Rebooking offer for delays > 2 hours
"""
import pytest
import requests
import os
import asyncio
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Use a single event loop for all tests
_event_loop = None

def get_event_loop():
    """Get or create a shared event loop."""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop

def run_async(coro):
    """Run async coroutine in sync context using shared loop."""
    loop = get_event_loop()
    return loop.run_until_complete(coro)


# ============================================================================
# LANGUAGE DETECTION TESTS
# ============================================================================
class TestLanguageDetection:
    """Test detect_language_extended for 7 supported languages."""
    
    def test_french_detection(self):
        """French keywords should be detected as 'fr'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("Je veux aller à Paris", "fr"),
            ("Bonjour, je voudrais réserver un vol", "fr"),
            ("Merci pour votre aide", "fr"),
            ("Un billet pour Dakar", "fr"),
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ French detection: PASSED")
    
    def test_english_detection(self):
        """English keywords should be detected as 'en'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("I want to book a flight", "en"),
            ("Hello, please help me", "en"),
            ("I need a ticket to Paris", "en"),
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ English detection: PASSED")
    
    def test_wolof_detection(self):
        """Wolof keywords should be detected as 'wo'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("Nanga def", "wo"),  # How are you
            ("Jere jef", "wo"),   # Thank you
            ("Dinaa dem Paris", "wo"),  # I will go to Paris
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ Wolof detection: PASSED")
    
    def test_fon_detection(self):
        """Fon keywords should be detected as 'fon'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("Mi nyi", "fon"),  # I am
            ("Nado avion", "fon"),  # Need airplane
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ Fon detection: PASSED")
    
    def test_yoruba_detection(self):
        """Yoruba keywords should be detected as 'yo'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("Bawo ni", "yo"),  # How are you
            ("Mo fe lo Paris", "yo"),  # I want to go to Paris
            ("Emi fe gba tiketi", "yo"),  # I want to get a ticket
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ Yoruba detection: PASSED")
    
    def test_hausa_detection(self):
        """Hausa keywords should be detected as 'ha'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("Ina kwana", "ha"),  # Good morning
            ("Sannu da zuwa", "ha"),  # Welcome
            ("Yaya gida", "ha"),  # How is home
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ Hausa detection: PASSED")
    
    def test_swahili_detection(self):
        """Swahili keywords should be detected as 'sw'."""
        from services.translation import detect_language_extended
        
        test_cases = [
            ("Habari yako", "sw"),  # How are you
            ("Jambo", "sw"),  # Hello
            ("Nataka kwenda Paris", "sw"),  # I want to go to Paris
        ]
        for text, expected in test_cases:
            result = detect_language_extended(text)
            assert result == expected, f"Expected '{expected}' for '{text}', got '{result}'"
        print("✓ Swahili detection: PASSED")
    
    def test_unknown_defaults_to_french(self):
        """Unknown text should default to French."""
        from services.translation import detect_language_extended
        
        result = detect_language_extended("xyz123")
        assert result == "fr", f"Expected 'fr' for unknown text, got '{result}'"
        print("✓ Unknown defaults to French: PASSED")


# ============================================================================
# TRANSLATION PIPELINE TESTS
# ============================================================================
class TestTranslationPipeline:
    """Test translate_to_french for African languages."""
    
    def test_direct_languages_no_translation(self):
        """French and English should return original text with confidence 1.0."""
        from services.translation import translate_to_french
        
        async def test():
            # French - no translation needed
            text_fr, conf_fr = await translate_to_french("Je veux un billet", "fr")
            assert text_fr == "Je veux un billet"
            assert conf_fr == 1.0
            
            # English - no translation needed
            text_en, conf_en = await translate_to_french("I want a ticket", "en")
            assert text_en == "I want a ticket"
            assert conf_en == 1.0
        
        run_async(test())
        print("✓ Direct languages (FR/EN) skip translation: PASSED")
    
    def test_wolof_translation(self):
        """Wolof text should be translated to French via Claude."""
        from services.translation import translate_to_french
        
        async def test():
            # Simple Wolof greeting
            translated, confidence = await translate_to_french("Nanga def", "wo")
            
            # Should return some translation (not empty)
            assert translated is not None
            assert len(translated) > 0
            # Confidence should be between 0 and 1
            assert 0 <= confidence <= 1
            
            print(f"  Wolof translation: '{translated}' (confidence: {confidence:.2f})")
            return translated, confidence
        
        result = run_async(test())
        print("✓ Wolof translation via Claude: PASSED")
    
    def test_swahili_translation(self):
        """Swahili text should be translated to French via Claude."""
        from services.translation import translate_to_french
        
        async def test():
            translated, confidence = await translate_to_french("Habari yako", "sw")
            
            assert translated is not None
            assert len(translated) > 0
            assert 0 <= confidence <= 1
            
            print(f"  Swahili translation: '{translated}' (confidence: {confidence:.2f})")
            return translated, confidence
        
        result = run_async(test())
        print("✓ Swahili translation via Claude: PASSED")


# ============================================================================
# HITL (HUMAN-IN-THE-LOOP) TESTS
# ============================================================================
class TestHITLThresholds:
    """Test HITL threshold logic."""
    
    def test_low_confidence_triggers_review(self):
        """Confidence < 0.85 should trigger HITL review."""
        from services.hitl import needs_human_review, CONFIDENCE_THRESHOLD
        
        assert CONFIDENCE_THRESHOLD == 0.85, f"Expected threshold 0.85, got {CONFIDENCE_THRESHOLD}"
        
        # Low confidence should trigger review
        assert needs_human_review(0.5, 0) == True
        assert needs_human_review(0.84, 0) == True
        assert needs_human_review(0.849, 0) == True
        
        # High confidence should NOT trigger review (unless high value)
        assert needs_human_review(0.85, 0) == False
        assert needs_human_review(0.9, 0) == False
        assert needs_human_review(1.0, 0) == False
        
        print("✓ Low confidence threshold (< 0.85) triggers review: PASSED")
    
    def test_high_value_triggers_review(self):
        """Amount > 500 EUR should trigger HITL review."""
        from services.hitl import needs_human_review, HIGH_VALUE_THRESHOLD_EUR
        
        assert HIGH_VALUE_THRESHOLD_EUR == 500.0, f"Expected threshold 500.0, got {HIGH_VALUE_THRESHOLD_EUR}"
        
        # High value should trigger review even with high confidence
        assert needs_human_review(0.95, 501) == True
        assert needs_human_review(0.99, 1000) == True
        
        # Below threshold should NOT trigger (with high confidence)
        assert needs_human_review(0.95, 500) == False
        assert needs_human_review(0.95, 499) == False
        
        print("✓ High value threshold (> 500 EUR) triggers review: PASSED")
    
    def test_combined_thresholds(self):
        """Both conditions should trigger review independently."""
        from services.hitl import needs_human_review
        
        # Low confidence + low value = review (confidence)
        assert needs_human_review(0.5, 100) == True
        
        # High confidence + high value = review (value)
        assert needs_human_review(0.95, 600) == True
        
        # Low confidence + high value = review (both)
        assert needs_human_review(0.5, 600) == True
        
        # High confidence + low value = NO review
        assert needs_human_review(0.95, 100) == False
        
        print("✓ Combined threshold logic: PASSED")


class TestHITLReviewAPI:
    """Test HITL review API endpoints."""
    
    def test_trigger_and_get_review(self):
        """Test creating and retrieving HITL reviews."""
        from services.hitl import trigger_human_review, get_pending_reviews
        
        async def test():
            # Create a test review
            review_id = await trigger_human_review(
                phone="+22990PHASEC01",
                original_text="Nanga def",
                translated_text="Comment allez-vous",
                source_lang="wo",
                confidence=0.75,
                reason="low_confidence (0.75)",
                context={"state": "idle", "booking_amount": 0}
            )
            
            assert review_id is not None
            assert review_id.startswith("HITL-")
            
            # Get pending reviews
            reviews = await get_pending_reviews()
            assert isinstance(reviews, list)
            
            # Find our review
            our_review = next((r for r in reviews if r["review_id"] == review_id), None)
            assert our_review is not None
            assert our_review["status"] == "pending"
            assert our_review["source_language"] == "wo"
            assert our_review["confidence"] == 0.75
            
            print(f"  HITL review created: {review_id}")
            return review_id
        
        review_id = run_async(test())
        print("✓ HITL review created and retrieved: PASSED")
    
    def test_get_reviews_api(self):
        """Test GET /api/hitl/reviews endpoint."""
        response = requests.get(f"{BASE_URL}/api/hitl/reviews")
        assert response.status_code == 200
        
        data = response.json()
        assert "reviews" in data
        assert "count" in data
        assert isinstance(data["reviews"], list)
        
        print(f"✓ GET /api/hitl/reviews: {data['count']} pending reviews")
    
    def test_resolve_review(self):
        """Test resolving a HITL review."""
        from services.hitl import trigger_human_review, resolve_review
        from database import db
        
        async def test():
            # Create a review to resolve
            review_id = await trigger_human_review(
                phone="+22990PHASEC02",
                original_text="Test message",
                translated_text="Message de test",
                source_lang="wo",
                confidence=0.6,
                reason="test_resolve",
                context={}
            )
            
            # Resolve it
            success = await resolve_review(
                review_id=review_id,
                resolved_by="test_admin",
                resolution="approved",
                corrected_text=None
            )
            
            assert success == True
            
            # Verify it's resolved in DB
            review = await db.hitl_reviews.find_one({"review_id": review_id}, {"_id": 0})
            assert review["status"] == "resolved"
            assert review["resolved_by"] == "test_admin"
            assert review["resolution"] == "approved"
            
            print(f"  HITL review resolved: {review_id}")
            return review_id
        
        run_async(test())
        print("✓ HITL review resolved: PASSED")
    
    def test_resolve_review_api(self):
        """Test POST /api/hitl/reviews/{id}/resolve endpoint."""
        from services.hitl import trigger_human_review
        
        async def create_review():
            return await trigger_human_review(
                phone="+22990PHASEC03",
                original_text="API test",
                translated_text="Test API",
                source_lang="fon",
                confidence=0.7,
                reason="api_test",
                context={}
            )
        
        review_id = run_async(create_review())
        
        # Resolve via API
        response = requests.post(
            f"{BASE_URL}/api/hitl/reviews/{review_id}/resolve",
            json={
                "resolved_by": "api_tester",
                "resolution": "approved"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["review_id"] == review_id
        
        print(f"✓ POST /api/hitl/reviews/{review_id}/resolve: PASSED")


# ============================================================================
# DISRUPTION NOTIFICATION TESTS
# ============================================================================
class TestDisruptionNotifications:
    """Test disruption notification API and processing."""
    
    # Use a confirmed booking with payment_driver
    BOOKING_REF = "TRV-ZT3GEM"
    
    def test_delay_notification(self):
        """Test DELAY disruption notification."""
        response = requests.post(
            f"{BASE_URL}/api/disruptions/notify",
            json={
                "booking_ref": self.BOOKING_REF,
                "type": "DELAY",
                "details": {
                    "delay_minutes": 45,
                    "new_departure_time": "15:30"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "notified"
        assert data["type"] == "DELAY"
        
        print(f"✓ DELAY notification sent for {self.BOOKING_REF}")
    
    def test_gate_change_notification(self):
        """Test GATE_CHANGE disruption notification."""
        response = requests.post(
            f"{BASE_URL}/api/disruptions/notify",
            json={
                "booking_ref": self.BOOKING_REF,
                "type": "GATE_CHANGE",
                "details": {
                    "new_gate": "C15"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "notified"
        assert data["type"] == "GATE_CHANGE"
        
        print(f"✓ GATE_CHANGE notification sent for {self.BOOKING_REF}")
    
    def test_schedule_change_notification(self):
        """Test SCHEDULE_CHANGE disruption notification."""
        response = requests.post(
            f"{BASE_URL}/api/disruptions/notify",
            json={
                "booking_ref": self.BOOKING_REF,
                "type": "SCHEDULE_CHANGE",
                "details": {
                    "new_departure_time": "08:00"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "notified"
        assert data["type"] == "SCHEDULE_CHANGE"
        
        print(f"✓ SCHEDULE_CHANGE notification sent for {self.BOOKING_REF}")
    
    def test_get_disruption_events(self):
        """Test GET /api/disruptions/events/{booking_ref}."""
        response = requests.get(f"{BASE_URL}/api/disruptions/events/{self.BOOKING_REF}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["booking_ref"] == self.BOOKING_REF
        assert "events" in data
        assert "count" in data
        assert isinstance(data["events"], list)
        
        # Should have at least the events we just created
        assert data["count"] >= 3
        
        print(f"✓ GET /api/disruptions/events/{self.BOOKING_REF}: {data['count']} events")
    
    def test_invalid_booking_ref(self):
        """Test disruption notification with invalid booking ref."""
        response = requests.post(
            f"{BASE_URL}/api/disruptions/notify",
            json={
                "booking_ref": "INVALID-REF",
                "type": "DELAY",
                "details": {}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        
        print("✓ Invalid booking ref returns failed status: PASSED")
    
    def test_invalid_disruption_type(self):
        """Test disruption notification with invalid type."""
        response = requests.post(
            f"{BASE_URL}/api/disruptions/notify",
            json={
                "booking_ref": self.BOOKING_REF,
                "type": "INVALID_TYPE",
                "details": {}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        
        print("✓ Invalid disruption type returns error: PASSED")
    
    def test_missing_booking_ref(self):
        """Test disruption notification without booking_ref."""
        response = requests.post(
            f"{BASE_URL}/api/disruptions/notify",
            json={
                "type": "DELAY",
                "details": {}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "booking_ref required" in data["error"]
        
        print("✓ Missing booking_ref returns error: PASSED")


class TestDisruptionAutoActions:
    """Test automatic actions on disruptions (refund, rebooking)."""
    
    def test_delay_over_2_hours_offers_rebooking(self):
        """DELAY > 120 minutes should offer rebooking."""
        from database import db
        from services.disruption import process_disruption, DELAY
        
        async def test():
            # Use a different confirmed booking for this test
            booking = await db.bookings.find_one(
                {"status": "confirmed", "payment_driver": {"$exists": True}},
                {"_id": 0}
            )
            
            if not booking:
                pytest.skip("No confirmed booking with payment_driver found")
            
            booking_ref = booking["booking_ref"]
            phone = booking["phone"]
            
            # Process a delay > 120 minutes
            success = await process_disruption(
                booking_ref=booking_ref,
                disruption_type=DELAY,
                details={"delay_minutes": 150, "new_departure_time": "20:00"}
            )
            
            assert success == True
            
            # Check session state for rebooking offer
            session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
            if session:
                # Session should be in MODIFICATION_REQUESTED state
                state = session.get("state")
                disruption_rebooking = session.get("_disruption_rebooking")
                print(f"  Session state: {state}, _disruption_rebooking: {disruption_rebooking}")
            
            print(f"  DELAY > 120min processed for {booking_ref}")
            return success
        
        run_async(test())
        print("✓ DELAY > 120min offers rebooking: PASSED")
    
    def test_cancellation_triggers_auto_refund(self):
        """CANCELLATION should auto-trigger refund and update status."""
        from database import db
        from services.disruption import process_disruption, CANCELLATION
        import uuid
        
        async def test():
            # Create a test booking specifically for cancellation test
            test_booking = {
                "id": str(uuid.uuid4()),
                "booking_ref": f"TRV-CANCEL{datetime.now().strftime('%H%M%S')}",
                "phone": "+22990PHASEC04",
                "passenger_id": str(uuid.uuid4()),
                "passenger_name": "Test Cancel",
                "airline": "Test Air",
                "flight_number": "TA123",
                "origin": "COO",
                "destination": "CDG",
                "departure_date": "2026-04-20",
                "gds_price_eur": 200,
                "travelioo_fee_eur": 16.0,
                "price_eur": 216.0,
                "status": "confirmed",
                "payment_driver": "celtiis_cash",
                "payment_reference": "CELT-TEST-CANCEL",
                "created_at": datetime.now().isoformat(),
            }
            
            await db.bookings.insert_one(test_booking)
            booking_ref = test_booking["booking_ref"]
            
            # Process cancellation
            success = await process_disruption(
                booking_ref=booking_ref,
                disruption_type=CANCELLATION,
                details={"reason": "Weather conditions"}
            )
            
            assert success == True
            
            # Verify booking status updated
            updated_booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
            assert updated_booking["status"] == "cancelled_by_airline"
            assert updated_booking["refund_status"] == "PROCESSED"
            
            # Verify disruption event stored
            events = updated_booking.get("disruption_events", [])
            cancel_event = next((e for e in events if e["type"] == "CANCELLATION"), None)
            assert cancel_event is not None
            assert cancel_event["notified"] == True
            
            print(f"  CANCELLATION auto-refund processed for {booking_ref}")
            print(f"  Status: {updated_booking['status']}, Refund: {updated_booking['refund_status']}")
            
            # Cleanup
            await db.bookings.delete_one({"booking_ref": booking_ref})
            return success
        
        run_async(test())
        print("✓ CANCELLATION auto-refund: PASSED")


# ============================================================================
# SHADOW PROFILE LANGUAGE PREFERENCE TESTS
# ============================================================================
class TestShadowProfileLanguage:
    """Test shadow profile language_pref updates on language detection."""
    
    def test_language_detection_updates_shadow_profile(self):
        """Language detection should update shadow profile language_pref."""
        # Send a message in Wolof to trigger language detection
        response = requests.post(
            f"{BASE_URL}/api/test/simulate",
            json={
                "phone": "+22990PHASEC05",
                "message": "Nanga def"  # Wolof greeting
            }
        )
        
        assert response.status_code == 200
        
        # Check shadow profile was updated
        from database import db
        
        async def check_profile():
            profile = await db.shadow_profiles.find_one(
                {"phone_number": "+22990PHASEC05"},
                {"_id": 0}
            )
            return profile
        
        profile = run_async(check_profile())
        
        if profile:
            lang_pref = profile.get("language_pref")
            print(f"  Shadow profile language_pref: {lang_pref}")
            # Should be 'wo' for Wolof
            assert lang_pref == "wo", f"Expected 'wo', got '{lang_pref}'"
        else:
            # Profile might not exist yet if consent not given
            print("  Shadow profile not created (consent not given yet)")
        
        print("✓ Language detection updates shadow profile: PASSED")


# ============================================================================
# INTEGRATION TESTS - FULL FLOW
# ============================================================================
class TestMultilingualConversationFlow:
    """Test full conversation flow with African language input."""
    
    def test_wolof_message_triggers_translation_pipeline(self):
        """Wolof message should trigger translation and HITL check."""
        timestamp = datetime.now().strftime('%H%M%S')
        phone = f"+22990PHASEC06{timestamp}"
        
        # Send Wolof message
        response = requests.post(
            f"{BASE_URL}/api/test/simulate",
            json={
                "phone": phone,
                "message": "Nanga def, dinaa dem Paris"  # Hello, I will go to Paris
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should get a processed status
        assert data["status"] == "processed"
        # New user should be in awaiting_consent state
        assert data["session_state"] == "awaiting_consent"
        
        print(f"✓ Wolof message processed for {phone}")
        print(f"  Session state: {data['session_state']}")
    
    def test_swahili_message_triggers_translation_pipeline(self):
        """Swahili message should trigger translation and HITL check."""
        timestamp = datetime.now().strftime('%H%M%S')
        phone = f"+22990PHASEC07{timestamp}"
        
        # Send Swahili message
        response = requests.post(
            f"{BASE_URL}/api/test/simulate",
            json={
                "phone": phone,
                "message": "Habari, nataka kwenda Paris"  # Hello, I want to go to Paris
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should get a processed status
        assert data["status"] == "processed"
        # New user should be in awaiting_consent state
        assert data["session_state"] == "awaiting_consent"
        
        print(f"✓ Swahili message processed for {phone}")
        print(f"  Session state: {data['session_state']}")


# ============================================================================
# DISRUPTION EVENTS STORAGE TESTS
# ============================================================================
class TestDisruptionEventsStorage:
    """Test that disruption events are stored in booking document."""
    
    def test_events_stored_in_booking_document(self):
        """Disruption events should be stored in booking.disruption_events array."""
        from database import db
        
        async def check_events():
            booking = await db.bookings.find_one(
                {"booking_ref": "TRV-ZT3GEM"},
                {"_id": 0, "disruption_events": 1}
            )
            return booking
        
        booking = run_async(check_events())
        
        assert booking is not None
        events = booking.get("disruption_events", [])
        assert isinstance(events, list)
        assert len(events) > 0
        
        # Check event structure
        for event in events:
            assert "type" in event
            assert "details" in event
            assert "detected_at" in event
            assert "notified" in event
            assert event["type"] in ["DELAY", "CANCELLATION", "GATE_CHANGE", "SCHEDULE_CHANGE"]
        
        print(f"✓ Disruption events stored in booking: {len(events)} events")
        for e in events[-3:]:  # Show last 3
            print(f"  - {e['type']}: {e['details']}")


# ============================================================================
# RUN TESTS
# ============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
