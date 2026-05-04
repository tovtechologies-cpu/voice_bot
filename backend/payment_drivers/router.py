"""Geographic payment routing — dynamically registers a MOCK driver for every
operator declared in `services.country.COUNTRY_PAYMENT_METHODS`, plus the existing
real drivers (Celtiis, MTN MoMo, Moov, Stripe). Card alternatives via Stripe."""

import logging
from typing import List

import httpx

from config import IPINFO_API_KEY
from payment_drivers import BasePaymentDriver
from payment_drivers.celtiis_driver import CeltiisDriver
from payment_drivers.mtn_momo_driver import MtnMomoDriver
from payment_drivers.moov_driver import MoovDriver
from payment_drivers.stripe_driver import StripeDriver
from payment_drivers.mock_mobile_money import MockMobileMoneyDriver
from services.country import COUNTRY_PAYMENT_METHODS, get_country_currency

logger = logging.getLogger("PaymentRouter")

# Card / international alternatives offered as universal fallback
CARD_DRIVERS_ORDER = ["stripe", "paypal", "card_visa"]

# ─────────────────── Driver registry ───────────────────
# Real (existing) drivers map to their canonical operator id used in country list.
_REAL_DRIVER_INSTANCES = {
    "celtiis_cash": CeltiisDriver(),
    "mtn_momo": MtnMomoDriver(),         # used for legacy "mtn_momo" id
    "moov_money": MoovDriver(),          # used for legacy "moov_money" id
    "stripe": StripeDriver(),            # used for stripe + as fallback for paypal/card
}


def _build_drivers() -> dict:
    """Build the full driver registry: real drivers + 1 mock per operator id from
    the country map. Real drivers always take precedence (e.g. celtiis_cash)."""
    registry: dict[str, BasePaymentDriver] = {}

    # 1) seed real drivers
    for k, drv in _REAL_DRIVER_INSTANCES.items():
        registry[k] = drv

    # 2) seed MOCK drivers for every operator listed in the country map
    for country_code, operators in COUNTRY_PAYMENT_METHODS.items():
        currency = get_country_currency(country_code)
        for op in operators:
            op_id = op["id"]
            if op_id in registry:
                continue  # don't overwrite real drivers (e.g. celtiis_cash)
            registry[op_id] = MockMobileMoneyDriver(op_id, op["name"], currency)

    # 3) seed mock card alternatives (PayPal, generic Visa) — Stripe is real
    if "paypal" not in registry:
        registry["paypal"] = MockMobileMoneyDriver("paypal", "PayPal", "USD")
    if "card_visa" not in registry:
        registry["card_visa"] = MockMobileMoneyDriver("card_visa", "Carte Visa / Mastercard", "EUR")

    return registry


_drivers: dict[str, BasePaymentDriver] = _build_drivers()


def get_driver(name: str) -> BasePaymentDriver:
    return _drivers.get(name)


def get_all_drivers() -> dict:
    return _drivers


async def detect_country_from_ip(ip_address: str) -> str:
    """Detect country code from IP using ipinfo.io. Default BJ."""
    if not ip_address or ip_address in ["127.0.0.1", "0.0.0.0", "localhost", "unknown"]:
        return "BJ"
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


# ─────────────────── Menu builders ───────────────────

def get_country_mobile_methods(country_code: str) -> List[dict]:
    """Return the list of mobile-money operators for a country (ordered).
    Each item: {id, name, currency}."""
    cc = (country_code or "").upper()
    operators = COUNTRY_PAYMENT_METHODS.get(cc, [])
    currency = get_country_currency(cc)
    return [{"id": op["id"], "name": op["name"], "currency": currency} for op in operators]


def get_payment_options_for_country(country_code: str) -> List[str]:
    """Return ordered list of payment driver ids for a country.
    Mobile money first, then international card alternatives."""
    ids = [op["id"] for op in get_country_mobile_methods(country_code)]
    # always offer card alternatives at the end
    for fallback in CARD_DRIVERS_ORDER:
        if fallback not in ids:
            ids.append(fallback)
    return ids


def get_payment_menu_for_country(country_code: str, lang: str = "fr") -> list:
    """Build a numbered payment menu for the user's country.
    Returns list of dicts: {index, driver_name, label, group}"""
    cc = (country_code or "").upper()
    mobile = get_country_mobile_methods(cc)
    menu = []
    idx = 1

    # Group 1: country-native mobile money
    for op in mobile:
        drv = _drivers.get(op["id"])
        if not drv:
            continue
        mode_tag = f" [{drv.mode}]" if drv.mode != "PRODUCTION" else ""
        menu.append({
            "index": idx, "driver_name": op["id"], "label": f"{drv.display_name}{mode_tag}",
            "group": "mobile_money", "country": cc,
        })
        idx += 1

    # Group 2: international card alternatives
    for fallback in CARD_DRIVERS_ORDER:
        drv = _drivers.get(fallback)
        if not drv:
            continue
        mode_tag = f" [{drv.mode}]" if drv.mode != "PRODUCTION" else ""
        # Friendly label
        if fallback == "stripe":
            label = f"Google Pay / Apple Pay{mode_tag}"
        else:
            label = f"{drv.display_name}{mode_tag}"
        menu.append({
            "index": idx, "driver_name": fallback, "label": label,
            "group": "card", "country": "INTL",
        })
        idx += 1

    # Group 3: "other country mobile money" entry — handled by a separate sub-flow
    menu.append({
        "index": idx,
        "driver_name": "__other_country__",
        "label": "Autre pays (mobile money)" if lang == "fr" else "Other country (mobile money)",
        "group": "switch_country", "country": "*",
    })

    return menu


def list_supported_countries(lang: str = "fr") -> list:
    """Return list of {code, name, count} for countries with mobile money support.
    Used by the 'other country' selector."""
    # Country names — minimal map, French primary
    NAMES_FR = {
        "BJ": "Bénin", "TG": "Togo", "SN": "Sénégal", "CI": "Côte d'Ivoire",
        "ML": "Mali", "BF": "Burkina Faso", "NE": "Niger", "GN": "Guinée",
        "GW": "Guinée-Bissau", "GH": "Ghana", "NG": "Nigeria", "SL": "Sierra Leone",
        "LR": "Liberia", "GM": "Gambie", "MR": "Mauritanie", "CV": "Cabo Verde",
        "CM": "Cameroun", "GA": "Gabon", "CG": "Congo", "CD": "RDC",
        "CF": "Centrafrique", "TD": "Tchad", "GQ": "Guinée Équatoriale", "ST": "Sao Tomé",
        "MA": "Maroc", "DZ": "Algérie", "TN": "Tunisie", "LY": "Libye",
        "EG": "Égypte", "SD": "Soudan", "SS": "Soudan du Sud",
        "ET": "Éthiopie", "DJ": "Djibouti", "SO": "Somalie",
        "KE": "Kenya", "TZ": "Tanzanie", "UG": "Ouganda", "RW": "Rwanda", "BI": "Burundi",
        "ZA": "Afrique du Sud", "ZW": "Zimbabwe", "ZM": "Zambie", "MW": "Malawi",
        "MZ": "Mozambique", "AO": "Angola", "BW": "Botswana", "NA": "Namibie",
        "LS": "Lesotho", "SZ": "Eswatini", "MG": "Madagascar", "MU": "Maurice",
        "RE": "La Réunion", "SC": "Seychelles", "KM": "Comores",
    }
    NAMES_EN = {
        "BJ": "Benin", "TG": "Togo", "SN": "Senegal", "CI": "Ivory Coast",
        "ML": "Mali", "BF": "Burkina Faso", "NE": "Niger", "GN": "Guinea",
        "GW": "Guinea-Bissau", "GH": "Ghana", "NG": "Nigeria", "SL": "Sierra Leone",
        "LR": "Liberia", "GM": "Gambia", "MR": "Mauritania", "CV": "Cabo Verde",
        "CM": "Cameroon", "GA": "Gabon", "CG": "Congo", "CD": "DRC",
        "CF": "Central African Republic", "TD": "Chad", "GQ": "Equatorial Guinea", "ST": "Sao Tome",
        "MA": "Morocco", "DZ": "Algeria", "TN": "Tunisia", "LY": "Libya",
        "EG": "Egypt", "SD": "Sudan", "SS": "South Sudan",
        "ET": "Ethiopia", "DJ": "Djibouti", "SO": "Somalia",
        "KE": "Kenya", "TZ": "Tanzania", "UG": "Uganda", "RW": "Rwanda", "BI": "Burundi",
        "ZA": "South Africa", "ZW": "Zimbabwe", "ZM": "Zambia", "MW": "Malawi",
        "MZ": "Mozambique", "AO": "Angola", "BW": "Botswana", "NA": "Namibia",
        "LS": "Lesotho", "SZ": "Eswatini", "MG": "Madagascar", "MU": "Mauritius",
        "RE": "Réunion", "SC": "Seychelles", "KM": "Comoros",
    }
    names = NAMES_FR if lang == "fr" else NAMES_EN
    result = []
    for code, ops in COUNTRY_PAYMENT_METHODS.items():
        result.append({"code": code, "name": names.get(code, code), "count": len(ops)})
    # Sort alphabetically by display name
    result.sort(key=lambda x: x["name"])
    return result
