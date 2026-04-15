"""Geographic payment routing — Benin (BJ) always prioritizes Celtiis Cash."""
import logging
from typing import List
import httpx
from config import IPINFO_API_KEY, UEMOA_COUNTRIES, SADC_COUNTRIES
from payment_drivers.celtiis_driver import CeltiisDriver
from payment_drivers.mtn_momo_driver import MtnMomoDriver
from payment_drivers.moov_driver import MoovDriver
from payment_drivers.stripe_driver import StripeDriver
from payment_drivers import BasePaymentDriver

logger = logging.getLogger("PaymentRouter")

# Singleton driver instances
_drivers = {
    "celtiis_cash": CeltiisDriver(),
    "mtn_momo": MtnMomoDriver(),
    "moov_money": MoovDriver(),
    "stripe": StripeDriver(),
}


def get_driver(name: str) -> BasePaymentDriver:
    return _drivers.get(name)


def get_all_drivers() -> dict:
    return _drivers


async def detect_country_from_ip(ip_address: str) -> str:
    """Detect country code from IP using ipinfo.io."""
    if not ip_address or ip_address in ["127.0.0.1", "0.0.0.0", "localhost", "unknown"]:
        return "BJ"  # Default to Benin
    try:
        url = f"https://ipinfo.io/{ip_address}/json"
        params = {}
        if IPINFO_API_KEY:
            params["token"] = IPINFO_API_KEY
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json().get("country", "BJ")
    except Exception as e:
        logger.debug(f"IP geolocation failed for {ip_address}: {e}")
    return "BJ"


def get_payment_options_for_country(country_code: str) -> List[str]:
    """Return ordered list of payment driver names for a country."""
    cc = country_code.upper()

    if cc == "BJ":
        # Benin — Celtiis Cash is exclusive priority partner
        return ["celtiis_cash", "mtn_momo", "moov_money"]

    elif cc in UEMOA_COUNTRIES:
        # UEMOA zone (Togo, Senegal, Cote d'Ivoire, Mali, Burkina, Niger, Guinea-Bissau)
        return ["mtn_momo", "moov_money"]

    elif cc in SADC_COUNTRIES:
        # Southern Africa — future TCIB rail
        return ["mtn_momo", "stripe"]

    elif cc == "NG":
        # Nigeria — future NIP/NIBSS rail
        return ["mtn_momo", "stripe"]

    else:
        # International — card-based
        return ["stripe"]


def get_payment_menu_for_country(country_code: str, lang: str = "fr") -> list:
    """Build a numbered payment menu for the user's country."""
    driver_names = get_payment_options_for_country(country_code)
    menu = []
    for i, name in enumerate(driver_names, 1):
        driver = _drivers.get(name)
        if driver:
            label = driver.display_name
            mode_tag = f" [{driver.mode}]" if driver.mode != "PRODUCTION" else ""
            menu.append({"index": i, "driver_name": name, "label": f"{label}{mode_tag}"})
    # Always add international card option at the end if not already present
    if "stripe" not in driver_names:
        stripe = _drivers.get("stripe")
        menu.append({"index": len(menu) + 1, "driver_name": "stripe",
                      "label": f"Google Pay / Apple Pay{' [' + stripe.mode + ']' if stripe.mode != 'LIVE' else ''}"})
    return menu
