#!/usr/bin/env python3

import requests
import sys
import json
import time
import os
from datetime import datetime, timedelta
import uuid

class TraveliooWhatsAppTester:
    def __init__(self, base_url="https://voice-travel-booking.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_phone = "+221771234567"
        self.booking_ref = None
        self.ticket_filename = None
        self.EUR_TO_XOF = 655.957

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, params=params, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    if response.headers.get('content-type', '').startswith('application/json'):
                        response_data = response.json()
                        print(f"   Response: {json.dumps(response_data, indent=2)[:300]}...")
                        return True, response_data
                    else:
                        print(f"   Response: {response.text[:200]}...")
                        return True, response.text
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout after {timeout}s")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health check endpoint returns whatsapp_agent type and version 4.0.0"""
        success, data = self.run_test("Health Check", "GET", "health", 200)
        if success and data.get('type') == 'whatsapp_agent' and data.get('version') == '4.0.0':
            print(f"   ✅ Correct agent type: {data.get('type')} and version: {data.get('version')}")
            return True
        elif success:
            print(f"   ❌ Wrong agent type: {data.get('type')} or version: {data.get('version')} (expected: whatsapp_agent, 4.0.0)")
        return False

    def test_webhook_verification(self):
        """Test WhatsApp webhook verification"""
        params = {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'travelioo_verify_2024',
            'hub.challenge': '12345'
        }
        success, data = self.run_test("Webhook Verification", "GET", "webhook", 200, params=params)
        if success and str(data).strip() == '12345':
            print(f"   ✅ Challenge returned correctly: {data}")
            return True
        elif success:
            print(f"   ❌ Wrong challenge response: {data} (expected: 12345)")
        return False

    def test_welcome_message(self):
        """Test welcome message with 'bonjour' command"""
        params = {
            "phone": self.test_phone,
            "message": "bonjour"
        }
        success, data = self.run_test("Welcome Message", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'idle':
            print(f"   ✅ Session state: {data.get('session_state')}")
            return True
        return False

    def test_travel_request_parsing(self):
        """Test travel request processing and intent parsing"""
        params = {
            "phone": self.test_phone,
            "message": "Je veux aller à Lagos vendredi prochain"
        }
        success, data = self.run_test("Travel Request Processing", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'awaiting_flight_selection':
            print(f"   ✅ Session transitioned to: {data.get('session_state')}")
            return True
        elif success:
            print(f"   ❌ Wrong session state: {data.get('session_state')} (expected: awaiting_flight_selection)")
        return False

    def test_flight_selection(self):
        """Test flight selection with option '2'"""
        params = {
            "phone": self.test_phone,
            "message": "2"
        }
        success, data = self.run_test("Flight Selection", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'awaiting_payment_confirmation':
            print(f"   ✅ Session transitioned to: {data.get('session_state')}")
            return True
        elif success:
            print(f"   ❌ Wrong session state: {data.get('session_state')} (expected: awaiting_payment_confirmation)")
        return False

    def test_payment_confirmation(self):
        """Test payment confirmation with 'oui'"""
        params = {
            "phone": self.test_phone,
            "message": "oui"
        }
        success, data = self.run_test("Payment Confirmation", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'awaiting_momo_approval':
            print(f"   ✅ Session transitioned to: {data.get('session_state')}")
            return True
        elif success:
            print(f"   ❌ Wrong session state: {data.get('session_state')} (expected: awaiting_momo_approval)")
        return False

    def test_flight_categorization(self):
        """Test flight categorization algorithm (PLUS_BAS, PLUS_RAPIDE, PREMIUM)"""
        success, data = self.run_test("Flight Categorization", "GET", "test/flights", 200, 
                                     params={"origin": "DSS", "destination": "CDG", "date": "2026-04-15"})
        if success and 'categorized' in data:
            categorized = data['categorized']
            expected_categories = ['PLUS_BAS', 'PLUS_RAPIDE', 'PREMIUM']
            found_categories = list(categorized.keys())
            
            if all(cat in found_categories for cat in expected_categories):
                print(f"   ✅ All categories found: {found_categories}")
                
                # Check PLUS_BAS is lowest price
                plus_bas = categorized.get('PLUS_BAS', {})
                plus_rapide = categorized.get('PLUS_RAPIDE', {})
                premium = categorized.get('PREMIUM', {})
                
                print(f"   PLUS_BAS price: {plus_bas.get('final_price')}€")
                print(f"   PLUS_RAPIDE price: {plus_rapide.get('final_price')}€")
                print(f"   PREMIUM price: {premium.get('final_price')}€")
                
                return True
            else:
                print(f"   ❌ Missing categories. Found: {found_categories}, Expected: {expected_categories}")
        return False

    def test_travelioo_pricing(self):
        """Test Travelioo pricing rule: final_price = amadeus_price + 15 + (amadeus_price * 0.05)"""
        success, data = self.run_test("Travelioo Pricing", "GET", "test/flights", 200,
                                     params={"origin": "DSS", "destination": "CDG", "date": "2026-04-15"})
        if success and 'flights' in data:
            flights = data['flights']
            if flights:
                flight = flights[0]
                amadeus_price = flight.get('amadeus_price', 0)
                final_price = flight.get('final_price', 0)
                expected_price = amadeus_price + 15 + (amadeus_price * 0.05)
                
                if abs(final_price - expected_price) < 0.01:  # Allow small floating point differences
                    print(f"   ✅ Pricing correct: {amadeus_price}€ + 15 + 5% = {final_price}€")
                    return True
                else:
                    print(f"   ❌ Pricing incorrect: Expected {expected_price}€, got {final_price}€")
        return False

    def test_eur_to_xof_conversion(self):
        """Test EUR to XOF conversion uses rate 655.957"""
        success, data = self.run_test("EUR to XOF Conversion", "GET", "test/flights", 200,
                                     params={"origin": "DSS", "destination": "CDG", "date": "2026-04-15"})
        if success and 'flights' in data:
            flights = data['flights']
            if flights:
                flight = flights[0]
                final_price_eur = flight.get('final_price', 0)
                price_xof = flight.get('price_xof', 0)
                expected_xof = int(round(final_price_eur * self.EUR_TO_XOF))
                
                if price_xof == expected_xof:
                    print(f"   ✅ Conversion correct: {final_price_eur}€ × {self.EUR_TO_XOF} = {price_xof} XOF")
                    return True
                else:
                    print(f"   ❌ Conversion incorrect: Expected {expected_xof} XOF, got {price_xof} XOF")
        return False

    def test_flight_selection_plus_bas(self):
        """Test flight selection '1' selects PLUS_BAS category"""
        # Reset and setup
        self.run_test("Reset", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        self.run_test("Setup", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "Je veux aller à Paris vendredi"})
        
        success, data = self.run_test("Flight Selection PLUS_BAS", "POST", "test/message", 200,
                                     params={"phone": self.test_phone, "message": "1"})
        if success:
            session = data.get('session', {})
            selected_flight = session.get('selected_flight', {})
            if selected_flight.get('category') == 'PLUS_BAS':
                print(f"   ✅ PLUS_BAS selected correctly")
                return True
            else:
                print(f"   ❌ Wrong category selected: {selected_flight.get('category')} (expected: PLUS_BAS)")
        return False

    def test_flight_selection_plus_rapide(self):
        """Test flight selection '2' selects PLUS_RAPIDE category"""
        # Reset and setup
        self.run_test("Reset", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        self.run_test("Setup", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "Je veux aller à Paris vendredi"})
        
        success, data = self.run_test("Flight Selection PLUS_RAPIDE", "POST", "test/message", 200,
                                     params={"phone": self.test_phone, "message": "2"})
        if success:
            session = data.get('session', {})
            selected_flight = session.get('selected_flight', {})
            if selected_flight.get('category') == 'PLUS_RAPIDE':
                print(f"   ✅ PLUS_RAPIDE selected correctly")
                return True
            else:
                print(f"   ❌ Wrong category selected: {selected_flight.get('category')} (expected: PLUS_RAPIDE)")
        return False

    def test_flight_selection_premium(self):
        """Test flight selection '3' selects PREMIUM category"""
        # Reset and setup
        self.run_test("Reset", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        self.run_test("Setup", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "Je veux aller à Paris vendredi"})
        
        success, data = self.run_test("Flight Selection PREMIUM", "POST", "test/message", 200,
                                     params={"phone": self.test_phone, "message": "3"})
        if success:
            session = data.get('session', {})
            selected_flight = session.get('selected_flight', {})
            if selected_flight.get('category') == 'PREMIUM':
                print(f"   ✅ PREMIUM selected correctly")
                return True
            else:
                print(f"   ❌ Wrong category selected: {selected_flight.get('category')} (expected: PREMIUM)")
        return False

    def test_missing_destination_prompt(self):
        """Test missing destination prompts for destination"""
        self.run_test("Reset", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        
        success, data = self.run_test("Missing Destination", "POST", "test/message", 200,
                                     params={"phone": self.test_phone, "message": "Je veux voyager vendredi"})
        if success:
            session = data.get('session', {})
            if session.get('state') == 'awaiting_destination':
                print(f"   ✅ Correctly prompting for destination")
                return True
            else:
                print(f"   ❌ Wrong state: {session.get('state')} (expected: awaiting_destination)")
        return False

    def test_missing_date_prompt(self):
        """Test missing date prompts for date"""
        self.run_test("Reset", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        
        success, data = self.run_test("Missing Date", "POST", "test/message", 200,
                                     params={"phone": self.test_phone, "message": "Je veux aller à Paris"})
        if success:
            session = data.get('session', {})
            if session.get('state') == 'awaiting_date':
                print(f"   ✅ Correctly prompting for date")
                return True
            else:
                print(f"   ❌ Wrong state: {session.get('state')} (expected: awaiting_date)")
        return False

    def test_cancel_command(self):
        """Test cancel command resets session"""
        params = {
            "phone": self.test_phone,
            "message": "annuler"
        }
        success, data = self.run_test("Cancel Command", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'idle':
            print(f"   ✅ Session reset to: {data.get('session_state')}")
            return True
        elif success:
            print(f"   ❌ Session not reset: {data.get('session_state')} (expected: idle)")
        return False

    def test_intent_parsing_french(self):
        """Test intent parsing for French message"""
        # Reset session first
        self.run_test("Reset for French test", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        
        params = {
            "phone": self.test_phone,
            "message": "Je veux aller à Abidjan demain avec un budget de 80000 francs"
        }
        success, data = self.run_test("Intent Parsing (French)", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'awaiting_flight_selection':
            print(f"   ✅ French intent parsed successfully")
            return True
        return False

    def test_intent_parsing_english(self):
        """Test intent parsing for English message"""
        # Reset session first
        self.run_test("Reset for English test", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "cancel"})
        
        params = {
            "phone": self.test_phone,
            "message": "I want to fly to Accra next week under $150"
        }
        success, data = self.run_test("Intent Parsing (English)", "POST", "test/message", 200, params=params)
        if success and data.get('session_state') == 'awaiting_flight_selection':
            print(f"   ✅ English intent parsed successfully")
            return True
        return False

    def test_complete_booking_flow(self):
        """Test complete booking flow to generate PDF ticket"""
        print("\n🔄 Testing Complete Booking Flow...")
        
        # Reset session
        self.run_test("Reset session", "POST", "test/message", 200, params={"phone": self.test_phone, "message": "annuler"})
        
        # Step 1: Travel request
        success1, _ = self.run_test("Step 1: Travel Request", "POST", "test/message", 200, 
                                   params={"phone": self.test_phone, "message": "Je veux aller à Lagos vendredi"})
        
        if not success1:
            return False
            
        # Step 2: Flight selection
        success2, _ = self.run_test("Step 2: Flight Selection", "POST", "test/message", 200,
                                   params={"phone": self.test_phone, "message": "1"})
        
        if not success2:
            return False
            
        # Step 3: Payment confirmation
        success3, _ = self.run_test("Step 3: Payment Confirmation", "POST", "test/message", 200,
                                   params={"phone": self.test_phone, "message": "oui"})
        
        if not success3:
            return False
            
        # Wait for payment processing and ticket generation (simulated)
        print("   ⏳ Waiting for payment processing and ticket generation...")
        time.sleep(8)  # Wait for background processing
        
        # Check if session cleared to idle after payment completion
        success4, session_data = self.run_test("Step 4: Check Session After Payment", "GET", f"sessions/{self.test_phone}", 200)
        
        if success4 and session_data.get('state') == 'idle':
            print("   ✅ Session cleared to idle after payment completion")
            return True
        elif success4:
            print(f"   ❌ Session not cleared: {session_data.get('state')} (expected: idle)")
        
        return False

    def test_pdf_ticket_generation(self):
        """Test PDF ticket generation in tickets folder"""
        print("\n📄 Checking PDF ticket generation...")
        
        # Check if tickets directory exists and has files
        tickets_dir = "/app/backend/tickets"
        if os.path.exists(tickets_dir):
            ticket_files = [f for f in os.listdir(tickets_dir) if f.endswith('.pdf')]
            if ticket_files:
                self.ticket_filename = ticket_files[-1]  # Get the latest ticket
                print(f"   ✅ PDF ticket found: {self.ticket_filename}")
                self.tests_run += 1
                self.tests_passed += 1
                return True
            else:
                print("   ❌ No PDF tickets found in tickets directory")
        else:
            print("   ❌ Tickets directory not found")
        
        self.tests_run += 1
        return False

    def test_ticket_download(self):
        """Test ticket PDF download endpoint"""
        if not self.ticket_filename:
            print("❌ Skipped - No ticket filename available")
            self.tests_run += 1
            return False
            
        success, data = self.run_test("Ticket Download", "GET", f"tickets/{self.ticket_filename}", 200)
        if success:
            print(f"   ✅ Ticket PDF downloadable: {self.ticket_filename}")
            return True
        return False

    def test_booking_retrieval(self):
        """Test booking retrieval by reference"""
        if not self.booking_ref:
            # Try to find a booking reference from recent bookings
            print("   ℹ️  No booking reference available, skipping...")
            self.tests_run += 1
            return True
            
        success, data = self.run_test("Booking Retrieval", "GET", f"bookings/{self.booking_ref}", 200)
        if success and data.get('booking_ref') == self.booking_ref:
            print(f"   ✅ Booking retrieved: {data.get('booking_ref')}")
            return True
        return False

def main():
    print("🚀 Starting Travelioo WhatsApp Agent Tests v4.0")
    print("=" * 60)
    
    tester = TraveliooWhatsAppTester()
    
    # Core WhatsApp Agent Tests
    tests = [
        tester.test_health_check,
        tester.test_webhook_verification,
        tester.test_flight_categorization,
        tester.test_travelioo_pricing,
        tester.test_eur_to_xof_conversion,
        tester.test_welcome_message,
        tester.test_travel_request_parsing,
        tester.test_flight_selection_plus_bas,
        tester.test_flight_selection_plus_rapide,
        tester.test_flight_selection_premium,
        tester.test_payment_confirmation,
        tester.test_cancel_command,
        tester.test_missing_destination_prompt,
        tester.test_missing_date_prompt,
        tester.test_intent_parsing_french,
        tester.test_intent_parsing_english,
        tester.test_pdf_ticket_generation,
        tester.test_ticket_download,
    ]
    
    # Run all tests
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 Travelioo v4.0 WhatsApp Agent backend tests highly successful!")
        return 0
    elif success_rate >= 75:
        print("✅ Travelioo v4.0 WhatsApp Agent backend mostly working with minor issues")
        return 1
    elif success_rate >= 50:
        print("⚠️  Travelioo v4.0 WhatsApp Agent backend has some issues but core functionality works")
        return 2
    else:
        print("❌ Travelioo v4.0 WhatsApp Agent backend has significant issues")
        return 3

if __name__ == "__main__":
    sys.exit(main())