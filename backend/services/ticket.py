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
BRAND_ACCENT = "#F9A826"     # gold for round-trip badge
BRAND_WHITE = "#FFFFFF"
BRAND_MUTED = "#8B8FA3"
BRAND_LINE = "#E4E4EF"

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


def _fmt_time(iso_str: str) -> str:
    if not iso_str or "T" not in iso_str:
        return "--:--"
    try:
        return iso_str.split("T", 1)[1][:5]
    except Exception:
        return "--:--"


def _resolve_payment_context(booking: Dict, lang: str = "fr") -> tuple[str, str]:
    """Return (operator_display_name, country_name) for the booking's payment driver."""
    driver_id = booking.get("payment_driver") or booking.get("payment_method") or ""
    drv = get_driver(driver_id)
    display = drv.display_name if drv else (driver_id.replace("_", " ").title() or "Travelioo")

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


def _draw_leg(c, colors, left_x: float, leg_y: float, leg_w: float,
              label: str, airline: str, flight_num: str,
              origin_city: str, origin_code: str,
              dest_city: str, dest_code: str,
              dep_time: str, arr_time: str,
              duration: str, stops: str, mm: float):
    """Draw one flight leg block with proper column layout (no overlap)."""
    # Column positions (fractions of leg_w)
    col_origin_x = left_x
    col_dep_time_x = left_x + leg_w * 0.38
    col_middle_x = left_x + leg_w * 0.50
    col_dest_x = left_x + leg_w * 0.95
    col_arr_time_x = left_x + leg_w

    # Label (ALLER / RETOUR)
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_origin_x, leg_y, label)

    # Airline + flight number
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(col_origin_x, leg_y - 5 * mm, f"{airline}  {flight_num}")

    # Row 2: city names + times + center block — ALL on same Y axis
    row_y = leg_y - 12 * mm

    # Origin city name (left column)
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(col_origin_x, row_y, f"{origin_city} ({origin_code})")

    # Departure time (next column)
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(col_dep_time_x, row_y, dep_time)

    # Middle: duration + arrow + stops
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 9)
    c.drawString(col_middle_x, row_y + 1.5 * mm, duration)
    c.drawString(col_middle_x, row_y - 3 * mm, stops)
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(col_middle_x + leg_w * 0.17, row_y, "→")

    # Destination city (right column, right-aligned)
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(col_dest_x, row_y, f"{dest_city} ({dest_code})")

    # Arrival time (far right)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(col_arr_time_x, row_y, arr_time)

    return row_y - 4 * mm  # bottom of this leg block


def _draw_gradient_rect(c, colors, x: float, y: float, w: float, h: float,
                        color_left: str, color_right: str, steps: int = 60):
    """Draw a horizontal gradient rect by interpolating between two hex colors."""
    def _hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    r1, g1, b1 = _hex_to_rgb(color_left)
    r2, g2, b2 = _hex_to_rgb(color_right)
    step_w = w / steps
    for i in range(steps):
        t = i / (steps - 1)
        r = r1 + (r2 - r1) * t
        g = g1 + (g2 - g1) * t
        b = b1 + (b2 - b1) * t
        c.setFillColorRGB(r, g, b)
        c.rect(x + i * step_w, y, step_w + 0.5, h, stroke=0, fill=1)


def _draw_watermark(c, colors, tx: float, ty: float, tw: float, th: float, mm: float):
    """Ghost-render the TRAVELIOO logomark at very low opacity, rotated, tiled
    across the ticket so it reads as a subtle background texture."""
    c.saveState()
    try:
        c.setFillAlpha(0.06)
    except Exception:
        # Older reportlab may not support setFillAlpha — silently skip
        c.restoreState()
        return
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 42)
    # Tile diagonally
    step_x = 90 * mm
    step_y = 28 * mm
    rows = max(3, int(th / step_y) + 2)
    cols = max(3, int(tw / step_x) + 2)
    for row in range(rows):
        for col in range(cols):
            cx = tx + col * step_x - 10 * mm + (row % 2) * (step_x / 2)
            cy = ty + row * step_y
            c.saveState()
            c.translate(cx, cy)
            c.rotate(-18)
            c.drawString(0, 0, "TRAVELIOO")
            c.restoreState()
    c.restoreState()


def generate_ticket_pdf(booking: Dict) -> str:
    from reportlab.lib import colors
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

    # Build QR
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

    # Wider, shorter boarding-pass aspect ratio (~3:1 — real boarding pass proportions).
    # Custom page size instead of landscape A4.
    page_w = 340 * mm
    page_h = (130 if is_rt else 100) * mm
    c = canvas.Canvas(filepath, pagesize=(page_w, page_h))

    # Ticket fills most of the page with a small margin
    margin = 6 * mm
    tx = margin
    ty = margin
    tw = page_w - 2 * margin
    th = page_h - 2 * margin

    # Outer card
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setLineWidth(1)
    c.roundRect(tx, ty, tw, th, 5 * mm, fill=1, stroke=1)

    # Clip watermark + gradient to the rounded card area
    c.saveState()
    card_path = c.beginPath()
    card_path.roundRect(tx, ty, tw, th, 5 * mm)
    c.clipPath(card_path, stroke=0, fill=0)

    # Faint diagonal "TRAVELIOO" watermark across the full card
    _draw_watermark(c, colors, tx, ty, tw, th, mm)

    # Header bar — violet → dark gradient
    header_h = 16 * mm
    header_y = ty + th - header_h
    _draw_gradient_rect(c, colors, tx, header_y, tw, header_h, BRAND_VIOLET, BRAND_DARK)

    c.restoreState()

    # Brand wordmark
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(tx + 10 * mm, ty + th - 10 * mm, "TRAVELIOO")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(tx + 60 * mm, ty + th - 10 * mm, "Speak'n Go")

    # BOARDING PASS + trip badge (right side of header)
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(tx + tw - 10 * mm, ty + th - 7 * mm, "BOARDING PASS")

    badge_text = "ALLER-RETOUR" if is_rt else "ALLER SIMPLE"
    badge_color = BRAND_ACCENT if is_rt else BRAND_VIOLET
    c.setFillColor(colors.HexColor(badge_color))
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(tx + tw - 10 * mm, ty + th - 12 * mm, badge_text)

    # Content zone
    content_y = ty + th - header_h - 7 * mm
    left_x = tx + 10 * mm
    right_x = tx + tw - 60 * mm

    # Row 1: passenger name + booking ref
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 6.5)
    c.drawString(left_x, content_y, "PASSAGER / PASSENGER")
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_x, content_y - 4.5 * mm, booking.get("passenger_name", "N/A").upper())

    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 6.5)
    c.drawString(right_x, content_y, "REFERENCE")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 13)
    c.drawString(right_x, content_y - 4.5 * mm, booking_ref)

    # Dashed separator
    sep_y = content_y - 9 * mm
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setLineWidth(0.5)
    c.setDash(2, 3)
    c.line(left_x, sep_y, tx + tw - 10 * mm, sep_y)
    c.setDash()

    # Legs
    origin = booking.get("origin", "")
    dest = booking.get("destination", "")
    dep_time = _fmt_time(booking.get("departure_time", ""))
    arr_time = _fmt_time(booking.get("arrival_time", ""))
    duration = booking.get("duration_formatted", "") or ""
    stops = booking.get("stops_text", "") or ""
    airline = booking.get("airline", "")
    flight_num = booking.get("flight_number", "")

    leg_w = tw - 20 * mm
    leg_y = sep_y - 5 * mm

    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 6.5)
    c.drawRightString(tx + tw - 10 * mm, leg_y, f"DEPART  {booking.get('departure_date', '')}")

    bottom_out = _draw_leg(
        c, colors, left_x, leg_y, leg_w,
        "ALLER  /  OUTBOUND",
        airline, flight_num,
        get_city_name(origin), origin,
        get_city_name(dest), dest,
        dep_time, arr_time, duration, stops, mm,
    )

    if is_rt and return_leg:
        c.setStrokeColor(colors.HexColor(BRAND_LINE))
        c.setDash(2, 3)
        c.line(left_x, bottom_out - 1 * mm, tx + tw - 10 * mm, bottom_out - 1 * mm)
        c.setDash()

        ret_dep = _fmt_time(return_leg.get("departure_time", ""))
        ret_arr = _fmt_time(return_leg.get("arrival_time", ""))
        ret_dur = return_leg.get("duration_formatted", "") or ""
        ret_stops = return_leg.get("stops_text", "") or ""
        ret_airline = return_leg.get("airline") or airline
        ret_flight = return_leg.get("flight_number", "")
        ret_date = (return_leg.get("departure_time", "").split("T")[0]
                    if "T" in return_leg.get("departure_time", "") else "")

        ret_y = bottom_out - 6 * mm
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 6.5)
        c.drawRightString(tx + tw - 10 * mm, ret_y, f"RETOUR  {ret_date}")

        bottom_out = _draw_leg(
            c, colors, left_x, ret_y, leg_w,
            "RETOUR  /  RETURN",
            ret_airline, ret_flight,
            get_city_name(dest), dest,
            get_city_name(origin), origin,
            ret_dep, ret_arr, ret_dur, ret_stops, mm,
        )

    # Bottom dashed separator
    bot_sep_y = bottom_out - 3 * mm
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setDash(2, 3)
    c.line(left_x, bot_sep_y, tx + tw - 10 * mm, bot_sep_y)
    c.setDash()

    # Bottom row: Passport | Class | Price — aligned in 3 columns
    bot_y = bot_sep_y - 5 * mm

    def _field(label: str, value: str, x_pos: float, value_color=BRAND_DARK, value_size=11):
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 6.5)
        c.drawString(x_pos, bot_y, label)
        c.setFillColor(colors.HexColor(value_color))
        c.setFont("Helvetica-Bold", value_size)
        c.drawString(x_pos, bot_y - 5 * mm, value)

    passport = booking.get("passenger_passport") or "N/A"
    cat_raw = booking.get("category", "ECO")
    cat_display = CATEGORY_LABEL.get(cat_raw, str(cat_raw).upper())
    price_display = format_price_display(
        booking.get("price_eur", 0), booking.get("country_code", "BJ")
    )

    # 3 columns sized proportionally to the available width
    col1_x = left_x
    col2_x = left_x + tw * 0.30
    col3_x = left_x + tw * 0.55

    _field("PASSEPORT / PASSPORT", passport, col1_x)
    _field("CLASSE / CLASS", cat_display, col2_x)
    _field("PRIX TOTAL / TOTAL PRICE", price_display, col3_x,
           value_color=BRAND_VIOLET, value_size=13)

    # Payment badge — full-width violet strip above the footer
    pay_display, pay_country = _resolve_payment_context(booking, lang="fr")
    badge_parts = [f"Paye via {pay_display}"]
    if pay_country:
        badge_parts.append(pay_country)
    badge_parts.append(price_display)
    badge_text = "   -   ".join(badge_parts)

    badge_y = ty + 8 * mm
    badge_w = tw - 45 * mm
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.roundRect(left_x, badge_y - 1 * mm, badge_w, 5 * mm, 1 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(left_x + 3 * mm, badge_y + 0.5 * mm, badge_text)

    # QR code — bottom right, sized to fit neatly
    qr_size = 20 * mm
    c.drawImage(ImageReader(qr_buffer), tx + tw - qr_size - 6 * mm, ty + 5 * mm, qr_size, qr_size)

    # Footer (below the payment badge, above the bottom card border)
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 6.5)
    c.drawString(left_x, ty + 2.5 * mm,
                 f"Powered by Travelioo  |  {SUPPORT_PHONE}  |  {SUPPORT_SITE}")

    c.save()
    logger.info(f"[Ticket] Generated: {filename}  (trip={booking.get('trip_type', 'one_way')})")
    return filename
