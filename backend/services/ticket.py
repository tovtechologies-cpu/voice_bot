"""PDF ticket generation — Travelioo boarding pass style."""
import json
import logging
from typing import Dict
from config import TICKETS_DIR
from services.airport import get_city_name

logger = logging.getLogger("TicketService")

# Travelioo brand colors
BRAND_DARK = "#0A0F1E"
BRAND_VIOLET = "#6C63FF"
BRAND_WHITE = "#FFFFFF"
BRAND_LIGHT_BG = "#F4F3FF"


def generate_ticket_pdf(booking: Dict) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    import qrcode
    from io import BytesIO

    booking_ref = booking.get('booking_ref', 'TRV-XXXXXX')
    filename = f"travelioo_ticket_{booking_ref}.pdf"
    filepath = str(TICKETS_DIR / filename)

    # QR code
    qr_data = json.dumps({"ref": booking_ref, "pax": booking.get('passenger_name', ''), "route": f"{booking.get('origin')}-{booking.get('destination')}"})
    qr = qrcode.QRCode(version=1, box_size=8, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=BRAND_DARK, back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    # Create landscape A4 canvas
    w, h = landscape(A4)
    c = canvas.Canvas(filepath, pagesize=landscape(A4))

    # Ticket dimensions (centered on page)
    tw, th = 260 * mm, 130 * mm
    tx = (w - tw) / 2
    ty = (h - th) / 2

    # Background card with rounded corners
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setStrokeColor(colors.HexColor("#E0E0E0"))
    c.setLineWidth(1)
    c.roundRect(tx, ty, tw, th, 8 * mm, fill=1, stroke=1)

    # Header bar
    header_h = 22 * mm
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.roundRect(tx, ty + th - header_h, tw, header_h, 8 * mm, fill=1, stroke=0)
    # Cover bottom rounded corners of header
    c.rect(tx, ty + th - header_h, tw, 8 * mm, fill=1, stroke=0)

    # Header text
    c.setFillColor(colors.HexColor(BRAND_WHITE))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(tx + 12 * mm, ty + th - 15 * mm, "TRAVELIOO")
    c.setFont("Helvetica", 10)
    c.drawString(tx + 70 * mm, ty + th - 15 * mm, "Speak'n Go")

    # Boarding pass label
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(tx + tw - 12 * mm, ty + th - 14 * mm, "BOARDING PASS")

    # Content area
    content_y = ty + th - header_h - 8 * mm
    left_x = tx + 14 * mm

    # Passenger name
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawString(left_x, content_y, "PASSENGER NAME / NOM DU PASSAGER")
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left_x, content_y - 6 * mm, booking.get('passenger_name', 'N/A').upper())

    # Flight number (right side)
    right_x = tx + 160 * mm
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawString(right_x, content_y, "FLIGHT / VOL")
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 14)
    flight_num = booking.get('flight_number', '')
    airline = booking.get('airline', '')
    c.drawString(right_x, content_y - 6 * mm, f"{airline} {flight_num}")

    # Separator line
    sep_y = content_y - 14 * mm
    c.setStrokeColor(colors.HexColor("#E0E0E0"))
    c.setLineWidth(0.5)
    c.line(left_x, sep_y, tx + tw - 14 * mm, sep_y)

    # FROM / TO section
    row2_y = sep_y - 6 * mm
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawString(left_x, row2_y, "FROM / DE")
    c.drawString(left_x + 80 * mm, row2_y, "TO / A")

    origin = booking.get('origin', '')
    dest = booking.get('destination', '')
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_x, row2_y - 6 * mm, f"{get_city_name(origin)} ({origin})")
    c.drawString(left_x + 80 * mm, row2_y - 6 * mm, f"{get_city_name(dest)} ({dest})")

    # Arrow between cities
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left_x + 65 * mm, row2_y - 6 * mm, "->")

    # DATE / TIME / CLASS / SEAT row
    row3_y = row2_y - 18 * mm
    labels = ["DATE", "TIME / HEURE", "CLASS / CLASSE", "SEAT / SIEGE"]
    values = [
        booking.get('departure_date', 'N/A'),
        booking.get('departure_time', '').split('T')[1][:5] if 'T' in booking.get('departure_time', '') else 'N/A',
        booking.get('category', 'ECO'),
        "TBD"
    ]
    col_widths = [55 * mm, 40 * mm, 55 * mm, 40 * mm]
    col_x = left_x
    for i, (label, value) in enumerate(zip(labels, values)):
        c.setFillColor(colors.HexColor("#666666"))
        c.setFont("Helvetica", 8)
        c.drawString(col_x, row3_y, label)
        c.setFillColor(colors.HexColor(BRAND_DARK))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col_x, row3_y - 5 * mm, str(value))
        col_x += col_widths[i]

    # Bottom separator
    bot_sep_y = row3_y - 12 * mm
    c.setStrokeColor(colors.HexColor("#E0E0E0"))
    c.setDash(3, 3)
    c.line(left_x, bot_sep_y, tx + tw - 14 * mm, bot_sep_y)
    c.setDash()

    # Bottom row: Booking ref + QR code
    bot_y = bot_sep_y - 6 * mm
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawString(left_x, bot_y, "BOOKING REF / REFERENCE")
    c.setFillColor(colors.HexColor(BRAND_VIOLET))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_x, bot_y - 8 * mm, booking_ref)

    # Passport
    passport = booking.get('passenger_passport') or 'N/A'
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 80 * mm, bot_y, "PASSPORT")
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_x + 80 * mm, bot_y - 8 * mm, passport)

    # Price
    price_eur = booking.get('price_eur', 0)
    price_xof = booking.get('price_xof', 0)
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 8)
    c.drawString(left_x + 140 * mm, bot_y, "PRICE / PRIX")
    c.setFillColor(colors.HexColor(BRAND_DARK))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_x + 140 * mm, bot_y - 8 * mm, f"{price_eur}EUR")

    # QR Code (right side)
    from reportlab.lib.utils import ImageReader
    qr_reader = ImageReader(qr_buffer)
    qr_size = 28 * mm
    c.drawImage(qr_reader, tx + tw - 42 * mm, ty + 6 * mm, qr_size, qr_size)

    # Footer
    c.setFillColor(colors.HexColor("#999999"))
    c.setFont("Helvetica", 7)
    c.drawString(left_x, ty + 4 * mm, "Powered by Travelioo | +229 01 29 88 83 69 | travelioo.tech")

    c.save()
    logger.info(f"[Ticket] Generated: {filename}")
    return filename
