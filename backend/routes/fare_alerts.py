"""Fare alert routes — Predictive Fare Alerts API."""
import logging
from fastapi import APIRouter
from services.fare_alerts import (
    analyze_user_routes, check_and_alert_user, check_fare_for_route
)
from database import db

router = APIRouter(prefix="/fare-alerts")
logger = logging.getLogger("FareAlertRoutes")


@router.get("/routes/{phone}")
async def get_recurring_routes(phone: str):
    """Get recurring routes for a user based on travel history."""
    routes = await analyze_user_routes(phone)
    return {"phone": phone, "recurring_routes": routes, "count": len(routes)}


@router.post("/check/{phone}")
async def check_alerts(phone: str):
    """Check and send fare alerts for a user's recurring routes."""
    alerts = await check_and_alert_user(phone)
    return {"phone": phone, "alerts_sent": alerts, "count": len(alerts)}


@router.get("/fare/{origin}/{destination}")
async def get_current_fare(origin: str, destination: str):
    """Get current lowest fare for a route."""
    fare = await check_fare_for_route(origin.upper(), destination.upper())
    if fare is None:
        return {"error": "No fare data available", "origin": origin, "destination": destination}
    return {"origin": origin.upper(), "destination": destination.upper(), "lowest_fare_eur": fare}


@router.get("/history/{phone}")
async def get_alert_history(phone: str, limit: int = 20):
    """Get fare alert history for a user."""
    alerts = await db.fare_alerts.find(
        {"phone": phone}, {"_id": 0}
    ).sort("sent_at", -1).limit(limit).to_list(limit)
    return {"phone": phone, "alerts": alerts, "count": len(alerts)}
