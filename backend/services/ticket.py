"""PDF ticket generation — Travelioo boarding pass style (FCFA only, round-trip aware)."""
import json
import logging
from typing import Dict
from config import TICKETS_DIR
from services.airport import get_city_name
from services.country import COUNTRY_PAYMENT_METHODS
from payment_drivers.router import get_driver, list_supported_countries
from models import format_price_display

logger = logging.getLogger("TicketService")

# Travelioo brand
BRAND_DARK = "#0A0F1E"
BRAND_VIOLET = "#6C63FF"
BRAND_ACCENT = "#F9A826"     # gold accent for "ROUND-TRIP" badge
BRAND_WHITE = "#FFFFFF"
BRAND_MUTED = "#8B8FA3"
BRAND_LINE = "#E4E4EF"
BRAND_BG = "#FBFBFE"

SUPPORT_PHONE = "+229 01 49 51 04 62"
SUPPORT_SITE = "travelioo.tech"

CATEGORY_LABEL = {
    "PLUS_BAS": "ECO",
    "PLUS_RAPIDE": "EXPRESS",
    "PREMIUM": "PREMIUM",
    "cheapest": "ECO",
    "fastest": "EXPRESS",
    "premium": "PREMIUM",
}


def _resolve_payment_context(booking: Dict, lang: str = "fr") -> tuple[str, str]:
    """Return (operator_display_name, country_name) for the payment driver used.
    Falls back to ('Travelioo', '') if driver or country can't be resolved."""
    driver_id = booking.get("payment_driver") or booking.get("payment_method") or ""
    drv = get_driver(driver_id)
    display = drv.display_name if drv else driver_id.replace("_", " ").title() or "Travelioo"

    # Reverse lookup operator id -> country code
    op_country = None
    for cc, ops in COUNTRY_PAYMENT_METHODS.items():
        if any(op["id"] == driver_id for op in ops):
            op_country = cc
            break

    country_name = ""
    if op_country:
        names = {c["code"]: c["name"] for c in list_supported_countries(lang)}
        country_name = names.get(op_country, op_country)
    elif driver_id in ("stripe", "paypal", "card_visa"):
        country_name = "International"
    return display, country_name


def _fmt_time(iso_str: str) -> str:
    """Extract HH:MM from an ISO timestamp; return '--:--' if missing."""
    if not iso_str or "T" not in iso_str:
        return "--:--"
    try:
        return iso_str.split("T", 1)[1][:5]
    except Exception:
        return "--:--"


def _draw_leg(c, x, y, w, label, airline, flight_num, origin, dest,
              dep_time, arr_time, duration, stops, colors_mod, BRAND_DARK, BRAND_MUTED, BRAND_VIOLET):
    """Draw one flight leg block. Returns the bottom Y coordinate."""
    mm = 2.834645669  # 1 mm in points
    # Leg label (ALLER / RETOUR)
    c.setFillColor(colors_mod.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, label)

    # Airline + flight number
    c.setFillColor(colors_mod.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y - 5 * mm, f"{airline}  {flight_num}")

    # Route with times
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y - 12 * mm, origin)
    c.drawString(x + 28 * mm, y - 12 * mm, dep_time)

    c.setFillColor(colors_mod.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 9)
    c.drawString(x + 48 * mm, y - 12 * mm, f"{duration}  {stops}")

    c.setFillColor(colors_mod.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(x + w, y - 12 * mm, arr_time)
    c.drawRightString(x + w - 22 * mm, y - 12 * mm, dest)

    # Arrow
    c.setFillColor(colors_mod.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x + w / 2, y - 12 * mm, "→")

    return y - 16 * mm


def generate_ticket_pdf(booking: Dict) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    import qrcode
    from io import BytesIO

    booking_ref = booking.get("booking_ref", "TRV-XXXXXX")
    filename = f"travelioo_ticket_{booking_ref}.pdf"
    filepath = str(TICKETS_DIR / filename)

    is_rt = booking.get("trip_type") == "round_trip" or bool(booking.get("return_leg"))
    return_leg = booking.get("return_leg") or {}

    # QR encodes the booking ref + route summary
    route_str = f"{booking.get('origin')}-{booking.get('destination')}"
    if is_rt:
        route_str += f"-{booking.get('origin')}"
    qr_payload = json.dumps({
        "ref": booking_ref,
        "pax": booking.get("passenger_name", ""),
        "route": route_str,
        "trip": "RT" if is_rt else "OW",
    })
    qr = qrcode.QRCode(version=1, box_size=8, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=BRAND_DARK, back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Canvas
    w, h = landscape(A4)
    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # Ticket dims — add 10mm for the payment badge row
    tw = 260 * mm
    th = (155 * mm if is_rt else 130 * mm) + 10 * mm
    tx = (w - tw) / 2
    ty = (h - th) / 2

    # Outer card
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setLineWidth(1)
    c.roundRect(tx, ty, tw, th, 8 * mm, fill=1, stroke=1)

    # Header bar
    header_h = 22 * mm
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.roundRect(tx, ty + th - header_h, tw, header_h, 8 * mm, fill=1, stroke=0)
    c.rect(tx, ty + th - header_h, tw, 8 * mm, fill=1, stroke=0)

    # Brand wordmark
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 17)
    c.drawString(tx + 12 * mm, ty + th - 14 * mm, "TRAVELIOO")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(tx + 67 * mm, ty + th - 14 * mm, "Speak'n Go")

    # BOARDING PASS + trip badge
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(tx + tw - 12 * mm, ty + th - 10 * mm, "BOARDING PASS")

    badge_text = "ALLER-RETOUR" if is_rt else "ALLER SIMPLE"
    badge_color = BRAND_ACCENT if is_rt else BRAND_VIOLET
    c.setFillColor(colors.HexColor(badge_color))
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(tx + tw - 12 * mm, ty + th - 17 * mm, badge_text)

    # Content region
    content_y = ty + th - header_h - 8 * mm
    left_x = tx + 14 * mm

    # Row 1: Passenger + Booking ref
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7)
    c.drawString(left_x, content_y, "PASSAGER / PASSENGER")
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left_x, content_y - 5.5 * mm, booking.get("passenger_name", "N/A").upper())

    right_x = tx + 180 * mm
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7)
    c.drawString(right_x, content_y, "REFERENCE")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(right_x, content_y - 5.5 * mm, booking_ref)

    # Dashed separator
    sep_y = content_y - 11 * mm
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setLineWidth(0.5)
    c.setDash(2, 3)
    c.line(left_x, sep_y, tx + tw - 14 * mm, sep_y)
    c.setDash()

    # --- OUTBOUND LEG ---
    origin = booking.get("origin", "")
    dest = booking.get("destination", "")
    dep_time = _fmt_time(booking.get("departure_time", ""))
    arr_time = _fmt_time(booking.get("arrival_time", ""))
    duration = booking.get("duration_formatted", "") or ""
    stops = booking.get("stops_text", "") or ""
    airline = booking.get("airline", "")
    flight_num = booking.get("flight_number", "")

    leg_w = tw - 28 * mm
    leg_y = sep_y - 5 * mm

    # Outbound date label
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7)
    c.drawRightString(tx + tw - 14 * mm, leg_y, f"DEPART  {booking.get('departure_date', '')}")

    bottom_out = _draw_leg(
        c, left_x, leg_y, leg_w,
        "ALLER  /  OUTBOUND",
        airline, flight_num,
        f"{get_city_name(origin)} ({origin})",
        f"{get_city_name(dest)} ({dest})",
        dep_time, arr_time, duration, stops,
        colors, BRAND_DARK, BRAND_MUTED, BRAND_VIOLET,
    )

    # --- RETURN LEG (round-trip only) ---
    if is_rt and return_leg:
        # Small divider
        c.setStrokeColor(colors.HexColor(BRAND_LINE))
        c.setDash(2, 3)
        c.line(left_x, bottom_out - 2 * mm, tx + tw - 14 * mm, bottom_out - 2 * mm)
        c.setDash()

        ret_dep = _fmt_time(return_leg.get("departure_time", ""))
        ret_arr = _fmt_time(return_leg.get("arrival_time", ""))
        ret_dur = return_leg.get("duration_formatted", "") or ""
        ret_stops = return_leg.get("stops_text", "") or ""
        ret_airline = return_leg.get("airline") or airline
        ret_flight = return_leg.get("flight_number", "")
        ret_date = (return_leg.get("departure_time", "").split("T")[0]
                    if "T" in return_leg.get("departure_time", "") else "")

        ret_y = bottom_out - 7 * mm
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 7)
        c.drawRightString(tx + tw - 14 * mm, ret_y, f"RETOUR  {ret_date}")

        bottom_out = _draw_leg(
            c, left_x, ret_y, leg_w,
            "RETOUR  /  RETURN",
            ret_airline, ret_flight,
            f"{get_city_name(dest)} ({dest})",
            f"{get_city_name(origin)} ({origin})",
            ret_dep, ret_arr, ret_dur, ret_stops,
            colors, BRAND_DARK, BRAND_MUTED, BRAND_VIOLET,
        )

    # Bottom dashed separator
    bot_sep_y = bottom_out - 4 * mm
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setDash(2, 3)
    c.line(left_x, bot_sep_y, tx + tw - 14 * mm, bot_sep_y)
    c.setDash()

    # Bottom row: Passport | Class | Price | QR
    bot_y = bot_sep_y - 6 * mm

    def _field(label: str, value: str, x_pos: float):
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 7)
        c.drawString(x_pos, bot_y, label)
        c.setFillColor(colors.HexColor(BRAND_DARK))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x_pos, bot_y - 6 * mm, value)

    passport = booking.get("passenger_passport") or "N/A"
    cat_raw = booking.get("category", "ECO")
    cat_display = CATEGORY_LABEL.get(cat_raw, str(cat_raw).upper())

    price_display = format_price_display(booking.get("price_eur", 0), booking.get("country_code", "BJ"))

    _field("PASSEPORT / PASSPORT", passport, left_x)
    _field("CLASSE / CLASS", cat_display, left_x + 70 * mm)
    # Price — highlighted in violet
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7)
    c.drawString(left_x + 130 * mm, bot_y, "PRIX TOTAL / TOTAL PRICE")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left_x + 130 * mm, bot_y - 6 * mm, price_display)

    # Payment badge — "Payé via X — Country — Amount" — sits above the footer
    pay_display, pay_country = _resolve_payment_context(booking, lang="fr")
    badge_parts = [f"Paye via {pay_display}"]
    if pay_country:
        badge_parts.append(pay_country)
    badge_parts.append(price_display)
    badge_text = "   -   ".join(badge_parts)

    badge_y = ty + 10 * mm
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.roundRect(left_x, badge_y - 1 * mm, tw - 46 * mm, 5.5 * mm, 1.5 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(left_x + 3 * mm, badge_y + 0.8 * mm, badge_text)

    # QR code (right)
    qr_reader = ImageReader(qr_buffer)
    qr_size = 24 * mm
    c.drawImage(qr_reader, tx + tw - 32 * mm, ty + 6 * mm, qr_size, qr_size)

    # Footer (below the payment badge)
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7)
    c.drawString(left_x, ty + 3 * mm,
                 f"Powered by Travelioo  |  {SUPPORT_PHONE}  |  {SUPPORT_SITE}")

    c.save()
    logger.info(f"[Ticket] Generated: {filename}  (trip={booking.get('trip_type', 'one_way')})")
    return filename
