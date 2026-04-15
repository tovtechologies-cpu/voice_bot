"""
Test Predictive Fare Alerts Feature
Tests: recurring route detection, fare lookup, alert triggering, rate limiting, alert history
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test users
TEST_USER_RATE_LIMITED = "+22990FARE01"  # Has 3 bookings COO->CDG, already has alert sent (rate-limited)
TEST_USER_FRESH = "+22990FARE02"  # Fresh user for new tests


class TestFareAlertsRouteAnalysis:
    """Test GET /api/fare-alerts/routes/{phone} - Recurring route detection"""
    
    def test_get_recurring_routes_existing_user(self):
        """Test that user with 3 bookings on same route shows recurring route"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "phone" in data
        assert data["phone"] == TEST_USER_RATE_LIMITED
        assert "recurring_routes" in data
        assert "count" in data
        
        # Should have at least 1 recurring route (COO-CDG)
        assert data["count"] >= 1, f"Expected at least 1 recurring route, got {data['count']}"
        
        # Verify route structure
        routes = data["recurring_routes"]
        assert len(routes) >= 1
        
        coo_cdg_route = next((r for r in routes if r["route"] == "COO-CDG"), None)
        assert coo_cdg_route is not None, "Expected COO-CDG route not found"
        
        # Verify route data
        assert coo_cdg_route["origin"] == "COO"
        assert coo_cdg_route["destination"] == "CDG"
        assert coo_cdg_route["booking_count"] >= 2, "Recurring route requires 2+ bookings"
        assert coo_cdg_route["avg_price_eur"] > 0, "Average price should be positive"
        assert "prices" in coo_cdg_route
        print(f"✓ Recurring route found: {coo_cdg_route['route']} with {coo_cdg_route['booking_count']} bookings, avg {coo_cdg_route['avg_price_eur']} EUR")
    
    def test_get_recurring_routes_user_without_history(self):
        """Test that user without travel history returns empty routes"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_FRESH}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 0, "Fresh user should have no recurring routes"
        assert data["recurring_routes"] == []
        print("✓ Fresh user correctly returns empty recurring routes")
    
    def test_get_recurring_routes_nonexistent_user(self):
        """Test that nonexistent user returns empty routes (not error)"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/+99999999999")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 0
        assert data["recurring_routes"] == []
        print("✓ Nonexistent user correctly returns empty routes")


class TestFareAlertsFareLookup:
    """Test GET /api/fare-alerts/fare/{origin}/{destination} - Current fare lookup"""
    
    def test_get_current_fare_valid_route(self):
        """Test fare lookup for valid route (COO->CDG)"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert response.status_code == 200
        
        data = response.json()
        assert "origin" in data
        assert "destination" in data
        assert data["origin"] == "COO"
        assert data["destination"] == "CDG"
        
        # Should have fare or error
        if "lowest_fare_eur" in data:
            assert data["lowest_fare_eur"] > 0, "Fare should be positive"
            print(f"✓ Current fare for COO->CDG: {data['lowest_fare_eur']} EUR")
        else:
            # Duffel sandbox may not have flights for all routes
            assert "error" in data
            print(f"⚠ No fare data available for COO->CDG (Duffel sandbox limitation)")
    
    def test_get_current_fare_lowercase_codes(self):
        """Test that lowercase airport codes are converted to uppercase"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/fare/coo/cdg")
        assert response.status_code == 200
        
        data = response.json()
        assert data["origin"] == "COO", "Origin should be uppercase"
        assert data["destination"] == "CDG", "Destination should be uppercase"
        print("✓ Lowercase airport codes correctly converted to uppercase")
    
    def test_get_current_fare_invalid_route(self):
        """Test fare lookup for invalid/no-flight route"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/fare/XXX/YYY")
        assert response.status_code == 200
        
        data = response.json()
        # Should return error for invalid route
        assert "error" in data or "lowest_fare_eur" in data
        print("✓ Invalid route handled correctly")


class TestFareAlertsCheckAndAlert:
    """Test POST /api/fare-alerts/check/{phone} - Alert triggering"""
    
    def test_check_alerts_rate_limited_user(self):
        """Test that rate-limited user (already has alert this week) gets 0 alerts"""
        response = requests.post(f"{BASE_URL}/api/fare-alerts/check/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200
        
        data = response.json()
        assert "phone" in data
        assert "alerts_sent" in data
        assert "count" in data
        
        # User already has alert sent this week, should be rate-limited
        assert data["count"] == 0, f"Rate-limited user should get 0 alerts, got {data['count']}"
        assert data["alerts_sent"] == []
        print(f"✓ Rate limiting working: user {TEST_USER_RATE_LIMITED[-4:]} got 0 alerts (already alerted this week)")
    
    def test_check_alerts_user_without_routes(self):
        """Test that user without recurring routes gets 0 alerts"""
        response = requests.post(f"{BASE_URL}/api/fare-alerts/check/{TEST_USER_FRESH}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 0, "User without routes should get 0 alerts"
        print("✓ User without recurring routes correctly gets 0 alerts")
    
    def test_check_alerts_nonexistent_user(self):
        """Test that nonexistent user returns 0 alerts (not error)"""
        response = requests.post(f"{BASE_URL}/api/fare-alerts/check/+99999999999")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 0
        print("✓ Nonexistent user correctly returns 0 alerts")


class TestFareAlertsHistory:
    """Test GET /api/fare-alerts/history/{phone} - Alert history"""
    
    def test_get_alert_history_existing_user(self):
        """Test alert history for user with alerts"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200
        
        data = response.json()
        assert "phone" in data
        assert "alerts" in data
        assert "count" in data
        
        # User should have at least 1 alert
        assert data["count"] >= 1, f"Expected at least 1 alert in history, got {data['count']}"
        
        # Verify alert structure
        alert = data["alerts"][0]
        assert "phone" in alert
        assert "route" in alert
        assert "current_fare_eur" in alert
        assert "avg_fare_eur" in alert
        assert "savings_eur" in alert
        assert "sent_at" in alert
        
        # Verify savings calculation
        expected_savings = round(alert["avg_fare_eur"] - alert["current_fare_eur"], 2)
        assert alert["savings_eur"] == expected_savings, f"Savings mismatch: expected {expected_savings}, got {alert['savings_eur']}"
        
        print(f"✓ Alert history found: {data['count']} alerts for user {TEST_USER_RATE_LIMITED[-4:]}")
        print(f"  Latest alert: {alert['route']} - saved {alert['savings_eur']} EUR")
    
    def test_get_alert_history_user_without_alerts(self):
        """Test alert history for user without alerts"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_FRESH}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 0
        assert data["alerts"] == []
        print("✓ User without alerts correctly returns empty history")
    
    def test_get_alert_history_with_limit(self):
        """Test alert history with limit parameter"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["alerts"]) <= 5, "Limit parameter should be respected"
        print("✓ Alert history limit parameter working")


class TestFareAlertThresholdLogic:
    """Test the 10% fare drop threshold logic"""
    
    def test_threshold_calculation_verification(self):
        """Verify the threshold calculation: alert when fare < avg * 0.90"""
        # Get user's average price
        routes_response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_RATE_LIMITED}")
        assert routes_response.status_code == 200
        routes_data = routes_response.json()
        
        coo_cdg_route = next((r for r in routes_data["recurring_routes"] if r["route"] == "COO-CDG"), None)
        assert coo_cdg_route is not None
        
        avg_price = coo_cdg_route["avg_price_eur"]
        threshold = avg_price * 0.90  # 10% below average
        
        # Get current fare
        fare_response = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert fare_response.status_code == 200
        fare_data = fare_response.json()
        
        if "lowest_fare_eur" in fare_data:
            current_fare = fare_data["lowest_fare_eur"]
            
            # Check if alert should trigger
            should_alert = current_fare < threshold
            
            print(f"✓ Threshold verification:")
            print(f"  Average price: {avg_price} EUR")
            print(f"  Threshold (10% below): {threshold} EUR")
            print(f"  Current fare: {current_fare} EUR")
            print(f"  Should trigger alert: {should_alert}")
            
            # Verify against actual alert history
            history_response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
            history_data = history_response.json()
            
            if history_data["count"] > 0:
                latest_alert = history_data["alerts"][0]
                alert_fare = latest_alert["current_fare_eur"]
                alert_avg = latest_alert["avg_fare_eur"]
                
                # Verify alert was triggered correctly (fare was below threshold)
                assert alert_fare < alert_avg * 0.90, "Alert should only trigger when fare < avg * 0.90"
                print(f"  ✓ Alert correctly triggered at {alert_fare} EUR (below threshold {alert_avg * 0.90} EUR)")
        else:
            print("⚠ No fare data available for threshold verification")


class TestFareCacheVerification:
    """Test fare cache functionality"""
    
    def test_fare_cache_consistency(self):
        """Test that consecutive fare lookups return consistent cached data"""
        # First lookup
        response1 = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second lookup (should hit cache)
        response2 = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Both should return same fare (from cache)
        if "lowest_fare_eur" in data1 and "lowest_fare_eur" in data2:
            assert data1["lowest_fare_eur"] == data2["lowest_fare_eur"], "Cached fare should be consistent"
            print(f"✓ Fare cache working: consistent fare {data1['lowest_fare_eur']} EUR returned")
        else:
            print("⚠ No fare data available for cache verification")


class TestFareAlertDataIntegrity:
    """Test data integrity in fare alerts"""
    
    def test_alert_stored_in_fare_alerts_collection(self):
        """Verify alert is stored in fare_alerts collection with correct structure"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] >= 1, "Expected at least 1 alert"
        
        alert = data["alerts"][0]
        
        # Verify required fields
        required_fields = ["phone", "route", "current_fare_eur", "avg_fare_eur", "savings_eur", "sent_at"]
        for field in required_fields:
            assert field in alert, f"Missing required field: {field}"
        
        # Verify data types
        assert isinstance(alert["current_fare_eur"], (int, float))
        assert isinstance(alert["avg_fare_eur"], (int, float))
        assert isinstance(alert["savings_eur"], (int, float))
        assert isinstance(alert["route"], str)
        assert "-" in alert["route"], "Route should be in format ORIGIN-DEST"
        
        print("✓ Alert data structure verified in fare_alerts collection")
    
    def test_alert_route_format(self):
        """Verify route format is ORIGIN-DEST"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
        data = response.json()
        
        if data["count"] > 0:
            for alert in data["alerts"]:
                route = alert["route"]
                parts = route.split("-")
                assert len(parts) == 2, f"Route should have 2 parts: {route}"
                assert len(parts[0]) == 3, f"Origin should be 3-letter code: {parts[0]}"
                assert len(parts[1]) == 3, f"Destination should be 3-letter code: {parts[1]}"
            print("✓ All routes in correct ORIGIN-DEST format")


class TestFareAlertEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_phone_number(self):
        """Test handling of empty phone number"""
        # Routes endpoint
        response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/")
        # Should return 404 (not found) or redirect
        assert response.status_code in [404, 307, 405], f"Expected 404/307/405 for empty phone, got {response.status_code}"
        print("✓ Empty phone number handled correctly")
    
    def test_special_characters_in_phone(self):
        """Test handling of special characters in phone number"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/+229-90-00-00-01")
        assert response.status_code == 200
        # Should return empty (no matching user)
        data = response.json()
        assert data["count"] == 0
        print("✓ Special characters in phone handled correctly")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
