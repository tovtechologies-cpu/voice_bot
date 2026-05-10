"""PDF electronic ticket — Travelioo formal e-ticket (FR/EN bilingual, A4 portrait)."""
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
BRAND_VIOLET_LIGHT = "#8B83FF"
BRAND_ACCENT = "#F9A826"
BRAND_WHITE = "#FFFFFF"
BRAND_MUTED = "#7A7F95"
BRAND_TEXT = "#22253A"
BRAND_LINE = "#E0E2EC"
BRAND_BG_SOFT = "#F6F6FB"

SUPPORT_PHONE = "+229 01 49 51 04 62"
SUPPORT_SITE = "travelioo.tech"
SUPPORT_EMAIL = "support@travelioo.tech"

CATEGORY_LABEL = {
    "PLUS_BAS": "ECO", "PLUS_RAPIDE": "EXPRESS", "PREMIUM": "PREMIUM",
    "cheapest": "ECO", "fastest": "EXPRESS", "premium": "PREMIUM",
}


def _fmt_time(iso_str: str) -> str:
    if not iso_str or "T" not in iso_str:
        return "--:--"
    try:
        return iso_str.split("T", 1)[1][:5]
    except Exception:
        return "--:--"


def _fmt_date(iso_str: str, fmt: str = "%d %b %Y") -> str:
    """Convert ISO date or datetime to a human-friendly date."""
    from datetime import datetime
    if not iso_str:
        return ""
    try:
        s = iso_str.split("T")[0] if "T" in iso_str else iso_str
        return datetime.strptime(s, "%Y-%m-%d").strftime(fmt).upper()
    except Exception:
        return iso_str


def _resolve_payment_context(booking: Dict, lang: str = "fr") -> tuple[str, str]:
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


def _draw_logo(c, colors, x: float, y: float, mm: float, scale: float = 1.0):
    """Draw the Travelioo logomark (paper plane in violet circle) + wordmark.
    Vector-only, no asset file needed. Origin point = top-left corner of the logo."""
    s = scale
    # Violet rounded square 12mm × 12mm
    box = 12 * mm * s
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.roundRect(x, y - box, box, box, 2.5 * mm * s, fill=1, stroke=0)

    # Paper-plane glyph (white) — drawn as a polygon
    cx = x + box / 2
    cy = y - box / 2
    p = c.beginPath()
    # Triangle points: tip-right, fold-mid, tail-bottom-left, tail-top-left
    pl = 4.2 * mm * s
    p.moveTo(cx + pl, cy)                 # tip
    p.lineTo(cx - pl * 0.7, cy + pl * 0.6) # top tail
    p.lineTo(cx - pl * 0.2, cy)            # mid fold
    p.lineTo(cx - pl * 0.7, cy - pl * 0.6) # bottom tail
    p.close()
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.drawPath(p, fill=1, stroke=0)
    # Inner fold line (thin dark line)
    c.setStrokeColor(colors.HexColor(BRAND_VIOLET))
    c.setLineWidth(0.6)
    c.line(cx - pl * 0.7, cy + pl * 0.6, cx - pl * 0.2, cy)
    c.line(cx - pl * 0.2, cy, cx + pl, cy)

    # Wordmark to the right of the logomark
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 16 * s)
    c.drawString(x + box + 3 * mm * s, y - 7 * mm * s, "TRAVELIOO")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Oblique", 8 * s)
    c.drawString(x + box + 3 * mm * s, y - 11 * mm * s, "Speak'n Go")


def _draw_section_title(c, colors, x: float, y: float, mm: float,
                        fr_text: str, en_text: str):
    """Bilingual section header — French primary, English secondary in muted."""
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, fr_text)
    # Right-side English (italic, muted)
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(x + 0.5 * mm + c.stringWidth(fr_text, "Helvetica-Bold", 10) + 2 * mm, y,
                 f"/ {en_text}")
    # Underline
    c.setStrokeColor(colors.HexColor(BRAND_VIOLET))
    c.setLineWidth(1.5)
    c.line(x, y - 1.5 * mm, x + 18 * mm, y - 1.5 * mm)


def generate_ticket_pdf(booking: Dict) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
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
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=BRAND_DARK, back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # ── A4 portrait ──
    page_w, page_h = A4
    c = canvas.Canvas(filepath, pagesize=A4)
    margin_x = 18 * mm
    margin_top = 18 * mm

    # ── HEADER ──
    # Logo top-left
    _draw_logo(c, colors, margin_x, page_h - margin_top, mm, scale=1.0)

    # Title block top-right
    title_x = page_w - margin_x
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(title_x, page_h - margin_top - 1 * mm, "BILLET ELECTRONIQUE")
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Oblique", 9)
    c.drawRightString(title_x, page_h - margin_top - 6 * mm, "ELECTRONIC TICKET")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 8)
    badge = "ALLER-RETOUR" if is_rt else "ALLER SIMPLE"
    c.drawRightString(title_x, page_h - margin_top - 11 * mm, badge)

    # ── BOOKING REFERENCE BAND ──
    band_y = page_h - margin_top - 22 * mm
    band_h = 18 * mm
    c.setFillColor(colors.HexColor(BRAND_BG_SOFT))
    c.rect(margin_x, band_y, page_w - 2 * margin_x, band_h, fill=1, stroke=0)

    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin_x + 4 * mm, band_y + 12 * mm, "REFERENCE DE VOTRE RESERVATION")
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(margin_x + 4 * mm, band_y + 8.5 * mm, "Your booking reference")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin_x + 4 * mm, band_y + 1.5 * mm, booking_ref)

    # Right side: airport notice
    notice_x = page_w - margin_x - 4 * mm
    c.setFillColor(colors.HexColor(BRAND_TEXT))
    c.setFont("Helvetica", 8)
    c.drawRightString(notice_x, band_y + 11 * mm,
                      "A l'aeroport, presentez une piece d'identite valide.")
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Oblique", 7)
    c.drawRightString(notice_x, band_y + 7 * mm,
                      "At the airport, present a valid ID document.")

    # ── PASSENGER + QR ROW ──
    pax_y = band_y - 8 * mm
    _draw_section_title(c, colors, margin_x, pax_y, mm, "PASSAGER", "Passenger")

    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 12)
    pax_name = booking.get("passenger_name", "N/A").upper()
    c.drawString(margin_x, pax_y - 7 * mm, pax_name)

    # Passport
    passport = booking.get("passenger_passport") or "N/A"
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7.5)
    c.drawString(margin_x, pax_y - 12 * mm, "Passeport / Passport")
    c.setFillColor(colors.HexColor(BRAND_TEXT))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_x, pax_y - 16 * mm, passport)

    # Ticket number (booking ref + sequence)
    ticket_number = f"TRV {booking_ref.replace('TRV-', '')} 001"
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7.5)
    c.drawString(margin_x + 60 * mm, pax_y - 12 * mm, "N° Billet / Ticket Number")
    c.setFillColor(colors.HexColor(BRAND_TEXT))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_x + 60 * mm, pax_y - 16 * mm, ticket_number)

    # QR code on the right
    qr_size = 28 * mm
    qr_x = page_w - margin_x - qr_size
    qr_y = pax_y - 22 * mm
    c.drawImage(ImageReader(qr_buffer), qr_x, qr_y, qr_size, qr_size)
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 3 * mm, "GAGNEZ DU TEMPS")
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 6 * mm, "Save time")

    # ── ITINERARY ──
    iti_y = pax_y - 32 * mm
    _draw_section_title(c, colors, margin_x, iti_y, mm, "ITINERAIRE", "Itinerary")

    # Itinerary table headers
    table_y = iti_y - 7 * mm
    headers = [
        ("Date", 0),
        ("Depart / Departure", 22 * mm),
        ("Arrivee / Arrival", 60 * mm),
        ("Vol / Flight", 100 * mm),
        ("Duree / Duration", 130 * mm),
        ("Classe / Class", 160 * mm),
    ]
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.rect(margin_x, table_y - 1 * mm, page_w - 2 * margin_x, 6 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 7.5)
    for label, dx in headers:
        c.drawString(margin_x + 2 * mm + dx, table_y + 1 * mm, label)

    # Outbound row
    def _draw_iti_row(row_y: float, leg_date: str,
                      org_code: str, org_city: str, org_time: str,
                      dest_code: str, dest_city: str, dest_time: str,
                      airline: str, flight_num: str,
                      duration: str, stops: str, cat_display: str):
        c.setFillColor(colors.HexColor(BRAND_TEXT))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_x + 2 * mm, row_y, _fmt_date(leg_date))
        # Departure (city + code + time)
        c.drawString(margin_x + 2 * mm + 22 * mm, row_y, f"{org_city}")
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 7)
        c.drawString(margin_x + 2 * mm + 22 * mm, row_y - 3.2 * mm, f"{org_code} - {org_time}")
        # Arrival
        c.setFillColor(colors.HexColor(BRAND_TEXT))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_x + 2 * mm + 60 * mm, row_y, f"{dest_city}")
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 7)
        c.drawString(margin_x + 2 * mm + 60 * mm, row_y - 3.2 * mm, f"{dest_code} - {dest_time}")
        # Flight
        c.setFillColor(colors.HexColor(BRAND_TEXT))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_x + 2 * mm + 100 * mm, row_y, flight_num)
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 7)
        c.drawString(margin_x + 2 * mm + 100 * mm, row_y - 3.2 * mm, airline[:18])
        # Duration + stops
        c.setFillColor(colors.HexColor(BRAND_TEXT))
        c.setFont("Helvetica", 9)
        c.drawString(margin_x + 2 * mm + 130 * mm, row_y, duration)
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica", 7)
        c.drawString(margin_x + 2 * mm + 130 * mm, row_y - 3.2 * mm, stops)
        # Class
        c.setFillColor(colors.HexColor(BRAND_VIOLET))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_x + 2 * mm + 160 * mm, row_y, cat_display)
        return row_y - 8 * mm

    cat_raw = booking.get("category", "ECO")
    cat_display = CATEGORY_LABEL.get(cat_raw, str(cat_raw).upper())

    row_y = table_y - 6 * mm
    bottom_y = _draw_iti_row(
        row_y,
        booking.get("departure_date", ""),
        booking.get("origin", ""), get_city_name(booking.get("origin", "")),
        _fmt_time(booking.get("departure_time", "")),
        booking.get("destination", ""), get_city_name(booking.get("destination", "")),
        _fmt_time(booking.get("arrival_time", "")),
        booking.get("airline", ""), booking.get("flight_number", ""),
        booking.get("duration_formatted", "") or "", booking.get("stops_text", "") or "",
        cat_display,
    )

    if is_rt and return_leg:
        # Light divider between legs
        c.setStrokeColor(colors.HexColor(BRAND_LINE))
        c.setLineWidth(0.5)
        c.setDash(1, 2)
        c.line(margin_x, bottom_y + 2 * mm, page_w - margin_x, bottom_y + 2 * mm)
        c.setDash()

        ret_date = (return_leg.get("departure_time", "").split("T")[0]
                    if "T" in return_leg.get("departure_time", "") else "")
        bottom_y = _draw_iti_row(
            bottom_y - 2 * mm,
            ret_date,
            booking.get("destination", ""), get_city_name(booking.get("destination", "")),
            _fmt_time(return_leg.get("departure_time", "")),
            booking.get("origin", ""), get_city_name(booking.get("origin", "")),
            _fmt_time(return_leg.get("arrival_time", "")),
            return_leg.get("airline") or booking.get("airline", ""),
            return_leg.get("flight_number", ""),
            return_leg.get("duration_formatted", "") or "",
            return_leg.get("stops_text", "") or "",
            cat_display,
        )

    # ── PAYMENT RECEIPT ──
    pay_y = bottom_y - 5 * mm
    _draw_section_title(c, colors, margin_x, pay_y, mm, "REÇU DE PAIEMENT", "Receipt")

    pay_display, pay_country = _resolve_payment_context(booking, lang="fr")
    price_display = format_price_display(
        booking.get("price_eur", 0), booking.get("country_code", "BJ")
    )
    fee_eur = booking.get("travelioo_fee_eur", 0) or 0
    gds_eur = booking.get("gds_price_eur", booking.get("price_eur", 0) - fee_eur)
    fee_display = format_price_display(fee_eur, booking.get("country_code", "BJ"))
    gds_display = format_price_display(gds_eur, booking.get("country_code", "BJ"))

    # Receipt table
    rt_y = pay_y - 7 * mm
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.setLineWidth(0.5)
    c.rect(margin_x, rt_y - 28 * mm, page_w - 2 * margin_x, 28 * mm, fill=0, stroke=1)

    def _receipt_row(rrow_y: float, label_fr: str, label_en: str, value: str, bold_value=False):
        c.setFillColor(colors.HexColor(BRAND_TEXT))
        c.setFont("Helvetica", 8.5)
        c.drawString(margin_x + 4 * mm, rrow_y, label_fr)
        c.setFillColor(colors.HexColor(BRAND_MUTED))
        c.setFont("Helvetica-Oblique", 7)
        c.drawString(margin_x + 4 * mm, rrow_y - 3 * mm, label_en)
        c.setFillColor(colors.HexColor(BRAND_DARK))
        c.setFont("Helvetica-Bold" if bold_value else "Helvetica", 9 if bold_value else 8.5)
        c.drawRightString(page_w - margin_x - 4 * mm, rrow_y, value)

    _receipt_row(rt_y - 4 * mm, "Methode de paiement",
                 f"Form of payment ({pay_country})" if pay_country else "Form of payment",
                 pay_display)
    _receipt_row(rt_y - 12 * mm, "Prix vol", "Flight fare", gds_display)
    _receipt_row(rt_y - 18 * mm, "Frais Travelioo", "Travelioo service fee", fee_display)

    # Total line — emphasized
    c.setStrokeColor(colors.HexColor(BRAND_LINE))
    c.line(margin_x + 4 * mm, rt_y - 22 * mm,
           page_w - margin_x - 4 * mm, rt_y - 22 * mm)
    _receipt_row(rt_y - 26 * mm, "MONTANT TOTAL", "Total cost", price_display, bold_value=True)

    # ── PRE-FLIGHT CONTACT BLOCK ──
    contact_y = rt_y - 36 * mm
    _draw_section_title(c, colors, margin_x, contact_y, mm,
                        "AVANT VOTRE DEPART", "Before your flight")

    c.setFillColor(colors.HexColor(BRAND_TEXT))
    c.setFont("Helvetica", 8.5)
    c.drawString(margin_x, contact_y - 7 * mm,
                 f"Site web : {SUPPORT_SITE}")
    c.drawString(margin_x, contact_y - 11 * mm,
                 f"Telephone / WhatsApp : {SUPPORT_PHONE}")
    c.drawString(margin_x, contact_y - 15 * mm,
                 f"E-mail : {SUPPORT_EMAIL}")
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(margin_x, contact_y - 19 * mm,
                 "Modifiez ou annulez votre reservation directement via WhatsApp / Telegram.")
    c.drawString(margin_x, contact_y - 22.5 * mm,
                 "Modify or cancel your booking directly via WhatsApp / Telegram.")

    # ── FARE RULES ──
    rules_y = contact_y - 32 * mm
    _draw_section_title(c, colors, margin_x, rules_y, mm,
                        "CONDITIONS TARIFAIRES", "Fare rules")

    rules_fr = [
        "Le tarif est valable pour un billet utilise dans l'ordre des coupons.",
        "Annulation : selon les conditions de la compagnie aerienne.",
        "Modification : penalite applicable selon la classe tarifaire.",
        "Frais Travelioo non remboursables en cas d'annulation client.",
        "L'identite du passager doit correspondre au document presente.",
    ]
    rules_en = [
        "Fare valid for a ticket used in coupon order.",
        "Cancellation: subject to airline conditions.",
        "Modification: penalty applies per fare class.",
        "Travelioo service fee non-refundable on customer cancellation.",
        "Passenger ID must match the booking name.",
    ]
    c.setFillColor(colors.HexColor(BRAND_TEXT))
    c.setFont("Helvetica", 7.5)
    for i, line in enumerate(rules_fr):
        c.drawString(margin_x, rules_y - 6 * mm - i * 3.4 * mm, f"• {line}")
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica-Oblique", 7)
    for i, line in enumerate(rules_en):
        c.drawString(page_w / 2 + 4 * mm, rules_y - 6 * mm - i * 3.4 * mm, f"• {line}")

    # ── FOOTER ──
    footer_y = 18 * mm
    c.setStrokeColor(colors.HexColor(BRAND_VIOLET))
    c.setLineWidth(2)
    c.line(margin_x, footer_y + 5 * mm, page_w - margin_x, footer_y + 5 * mm)
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin_x, footer_y + 1 * mm, "Powered by Travelioo")
    c.setFillColor(colors.HexColor(BRAND_MUTED))
    c.setFont("Helvetica", 7.5)
    c.drawString(margin_x + 36 * mm, footer_y + 1 * mm,
                 f"  |  {SUPPORT_PHONE}  |  {SUPPORT_SITE}  |  {SUPPORT_EMAIL}")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Oblique", 7)
    c.drawRightString(page_w - margin_x, footer_y + 1 * mm,
                      f"Bon voyage / Have a pleasant trip !")

    c.save()
    logger.info(f"[Ticket] Generated: {filename}  (trip={booking.get('trip_type', 'one_way')})")
    return filename
