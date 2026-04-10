"""PDF ticket generation service."""
import json
import logging
from typing import Dict
from config import TICKETS_DIR
from models import PaymentOperator
from services.airport import get_city_name

logger = logging.getLogger("TicketService")


def generate_ticket_pdf(booking: Dict) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    import qrcode
    from io import BytesIO

    booking_ref = booking.get('booking_ref', 'TRV-XXXXXX')
    filename = f"travelio_ticket_{booking_ref}.pdf"
    filepath = TICKETS_DIR / filename

    qr_data = json.dumps({"ref": booking_ref, "passenger": booking.get('passenger_name', 'N/A'), "route": f"{booking.get('origin')} -> {booking.get('destination')}", "date": booking.get('departure_date'), "verify": f"/api/verify_qr/{booking_ref}"})
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    doc = SimpleDocTemplate(str(filepath), pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#6C63FF'), alignment=TA_CENTER)
    elements = []
    elements.append(Paragraph("TRAVELIO", title_style))
    elements.append(Paragraph("Votre billet electronique", ParagraphStyle('Sub', fontSize=12, textColor=colors.gray, alignment=TA_CENTER)))
    elements.append(Spacer(1, 20))
    qr_image = Image(qr_buffer, width=80, height=80)

    payment_method_display = {PaymentOperator.MTN_MOMO: "MTN MoMo", PaymentOperator.MOOV_MONEY: "Moov Money", PaymentOperator.GOOGLE_PAY: "Google Pay", PaymentOperator.APPLE_PAY: "Apple Pay"}.get(booking.get('payment_method'), booking.get('payment_method', 'N/A'))

    ticket_data = [
        [Paragraph("<b>BOARDING PASS</b>", ParagraphStyle('BP', fontSize=14, textColor=colors.white)), qr_image],
        ["", ""],
        ["Passager", booking.get('passenger_name', 'Guest')],
        ["Passeport", booking.get('passenger_passport') or 'N/A'],
        ["De", f"{get_city_name(booking.get('origin', ''))} ({booking.get('origin')})"],
        ["A", f"{get_city_name(booking.get('destination', ''))} ({booking.get('destination')})"],
        ["Vol", f"{booking.get('airline')} {booking.get('flight_number')}"],
        ["Date", booking.get('departure_date')],
        ["Categorie", booking.get('category', 'Standard')],
        ["Prix", f"{booking.get('price_eur')}EUR ({booking.get('price_xof'):,} XOF)"],
        ["Paiement", payment_method_display],
        ["Reference", f"*{booking_ref}*"],
    ]

    table = Table(ticket_data, colWidths=[80 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C63FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('SPAN', (1, 0), (1, 1)),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('FONTNAME', (1, 2), (1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 2), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 2), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Scannez le QR code pour verifier - Bon voyage!", ParagraphStyle('Footer', fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))
    doc.build(elements)
    return filename
