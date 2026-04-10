#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime, timedelta
import uuid

class TravelioAPITester:
    def __init__(self, base_url="https://voice-travel-booking.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.user_id = None
        self.booking_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
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
        """Test health check endpoint"""
        return self.run_test("Health Check", "GET", "health", 200)

    def test_cities_endpoint(self):
        """Test cities endpoint"""
        success, data = self.run_test("Cities List", "GET", "cities", 200)
        if success and isinstance(data, list) and len(data) > 0:
            print(f"   Found {len(data)} cities")
            return True
        return False

    def test_parse_intent_english(self):
        """Test intent parsing in English"""
        test_data = {
            "text": "I want to fly from Dakar to Lagos next Friday for $200",
            "language": "en"
        }
        success, data = self.run_test("Parse Intent (English)", "POST", "parse-intent", 200, test_data, timeout=45)
        if success:
            print(f"   Parsed destination: {data.get('destination')}")
            print(f"   Parsed budget: {data.get('budget')}")
            return True
        return False

    def test_parse_intent_french(self):
        """Test intent parsing in French"""
        test_data = {
            "text": "Je veux aller de Dakar à Abidjan vendredi prochain avec un budget de 50000 XOF",
            "language": "fr"
        }
        success, data = self.run_test("Parse Intent (French)", "POST", "parse-intent", 200, test_data, timeout=45)
        if success:
            print(f"   Parsed destination: {data.get('destination')}")
            print(f"   Parsed budget: {data.get('budget')}")
            return True
        return False

    def test_flight_search(self):
        """Test flight search"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        test_data = {
            "origin": "Dakar",
            "destination": "Lagos",
            "departure_date": tomorrow,
            "passengers": 1,
            "travel_class": "economy"
        }
        success, data = self.run_test("Flight Search", "POST", "flights/search", 200, test_data)
        if success and isinstance(data, list) and len(data) == 3:
            print(f"   Found {len(data)} flight options")
            # Check if we have ECO, FAST, PREMIUM tiers
            tiers = [flight.get('tier') for flight in data]
            if 'ECO' in tiers and 'FAST' in tiers and 'PREMIUM' in tiers:
                print("   ✅ All tier types present (ECO, FAST, PREMIUM)")
                return True
            else:
                print(f"   ⚠️  Missing tier types. Found: {tiers}")
        return False

    def test_get_flight_by_id(self):
        """Test getting flight by ID"""
        test_flight_id = str(uuid.uuid4())
        success, data = self.run_test("Get Flight by ID", "GET", f"flights/{test_flight_id}", 200)
        if success:
            print(f"   Flight: {data.get('airline')} {data.get('flight_number')}")
            return True
        return False

    def test_create_user(self):
        """Test user creation"""
        test_data = {
            "first_name": "Amadou",
            "last_name": "Diallo",
            "phone": "+221771234567",
            "email": "amadou.diallo@example.com"
        }
        success, data = self.run_test("Create User", "POST", "users", 200, test_data)
        if success and data.get('id'):
            self.user_id = data['id']
            print(f"   Created user ID: {self.user_id}")
            return True
        return False

    def test_get_user_by_id(self):
        """Test getting user by ID"""
        if not self.user_id:
            print("❌ Skipped - No user ID available")
            return False
        
        success, data = self.run_test("Get User by ID", "GET", f"users/{self.user_id}", 200)
        if success:
            print(f"   User: {data.get('first_name')} {data.get('last_name')}")
            return True
        return False

    def test_bulk_user_creation(self):
        """Test bulk user creation"""
        test_data = [
            {
                "first_name": "Fatou",
                "last_name": "Sow",
                "phone": "+221771234568",
                "email": "fatou.sow@example.com"
            },
            {
                "first_name": "Moussa",
                "last_name": "Ba",
                "phone": "+221771234569",
                "email": "moussa.ba@example.com"
            }
        ]
        success, data = self.run_test("Bulk User Creation", "POST", "users/bulk", 200, test_data)
        if success and isinstance(data, list) and len(data) == 2:
            print(f"   Created {len(data)} users")
            return True
        return False

    def test_create_booking(self):
        """Test booking creation"""
        if not self.user_id:
            print("❌ Skipped - No user ID available")
            return False
            
        test_flight_id = str(uuid.uuid4())
        test_data = {
            "user_id": self.user_id,
            "flight_id": test_flight_id,
            "passengers": 1,
            "payment_method": "momo"
        }
        success, data = self.run_test("Create Booking", "POST", "bookings", 200, test_data)
        if success and data.get('id'):
            self.booking_id = data['id']
            print(f"   Created booking ID: {self.booking_id}")
            print(f"   QR Code: {data.get('qr_code')}")
            return True
        return False

    def test_get_user_bookings(self):
        """Test getting user bookings"""
        if not self.user_id:
            print("❌ Skipped - No user ID available")
            return False
            
        success, data = self.run_test("Get User Bookings", "GET", f"bookings/user/{self.user_id}", 200)
        if success and isinstance(data, list):
            print(f"   Found {len(data)} bookings for user")
            return True
        return False

    def test_get_booking_by_id(self):
        """Test getting booking by ID"""
        if not self.booking_id:
            print("❌ Skipped - No booking ID available")
            return False
            
        success, data = self.run_test("Get Booking by ID", "GET", f"bookings/{self.booking_id}", 200)
        if success:
            print(f"   Booking: {data.get('airline')} {data.get('flight_number')}")
            return True
        return False

    def test_momo_payment(self):
        """Test MTN MoMo payment"""
        test_data = {
            "booking_id": self.booking_id or "test-booking",
            "amount": 75000,
            "currency": "XOF",
            "phone_number": "+221771234567",
            "payment_method": "momo"
        }
        success, data = self.run_test("MTN MoMo Payment", "POST", "payments/momo", 200, test_data)
        if success and data.get('status') == 'success':
            print(f"   Transaction ID: {data.get('transaction_id')}")
            return True
        return False

    def test_google_pay_payment(self):
        """Test Google Pay payment"""
        test_data = {
            "booking_id": self.booking_id or "test-booking",
            "amount": 75000,
            "currency": "XOF",
            "phone_number": "+221771234567",
            "payment_method": "google"
        }
        success, data = self.run_test("Google Pay Payment", "POST", "payments/google-pay", 200, test_data)
        if success and data.get('status') == 'success':
            print(f"   Transaction ID: {data.get('transaction_id')}")
            return True
        return False

    def test_apple_pay_payment(self):
        """Test Apple Pay payment"""
        test_data = {
            "booking_id": self.booking_id or "test-booking",
            "amount": 75000,
            "currency": "XOF",
            "phone_number": "+221771234567",
            "payment_method": "apple"
        }
        success, data = self.run_test("Apple Pay Payment", "POST", "payments/apple-pay", 200, test_data)
        if success and data.get('status') == 'success':
            print(f"   Transaction ID: {data.get('transaction_id')}")
            return True
        return False

    def test_whatsapp_ticket(self):
        """Test WhatsApp ticket sending"""
        if not self.booking_id:
            print("❌ Skipped - No booking ID available")
            return False
            
        test_data = {
            "phone_number": "+221771234567",
            "booking_id": self.booking_id
        }
        success, data = self.run_test("WhatsApp Ticket", "POST", "whatsapp/send-ticket", 200, test_data)
        if success and data.get('status') == 'sent':
            print(f"   Ticket sent to: {data.get('phone_number')}")
            return True
        return False

def main():
    print("🚀 Starting Travelio API Tests")
    print("=" * 50)
    
    tester = TravelioAPITester()
    
    # Core API Tests
    tests = [
        tester.test_health_check,
        tester.test_cities_endpoint,
        tester.test_parse_intent_english,
        tester.test_parse_intent_french,
        tester.test_flight_search,
        tester.test_get_flight_by_id,
        tester.test_create_user,
        tester.test_get_user_by_id,
        tester.test_bulk_user_creation,
        tester.test_create_booking,
        tester.test_get_user_bookings,
        tester.test_get_booking_by_id,
        tester.test_momo_payment,
        tester.test_google_pay_payment,
        tester.test_apple_pay_payment,
        tester.test_whatsapp_ticket,
    ]
    
    # Run all tests
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 Backend API tests mostly successful!")
        return 0
    elif success_rate >= 60:
        print("⚠️  Backend API has some issues but core functionality works")
        return 1
    else:
        print("❌ Backend API has significant issues")
        return 2

if __name__ == "__main__":
    sys.exit(main())