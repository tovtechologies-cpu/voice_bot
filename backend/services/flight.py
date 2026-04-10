"""Duffel GDS flight search service with sandbox mock fallback."""
import logging
import random
import uuid
import math
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from config import (
    DUFFEL_API_KEY, is_duffel_sandbox, get_duffel_mode, API_TIMEOUT,
    EUR_TO_XOF, AIRLINES
)

logger = logging.getLogger("FlightService")


def apply_travelio_margin(base_price: float) -> float:
    return round(base_price + 15 + (base_price * 0.05), 2)


def eur_to_xof(eur: float) -> int:
    return int(math.ceil(eur * EUR_TO_XOF / 5) * 5)


def format_duration(iso_duration: str) -> str:
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return f"{hours}h{minutes:02d}" if hours else f"0h{minutes:02d}"
    return iso_duration


def parse_duration_minutes(iso_duration: str) -> int:
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if match:
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    return 9999


def _minutes_to_iso(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"PT{h}H{m}M"


async def search_flights(origin: str, destination: str, departure_date: str, adults: int = 1) -> List[Dict]:
    """Search flights via Duffel API, falling back to mock in sandbox/mock mode."""
    mode = get_duffel_mode()
    if mode == "MOCK":
        logger.info(f"[Duffel MOCK] No key configured. Mock search: {origin}->{destination} on {departure_date}")
        return generate_mock_flights(origin, destination, departure_date, adults)
    if mode == "SANDBOX":
        logger.info(f"[Duffel SANDBOX] Test search: {origin}->{destination} on {departure_date}")
        return await _search_duffel_flights(origin, destination, departure_date, adults)
    # PRODUCTION
    logger.info(f"[Duffel PRODUCTION] Live search: {origin}->{destination} on {departure_date}")
    return await _search_duffel_flights(origin, destination, departure_date, adults)


async def _search_duffel_flights(origin: str, destination: str, departure_date: str, adults: int) -> List[Dict]:
    """Real Duffel API search."""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT * 2) as client:
            # Create offer request
            offer_req = await client.post(
                "https://api.duffel.com/air/offer_requests",
                json={
                    "data": {
                        "slices": [{
                            "origin": origin,
                            "destination": destination,
                            "departure_date": departure_date
                        }],
                        "passengers": [{"type": "adult"} for _ in range(adults)],
                        "cabin_class": "economy"
                    }
                },
                headers={
                    "Authorization": f"Bearer {DUFFEL_API_KEY}",
                    "Content-Type": "application/json",
                    "Duffel-Version": "v2"
                }
            )

            if offer_req.status_code != 200:
                logger.error(f"Duffel offer_request failed: {offer_req.status_code} {offer_req.text[:200]}")
                return generate_mock_flights(origin, destination, departure_date, adults)

            data = offer_req.json().get("data", {})
            offers = data.get("offers", [])
            if not offers:
                return generate_mock_flights(origin, destination, departure_date, adults)

            return _parse_duffel_offers(offers)
    except Exception as e:
        logger.error(f"Duffel API error: {e}")
        return generate_mock_flights(origin, destination, departure_date, adults)


def _parse_duffel_offers(offers: list) -> List[Dict]:
    """Parse Duffel offer responses into our flight format."""
    flights = []
    for offer in offers[:20]:
        try:
            base_price = float(offer.get("total_amount", 0))
            final_price = apply_travelio_margin(base_price)
            currency = offer.get("total_currency", "EUR")

            slices = offer.get("slices", [])
            if not slices:
                continue
            outbound = slices[0]
            segments = outbound.get("segments", [])
            if not segments:
                continue

            first_seg = segments[0]
            last_seg = segments[-1]
            carrier = first_seg.get("operating_carrier", {})
            carrier_name = carrier.get("name", first_seg.get("marketing_carrier", {}).get("name", "Unknown"))
            carrier_code = carrier.get("iata_code", first_seg.get("marketing_carrier", {}).get("iata_code", "XX"))

            # Duration from Duffel
            duration_str = outbound.get("duration", "PT0H0M")

            # Fare conditions from Duffel offer
            conditions = offer.get("conditions", {})
            refund_before = conditions.get("refund_before_departure", {})
            change_before = conditions.get("change_before_departure", {})

            flights.append({
                "id": offer.get("id", str(uuid.uuid4())),
                "duffel_offer_id": offer.get("id"),
                "base_price": base_price,
                "final_price": final_price,
                "price_xof": eur_to_xof(final_price),
                "currency": currency,
                "airline": carrier_name,
                "carrier_code": carrier_code,
                "flight_number": f"{carrier_code}{first_seg.get('marketing_carrier_flight_number', '000')}",
                "origin": first_seg.get("origin", {}).get("iata_code", ""),
                "destination": last_seg.get("destination", {}).get("iata_code", ""),
                "departure_time": first_seg.get("departing_at", ""),
                "arrival_time": last_seg.get("arriving_at", ""),
                "duration": duration_str,
                "duration_formatted": format_duration(duration_str),
                "duration_minutes": parse_duration_minutes(duration_str),
                "stops": len(segments) - 1,
                "stops_text": "Direct" if len(segments) == 1 else f"{len(segments) - 1} escale{'s' if len(segments) > 2 else ''}",
                "is_demo": False,
                # Real fare conditions from Duffel
                "duffel_conditions": {
                    "refundable": refund_before.get("allowed", False),
                    "refund_penalty": refund_before.get("penalty_amount"),
                    "refund_penalty_currency": refund_before.get("penalty_currency"),
                    "changeable": change_before.get("allowed", False),
                    "change_penalty": change_before.get("penalty_amount"),
                    "change_penalty_currency": change_before.get("penalty_currency"),
                }
            })
        except Exception as e:
            logger.error(f"Duffel parse error: {e}")

    return flights


def generate_mock_flights(origin: str, destination: str, date: str, adults: int = 1) -> List[Dict]:
    """Generate realistic mock flights for sandbox mode."""
    flights = []
    base_prices = [185, 220, 310, 275, 195]
    durations_data = [(330, 1), (195, 0), (240, 0), (405, 2), (270, 1)]

    for i in range(min(5, len(base_prices))):
        airline_name, carrier = random.choice(AIRLINES)
        base_price = base_prices[i] + random.randint(-20, 30)
        final_price = apply_travelio_margin(base_price)
        dur_min, stops = durations_data[i]
        duration = _minutes_to_iso(dur_min)

        flights.append({
            "id": str(uuid.uuid4()),
            "duffel_offer_id": None,
            "base_price": base_price,
            "final_price": final_price,
            "price_xof": eur_to_xof(final_price),
            "currency": "EUR",
            "airline": airline_name,
            "carrier_code": carrier,
            "flight_number": f"{carrier}{random.randint(100, 999)}",
            "origin": origin,
            "destination": destination,
            "departure_time": f"{date}T{8 + i * 2:02d}:00:00",
            "arrival_time": f"{date}T{14 + i * 2:02d}:30:00",
            "duration": duration,
            "duration_formatted": format_duration(duration),
            "duration_minutes": dur_min,
            "stops": stops,
            "stops_text": "Direct" if stops == 0 else f"{stops} escale{'s' if stops > 1 else ''}",
            "is_demo": True,
            "duffel_conditions": None
        })
    return flights


def categorize_flights(flights: List[Dict]) -> Dict[str, Dict]:
    """Categorize flights into 3 options: cheapest, fastest, premium."""
    if not flights:
        return {}

    by_price = sorted(flights, key=lambda f: f["final_price"])
    by_duration = sorted(flights, key=lambda f: f["duration_minutes"])

    max_price = max(f["final_price"] for f in flights)
    max_duration = max(f["duration_minutes"] for f in flights)

    def get_score(f):
        price_score = (max_price - f["final_price"]) / max_price if max_price > 0 else 0
        duration_score = (max_duration - f["duration_minutes"]) / max_duration if max_duration > 0 else 0
        direct_bonus = 1.0 if f.get("stops", 0) == 0 else (0.5 if f.get("stops") == 1 else 0)
        return (price_score * 0.4) + (duration_score * 0.4) + (direct_bonus * 0.2)

    by_score = sorted(flights, key=get_score, reverse=True)

    result = {}
    used_ids = set()

    for f in by_price:
        if f["id"] not in used_ids:
            result["PLUS_BAS"] = {**f, "category": "PLUS_BAS", "label": "LE PLUS BAS"}
            used_ids.add(f["id"])
            break

    for f in by_duration:
        if f["id"] not in used_ids:
            result["PLUS_RAPIDE"] = {**f, "category": "PLUS_RAPIDE", "label": "LE PLUS RAPIDE"}
            used_ids.add(f["id"])
            break

    for f in by_score:
        if f["id"] not in used_ids:
            result["PREMIUM"] = {**f, "category": "PREMIUM", "label": "PREMIUM"}
            used_ids.add(f["id"])
            break

    return result


async def create_duffel_order(offer_id: str, passenger_data: dict) -> Optional[Dict]:
    """Create a Duffel order (booking) from a selected offer."""
    if is_duffel_sandbox() or not offer_id:
        return {"id": f"ord_{uuid.uuid4().hex[:16]}", "status": "confirmed", "is_mock": True}

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT * 2) as client:
            resp = await client.post(
                "https://api.duffel.com/air/orders",
                json={
                    "data": {
                        "selected_offers": [offer_id],
                        "payments": [{"type": "balance", "currency": "EUR", "amount": str(passenger_data.get("amount", 0))}],
                        "passengers": [{
                            "type": "adult",
                            "given_name": passenger_data.get("firstName", ""),
                            "family_name": passenger_data.get("lastName", ""),
                            "born_on": passenger_data.get("dateOfBirth"),
                            "title": "mr",
                            "gender": "m",
                            "email": "booking@travelio.app",
                            "phone_number": passenger_data.get("phone", "")
                        }]
                    }
                },
                headers={
                    "Authorization": f"Bearer {DUFFEL_API_KEY}",
                    "Content-Type": "application/json",
                    "Duffel-Version": "v2"
                }
            )
            if resp.status_code in [200, 201]:
                return resp.json().get("data")
            logger.error(f"Duffel order creation failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Duffel order error: {e}")
    return None


async def cancel_duffel_order(order_id: str) -> bool:
    """Cancel a Duffel order."""
    if is_duffel_sandbox() or not order_id or order_id.startswith("ord_"):
        return True

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(
                "https://api.duffel.com/air/order_cancellations",
                json={"data": {"order_id": order_id}},
                headers={
                    "Authorization": f"Bearer {DUFFEL_API_KEY}",
                    "Content-Type": "application/json",
                    "Duffel-Version": "v2"
                }
            )
            return resp.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Duffel cancel error: {e}")
    return False
