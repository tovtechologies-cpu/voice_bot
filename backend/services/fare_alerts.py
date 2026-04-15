"""Predictive Fare Alerts — analyze travel patterns and notify on price drops."""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from collections import Counter
from database import db
from services.whatsapp import send_whatsapp_message
from services.channel import set_channel
from config import EUR_TO_XOF

logger = logging.getLogger("FareAlertService")

# Configuration
FARE_DROP_THRESHOLD_PCT = 0.10  # Alert when fare drops > 10% below average
MIN_BOOKINGS_FOR_PATTERN = 2   # Need 2+ bookings on same route
MAX_ALERTS_PER_ROUTE_PER_WEEK = 1
FARE_CACHE_TTL_HOURS = 24


async def analyze_user_routes(phone: str) -> List[Dict]:
    """Analyze a user's travel history to find recurring routes."""
    profile = await db.shadow_profiles.find_one({"phone_number": phone}, {"_id": 0})
    if not profile:
        return []

    travel_history = profile.get("travel_history", [])
    if len(travel_history) < MIN_BOOKINGS_FOR_PATTERN:
        return []

    # Fetch full booking data for each trip
    route_data = Counter()
    route_prices = {}

    for trip in travel_history:
        ref = trip.get("ref")
        if not ref:
            continue
        booking = await db.bookings.find_one({"booking_ref": ref}, {"_id": 0})
        if not booking or booking.get("status") in ["cancelled_by_airline", "payment_failed"]:
            continue

        origin = booking.get("origin", "")
        dest = booking.get("destination", "")
        if not origin or not dest:
            continue

        route_key = f"{origin}-{dest}"
        route_data[route_key] += 1
        gds_price = booking.get("gds_price_eur", 0)
        if gds_price > 0:
            route_prices.setdefault(route_key, []).append(gds_price)

    # Find recurring routes (2+ bookings)
    recurring = []
    for route, count in route_data.items():
        if count >= MIN_BOOKINGS_FOR_PATTERN:
            prices = route_prices.get(route, [])
            avg_price = round(sum(prices) / len(prices), 2) if prices else 0
            origin, dest = route.split("-")
            recurring.append({
                "route": route,
                "origin": origin,
                "destination": dest,
                "booking_count": count,
                "avg_price_eur": avg_price,
                "prices": prices,
            })

    return recurring


async def check_fare_for_route(origin: str, destination: str) -> Optional[float]:
    """Check current fare for a route. Uses Duffel or fare cache."""
    # Check cache first
    cache_key = f"{origin}-{destination}"
    cached = await db.fare_cache.find_one({"route": cache_key}, {"_id": 0})
    if cached:
        cached_at = cached.get("cached_at", "")
        try:
            cache_time = datetime.fromisoformat(cached_at)
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < FARE_CACHE_TTL_HOURS * 3600:
                return cached.get("lowest_fare_eur")
        except (ValueError, TypeError):
            pass

    # Search Duffel for current fares
    from services.flight import search_flights
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    flights = await search_flights(origin, destination, tomorrow, 1)

    if not flights:
        return None

    # Find lowest fare
    lowest = min(f.get("base_price", f.get("final_price", 9999)) for f in flights)

    # Cache the result
    await db.fare_cache.update_one(
        {"route": cache_key},
        {"$set": {
            "route": cache_key,
            "origin": origin,
            "destination": destination,
            "lowest_fare_eur": round(lowest, 2),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )

    return round(lowest, 2)


async def _was_alert_sent_recently(phone: str, route: str) -> bool:
    """Check if an alert was sent for this route within the last week."""
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recent = await db.fare_alerts.find_one({
        "phone": phone,
        "route": route,
        "sent_at": {"$gte": one_week_ago},
    })
    return recent is not None


async def _record_alert(phone: str, route: str, current_fare: float,
                         avg_fare: float, savings: float):
    """Record that a fare alert was sent."""
    await db.fare_alerts.insert_one({
        "phone": phone,
        "route": route,
        "current_fare_eur": current_fare,
        "avg_fare_eur": avg_fare,
        "savings_eur": savings,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "action_taken": None,
    })


async def check_and_alert_user(phone: str) -> List[Dict]:
    """Check all recurring routes for a user and send alerts if fares dropped."""
    routes = await analyze_user_routes(phone)
    alerts_sent = []

    for route_info in routes:
        route = route_info["route"]
        avg_price = route_info["avg_price_eur"]
        if avg_price <= 0:
            continue

        # Skip if alert already sent this week
        if await _was_alert_sent_recently(phone, route):
            continue

        # Check current fare
        current_fare = await check_fare_for_route(
            route_info["origin"], route_info["destination"])
        if current_fare is None:
            continue

        # Check if fare dropped > 10%
        threshold = avg_price * (1 - FARE_DROP_THRESHOLD_PCT)
        if current_fare < threshold:
            savings = round(avg_price - current_fare, 2)
            await _send_fare_alert(phone, route_info, current_fare, savings)
            await _record_alert(phone, route, current_fare, avg_price, savings)
            # Store in shadow profile
            await db.shadow_profiles.update_one(
                {"phone_number": phone},
                {"$push": {"fare_alert_history": {
                    "route": route,
                    "fare": current_fare,
                    "savings": savings,
                    "at": datetime.now(timezone.utc).isoformat(),
                }}}
            )
            alerts_sent.append({
                "route": route,
                "current_fare": current_fare,
                "avg_fare": avg_price,
                "savings": savings,
            })

    return alerts_sent


async def _send_fare_alert(phone: str, route_info: Dict, current_fare: float,
                            savings: float):
    """Send the fare alert message on all available channels."""
    from models import format_price_display
    from services.airport import get_city_name

    origin = route_info["origin"]
    dest = route_info["destination"]
    avg_price = route_info["avg_price_eur"]
    origin_name = get_city_name(origin)
    dest_name = get_city_name(dest)

    # Detect user language
    profile = await db.shadow_profiles.find_one({"phone_number": phone}, {"_id": 0})
    lang = profile.get("language_pref", "fr") if profile else "fr"
    country = profile.get("country_code", "BJ") if profile else "BJ"
    # African language users get French responses
    if lang not in ["fr", "en"]:
        lang = "fr"

    current_display = format_price_display(current_fare, country)
    avg_display = format_price_display(avg_price, country)
    savings_display = format_price_display(savings, country)

    if lang == "fr":
        msg = "*Alerte prix Travelioo*\n\n"
        msg += f"{origin_name} -> {dest_name} est a *{current_display}* ce week-end\n"
        msg += f"(vous payez habituellement {avg_display})\n\n"
        msg += f"Economie : *{savings_display}*\n\n"
        msg += "*1* Reserver maintenant\n"
        msg += "*2* Me rappeler demain"
    else:
        msg = "*Travelioo Fare Alert*\n\n"
        msg += f"{origin_name} -> {dest_name} is at *{current_display}* this weekend\n"
        msg += f"(you usually pay {avg_display})\n\n"
        msg += f"Savings: *{savings_display}*\n\n"
        msg += "*1* Book now\n"
        msg += "*2* Remind me tomorrow"

    # Send on all channels
    await _notify_all_channels(phone, msg, profile)
    logger.info(f"[FARE_ALERT] Sent to {phone[-4:]}: {origin}-{dest} {current_fare}EUR (avg {avg_price}EUR, save {savings}EUR)")


async def _notify_all_channels(phone: str, msg: str, profile: Dict = None):
    """Send on WhatsApp + Telegram if both linked."""
    set_channel(phone, "whatsapp")
    await send_whatsapp_message(phone, msg)

    if profile and profile.get("telegram_id"):
        try:
            from services.telegram import register_chat
            chat_id = int(profile["telegram_id"])
            register_chat(phone, chat_id)
            set_channel(phone, "telegram")
            await send_whatsapp_message(phone, msg)
            set_channel(phone, "whatsapp")
        except (ValueError, TypeError):
            pass


async def monitor_fares_for_all_users():
    """Background task: check fares for all users with recurring routes.
    Called periodically from server lifespan (every 24h)."""
    profiles = await db.shadow_profiles.find(
        {"travel_history.1": {"$exists": True}},  # At least 2 trips
        {"_id": 0, "phone_number": 1}
    ).to_list(500)

    total_alerts = 0
    for profile in profiles:
        phone = profile.get("phone_number")
        if not phone:
            continue
        try:
            alerts = await check_and_alert_user(phone)
            total_alerts += len(alerts)
        except Exception as e:
            logger.error(f"Fare alert error for {phone[-4:]}: {e}")

    if total_alerts > 0:
        logger.info(f"[FARE_ALERT] Sent {total_alerts} alerts across {len(profiles)} users")
