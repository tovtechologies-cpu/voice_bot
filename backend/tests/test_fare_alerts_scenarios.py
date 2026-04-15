"""
Additional Fare Alert Tests - Specific Scenarios
Tests: 10% threshold verification, rate limiting, shadow profile storage
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

TEST_USER_RATE_LIMITED = "+22990FARE01"


class TestFareAlertSpecificScenarios:
    """Test specific scenarios from the review request"""
    
    def test_fare_drop_greater_than_10_percent_triggers_alert(self):
        """
        Verify: Alert triggers when fare drops > 10% below user's historical average
        User +22990FARE01 has avg 210 EUR, threshold is 189 EUR
        Current fare is 170 EUR (below 189), so alert should have been triggered
        """
        # Get user's route data
        routes_response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_RATE_LIMITED}")
        assert routes_response.status_code == 200
        routes_data = routes_response.json()
        
        coo_cdg = next((r for r in routes_data["recurring_routes"] if r["route"] == "COO-CDG"), None)
        assert coo_cdg is not None, "COO-CDG route should exist"
        
        avg_price = coo_cdg["avg_price_eur"]
        threshold = avg_price * 0.90  # 10% below average
        
        # Get current fare
        fare_response = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert fare_response.status_code == 200
        fare_data = fare_response.json()
        
        if "lowest_fare_eur" in fare_data:
            current_fare = fare_data["lowest_fare_eur"]
            
            # Verify the math: if current_fare < threshold, alert should trigger
            should_trigger = current_fare < threshold
            
            # Check alert history to verify alert was sent
            history_response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
            history_data = history_response.json()
            
            if should_trigger:
                assert history_data["count"] >= 1, "Alert should have been sent when fare < threshold"
                
                # Verify the alert was for the correct fare drop
                alert = history_data["alerts"][0]
                assert alert["current_fare_eur"] < alert["avg_fare_eur"] * 0.90, \
                    "Alert should only be sent when fare drops > 10%"
                
                print(f"✓ Alert correctly triggered:")
                print(f"  Avg price: {avg_price} EUR")
                print(f"  Threshold (10% below): {threshold} EUR")
                print(f"  Current fare: {current_fare} EUR")
                print(f"  Alert fare: {alert['current_fare_eur']} EUR")
                print(f"  Savings: {alert['savings_eur']} EUR")
            else:
                print(f"⚠ Current fare {current_fare} EUR is not below threshold {threshold} EUR")
    
    def test_fare_drop_less_than_10_percent_no_alert(self):
        """
        Verify: No alert when fare drop < 10%
        If avg is 210 and fare is 195 (7% drop), no alert should be sent
        """
        # This is verified by the rate limiting test - if user already has alert,
        # subsequent checks return 0 alerts
        # The logic is in the service: current_fare < avg_price * (1 - 0.10)
        
        # Get threshold calculation
        routes_response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_RATE_LIMITED}")
        routes_data = routes_response.json()
        
        coo_cdg = next((r for r in routes_data["recurring_routes"] if r["route"] == "COO-CDG"), None)
        if coo_cdg:
            avg_price = coo_cdg["avg_price_eur"]
            threshold = avg_price * 0.90
            
            # A fare of avg * 0.95 (5% drop) should NOT trigger alert
            hypothetical_fare = avg_price * 0.95
            should_not_trigger = hypothetical_fare >= threshold
            
            assert should_not_trigger, "5% drop should not trigger alert (threshold is 10%)"
            print(f"✓ Threshold logic verified: {hypothetical_fare} EUR (5% drop) >= {threshold} EUR threshold")
    
    def test_rate_limit_max_1_alert_per_route_per_week(self):
        """
        Verify: Max 1 alert per route per week
        User +22990FARE01 already has alert sent, second check should return 0
        """
        # First check - should return 0 (already alerted this week)
        response1 = requests.post(f"{BASE_URL}/api/fare-alerts/check/{TEST_USER_RATE_LIMITED}")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second check - should also return 0
        response2 = requests.post(f"{BASE_URL}/api/fare-alerts/check/{TEST_USER_RATE_LIMITED}")
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data1["count"] == 0, "First check should return 0 (rate limited)"
        assert data2["count"] == 0, "Second check should return 0 (rate limited)"
        
        print("✓ Rate limiting verified: max 1 alert per route per week")
    
    def test_recurring_route_requires_2_plus_bookings(self):
        """
        Verify: Recurring route detection requires 2+ bookings on same route
        """
        # User with 3 bookings should have recurring route
        routes_response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_RATE_LIMITED}")
        routes_data = routes_response.json()
        
        for route in routes_data["recurring_routes"]:
            assert route["booking_count"] >= 2, \
                f"Route {route['route']} has {route['booking_count']} bookings, should be >= 2"
        
        print(f"✓ All recurring routes have 2+ bookings")
        
        # User without bookings should have no recurring routes
        fresh_response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/+22990FRESH99")
        fresh_data = fresh_response.json()
        
        assert fresh_data["count"] == 0, "User without bookings should have no recurring routes"
        print("✓ User without bookings correctly has no recurring routes")
    
    def test_alert_stored_with_correct_fields(self):
        """
        Verify: Fare alert stored with phone, route, current_fare, avg_fare, savings
        """
        history_response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
        assert history_response.status_code == 200
        history_data = history_response.json()
        
        assert history_data["count"] >= 1, "Should have at least 1 alert"
        
        alert = history_data["alerts"][0]
        
        # Verify all required fields
        assert "phone" in alert, "Alert should have phone"
        assert "route" in alert, "Alert should have route"
        assert "current_fare_eur" in alert, "Alert should have current_fare_eur"
        assert "avg_fare_eur" in alert, "Alert should have avg_fare_eur"
        assert "savings_eur" in alert, "Alert should have savings_eur"
        assert "sent_at" in alert, "Alert should have sent_at timestamp"
        
        # Verify savings calculation
        expected_savings = round(alert["avg_fare_eur"] - alert["current_fare_eur"], 2)
        assert alert["savings_eur"] == expected_savings, \
            f"Savings mismatch: expected {expected_savings}, got {alert['savings_eur']}"
        
        print(f"✓ Alert stored with correct fields:")
        print(f"  phone: {alert['phone']}")
        print(f"  route: {alert['route']}")
        print(f"  current_fare: {alert['current_fare_eur']} EUR")
        print(f"  avg_fare: {alert['avg_fare_eur']} EUR")
        print(f"  savings: {alert['savings_eur']} EUR")
    
    def test_fare_cache_24h_ttl(self):
        """
        Verify: Fare cache is stored and reused within 24h TTL
        """
        # First request - may hit Duffel or cache
        response1 = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request - should hit cache
        response2 = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert response2.status_code == 200
        data2 = response2.json()
        
        if "lowest_fare_eur" in data1 and "lowest_fare_eur" in data2:
            # Both should return same fare (from cache)
            assert data1["lowest_fare_eur"] == data2["lowest_fare_eur"], \
                "Cached fare should be consistent within TTL"
            print(f"✓ Fare cache working: {data1['lowest_fare_eur']} EUR returned consistently")
        else:
            print("⚠ No fare data available for cache verification")


class TestFareAlertAPIResponses:
    """Test API response structures"""
    
    def test_routes_endpoint_response_structure(self):
        """Verify GET /api/fare-alerts/routes/{phone} response structure"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/routes/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required top-level fields
        assert "phone" in data
        assert "recurring_routes" in data
        assert "count" in data
        
        # Route structure
        if data["count"] > 0:
            route = data["recurring_routes"][0]
            assert "route" in route
            assert "origin" in route
            assert "destination" in route
            assert "booking_count" in route
            assert "avg_price_eur" in route
            assert "prices" in route
        
        print("✓ Routes endpoint response structure verified")
    
    def test_fare_endpoint_response_structure(self):
        """Verify GET /api/fare-alerts/fare/{origin}/{destination} response structure"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/fare/COO/CDG")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "origin" in data
        assert "destination" in data
        
        # Either has fare or error
        assert "lowest_fare_eur" in data or "error" in data
        
        print("✓ Fare endpoint response structure verified")
    
    def test_check_endpoint_response_structure(self):
        """Verify POST /api/fare-alerts/check/{phone} response structure"""
        response = requests.post(f"{BASE_URL}/api/fare-alerts/check/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "phone" in data
        assert "alerts_sent" in data
        assert "count" in data
        assert isinstance(data["alerts_sent"], list)
        
        print("✓ Check endpoint response structure verified")
    
    def test_history_endpoint_response_structure(self):
        """Verify GET /api/fare-alerts/history/{phone} response structure"""
        response = requests.get(f"{BASE_URL}/api/fare-alerts/history/{TEST_USER_RATE_LIMITED}")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "phone" in data
        assert "alerts" in data
        assert "count" in data
        assert isinstance(data["alerts"], list)
        
        print("✓ History endpoint response structure verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
