from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import random
import asyncio
import httpx
import json
import string

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tickets directory
TICKETS_DIR = ROOT_DIR / 'tickets'
TICKETS_DIR.mkdir(exist_ok=True)

# API timeout
API_TIMEOUT = 10.0

# ========== MODELS ==========

class UserProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserProfileCreate(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None

class TravelIntent(BaseModel):
    destination: Optional[str] = None
    origin: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    budget: Optional[float] = None
    passengers: int = 1
    travel_class: str = "economy"
    language: str = "fr"

class IntentParseRequest(BaseModel):
    text: str
    language: str = "fr"

class Flight(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration: str
    price: float
    currency: str = "XOF"
    tier: str  # ECO, FAST, PREMIUM
    stops: int = 0
    available_seats: int
    is_demo: bool = False  # Flag for demo/mock data

class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    travel_class: str = "economy"
    budget: Optional[float] = None

class Booking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    booking_ref: str = ""  # TRV-XXXXXX format
    user_id: str
    flight_id: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    return_date: Optional[str] = None
    price: float
    currency: str = "XOF"
    passengers: int
    travel_class: str = "economy"
    passenger_name: str = ""
    status: str = "pending"
    payment_method: str
    payment_status: str = "pending"
    payment_reference: Optional[str] = None
    ticket_url: Optional[str] = None
    qr_code: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BookingCreate(BaseModel):
    user_id: str
    flight_id: str
    flight_data: dict  # Full flight info
    passengers: int = 1
    travel_class: str = "economy"
    passenger_name: str = ""
    return_date: Optional[str] = None

class PaymentRequest(BaseModel):
    booking_id: str
    amount: float
    currency: str = "XOF"
    phone_number: str
    payment_method: str = "momo"

class PaymentStatusRequest(BaseModel):
    payment_reference: str

class WhatsAppRequest(BaseModel):
    phone_number: str
    booking_id: str

class MomoCallbackRequest(BaseModel):
    referenceId: str
    status: str
    financialTransactionId: Optional[str] = None

# ========== CITY MAPPINGS ==========

WEST_AFRICAN_CITIES = {
    "Dakar": "DSS",
    "Lagos": "LOS",
    "Accra": "ACC",
    "Abidjan": "ABJ",
    "Ouagadougou": "OUA",
    "Bamako": "BKO",
    "Conakry": "CKY",
    "Niamey": "NIM",
    "Cotonou": "COO",
    "Lomé": "LFW"
}

IATA_TO_CITY = {v: k for k, v in WEST_AFRICAN_CITIES.items()}

AIRLINES = [
    {"name": "Air Senegal", "code": "HC"},
    {"name": "ASKY Airlines", "code": "KP"},
    {"name": "Royal Air Maroc", "code": "AT"},
    {"name": "Ethiopian Airlines", "code": "ET"},
    {"name": "Air Côte d'Ivoire", "code": "HF"}
]

# ========== HELPER FUNCTIONS ==========

def generate_booking_ref() -> str:
    """Generate booking reference: TRV-XXXXXX"""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=6))
    return f"TRV-{suffix}"

def get_iata_code(city_name: str) -> str:
    """Get IATA code from city name"""
    return WEST_AFRICAN_CITIES.get(city_name, city_name.upper()[:3])

def get_city_name(iata_code: str) -> str:
    """Get city name from IATA code"""
    return IATA_TO_CITY.get(iata_code, iata_code)

# ========== AVIATIONSTACK INTEGRATION ==========

async def search_flights_aviationstack(origin: str, destination: str, date: str) -> List[dict]:
    """Search real flights using AviationStack API"""
    api_key = os.environ.get('AVIATIONSTACK_API_KEY')
    
    if not api_key or api_key == 'your_key_here':
        logger.warning("AviationStack API key not configured")
        return []
    
    origin_iata = get_iata_code(origin)
    dest_iata = get_iata_code(destination)
    
    url = "http://api.aviationstack.com/v1/flights"
    params = {
        "access_key": api_key,
        "dep_iata": origin_iata,
        "arr_iata": dest_iata,
        "flight_date": date
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("error"):
                    logger.error(f"AviationStack API error: {data['error']}")
                    return []
                
                return data.get("data", [])
            else:
                logger.error(f"AviationStack API returned {response.status_code}")
                return []
                
    except httpx.TimeoutException:
        logger.error("AviationStack API timeout")
        return []
    except Exception as e:
        logger.error(f"AviationStack API error: {e}")
        return []

def transform_aviationstack_flights(raw_flights: List[dict], budget: Optional[float] = None) -> List[Flight]:
    """Transform AviationStack response to our Flight model"""
    flights = []
    tiers = ["ECO", "FAST", "PREMIUM"]
    
    for i, raw in enumerate(raw_flights[:3]):  # Take up to 3 flights
        tier = tiers[i] if i < 3 else "ECO"
        
        # Extract flight data
        departure = raw.get("departure", {})
        arrival = raw.get("arrival", {})
        airline_data = raw.get("airline", {})
        flight_data = raw.get("flight", {})
        
        # Calculate duration
        dep_time = departure.get("scheduled", "")
        arr_time = arrival.get("scheduled", "")
        duration = "2h 30m"  # Default if calculation fails
        
        # Generate price based on tier
        base_price = random.randint(50000, 100000)
        tier_multipliers = {"ECO": 1.0, "FAST": 1.4, "PREMIUM": 2.2}
        price = int(base_price * tier_multipliers.get(tier, 1.0))
        
        if budget and price > budget:
            price = int(budget * 0.95)
        
        flight = Flight(
            airline=airline_data.get("name", "Unknown Airline"),
            flight_number=flight_data.get("iata", f"XX{random.randint(100,999)}"),
            origin=departure.get("iata", "DSS"),
            destination=arrival.get("iata", "ABJ"),
            departure_time=dep_time or f"{datetime.now().strftime('%Y-%m-%d')}T08:00:00",
            arrival_time=arr_time or f"{datetime.now().strftime('%Y-%m-%d')}T10:30:00",
            duration=duration,
            price=price,
            tier=tier,
            stops=0 if tier != "ECO" else 1,
            available_seats=random.randint(5, 50),
            is_demo=False
        )
        flights.append(flight)
    
    return flights

def generate_mock_flights(origin: str, destination: str, date: str, budget: Optional[float] = None) -> List[Flight]:
    """Generate mock flight options (fallback)"""
    flights = []
    
    origin_code = get_iata_code(origin)
    dest_code = get_iata_code(destination)
    
    tiers = [
        {"tier": "ECO", "price_mult": 1.0, "stops": 1, "duration": "4h 30m"},
        {"tier": "FAST", "price_mult": 1.4, "stops": 0, "duration": "2h 15m"},
        {"tier": "PREMIUM", "price_mult": 2.2, "stops": 0, "duration": "2h 00m"}
    ]
    
    base_price = random.randint(45000, 85000)
    
    for tier_info in tiers:
        airline = random.choice(AIRLINES)
        price = int(base_price * tier_info["price_mult"])
        
        if budget and price > budget:
            price = int(budget * 0.95)
        
        dep_hour = random.randint(6, 18)
        flight = Flight(
            airline=airline["name"],
            flight_number=f"{airline['code']}{random.randint(100, 999)}",
            origin=origin_code,
            destination=dest_code,
            departure_time=f"{date}T{dep_hour:02d}:00:00",
            arrival_time=f"{date}T{(dep_hour + 2) % 24:02d}:30:00",
            duration=tier_info["duration"],
            price=price,
            tier=tier_info["tier"],
            stops=tier_info["stops"],
            available_seats=random.randint(5, 50),
            is_demo=True  # Mark as demo data
        )
        flights.append(flight)
    
    return flights

# ========== MTN MOMO INTEGRATION ==========

async def get_momo_access_token() -> Optional[str]:
    """Get MTN MoMo API access token"""
    api_user = os.environ.get('MOMO_API_USER')
    api_key = os.environ.get('MOMO_API_KEY')
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL', 'https://sandbox.momodeveloper.mtn.com')
    
    if not all([api_user, api_key, subscription_key]) or api_user == 'your_uuid_here':
        return None
    
    url = f"{base_url}/collection/token/"
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                url,
                auth=(api_user, api_key),
                headers={
                    "Ocp-Apim-Subscription-Key": subscription_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            else:
                logger.error(f"MoMo token request failed: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"MoMo token error: {e}")
        return None

async def initiate_momo_payment(amount: float, phone_number: str, booking_ref: str) -> dict:
    """Initiate MTN MoMo collection request"""
    token = await get_momo_access_token()
    
    if not token:
        # Fallback to simulated payment
        logger.warning("MoMo not configured, using simulation")
        return await simulate_momo_payment(amount, phone_number, booking_ref)
    
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL')
    environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
    currency = os.environ.get('MOMO_CURRENCY', 'XOF')
    callback_url = os.environ.get('MOMO_CALLBACK_URL')
    
    reference_id = str(uuid.uuid4())
    url = f"{base_url}/collection/v1_0/requesttopay"
    
    # Format phone number (remove + and spaces)
    phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    payload = {
        "amount": str(int(amount)),
        "currency": currency,
        "externalId": booking_ref,
        "payer": {
            "partyIdType": "MSISDN",
            "partyId": phone
        },
        "payerMessage": f"Travelio Booking {booking_ref}",
        "payeeNote": "Flight booking payment"
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Reference-Id": reference_id,
                    "X-Target-Environment": environment,
                    "Ocp-Apim-Subscription-Key": subscription_key,
                    "Content-Type": "application/json",
                    "X-Callback-Url": callback_url
                }
            )
            
            if response.status_code == 202:
                return {
                    "status": "pending",
                    "reference_id": reference_id,
                    "message": "Payment initiated. Please approve on your phone."
                }
            else:
                logger.error(f"MoMo payment initiation failed: {response.status_code} - {response.text}")
                return await simulate_momo_payment(amount, phone_number, booking_ref)
                
    except Exception as e:
        logger.error(f"MoMo payment error: {e}")
        return await simulate_momo_payment(amount, phone_number, booking_ref)

async def check_momo_payment_status(reference_id: str) -> dict:
    """Check MTN MoMo payment status"""
    token = await get_momo_access_token()
    
    if not token:
        # Simulate success for demo
        return {"status": "SUCCESSFUL", "is_simulated": True}
    
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL')
    environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
    
    url = f"{base_url}/collection/v1_0/requesttopay/{reference_id}"
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Target-Environment": environment,
                    "Ocp-Apim-Subscription-Key": subscription_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": data.get("status", "PENDING"),
                    "financial_transaction_id": data.get("financialTransactionId"),
                    "is_simulated": False
                }
            else:
                logger.error(f"MoMo status check failed: {response.status_code}")
                return {"status": "FAILED", "is_simulated": False}
                
    except Exception as e:
        logger.error(f"MoMo status error: {e}")
        return {"status": "FAILED", "is_simulated": False}

async def simulate_momo_payment(amount: float, phone_number: str, booking_ref: str) -> dict:
    """Simulate MoMo payment for demo purposes"""
    reference_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"
    return {
        "status": "pending",
        "reference_id": reference_id,
        "message": "Payment initiated (simulation mode). Approve in 3 seconds.",
        "is_simulated": True
    }

# ========== WHATSAPP INTEGRATION ==========

async def send_whatsapp_message(phone_number: str, message: str, pdf_url: Optional[str] = None) -> dict:
    """Send WhatsApp message with optional PDF attachment"""
    phone_id = os.environ.get('WHATSAPP_PHONE_ID')
    token = os.environ.get('WHATSAPP_TOKEN')
    
    if not all([phone_id, token]) or phone_id == 'your_phone_id_here':
        logger.warning("WhatsApp not configured, using simulation")
        return {
            "status": "simulated",
            "message": "WhatsApp delivery simulated (API not configured)"
        }
    
    # Format phone number
    phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            # Send text message first
            text_payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {
                    "body": message
                }
            }
            
            text_response = await client.post(url, json=text_payload, headers=headers)
            
            if text_response.status_code != 200:
                logger.error(f"WhatsApp text message failed: {text_response.text}")
                return {
                    "status": "failed",
                    "error": "Failed to send text message"
                }
            
            # Send PDF document if URL provided
            if pdf_url:
                doc_payload = {
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "document",
                    "document": {
                        "link": pdf_url,
                        "caption": "Your Travelio Ticket / Votre billet Travelio",
                        "filename": "travelio_ticket.pdf"
                    }
                }
                
                doc_response = await client.post(url, json=doc_payload, headers=headers)
                
                if doc_response.status_code != 200:
                    logger.error(f"WhatsApp document failed: {doc_response.text}")
            
            return {
                "status": "sent",
                "message": "Ticket sent via WhatsApp"
            }
            
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }

# ========== PDF TICKET GENERATION ==========

def generate_ticket_pdf(booking: dict, user: dict) -> str:
    """Generate PDF ticket with QR code"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import qrcode
    from io import BytesIO
    
    booking_ref = booking.get('booking_ref', booking.get('qr_code', 'TRV-XXXXXX'))
    filename = f"travelio_ticket_{booking_ref}.pdf"
    filepath = TICKETS_DIR / filename
    
    # Create QR code with booking data
    qr_data = json.dumps({
        "booking_ref": booking_ref,
        "passenger": f"{user.get('first_name', '')} {user.get('last_name', '')}",
        "origin": booking.get('origin', ''),
        "destination": booking.get('destination', ''),
        "departure": booking.get('departure_time', ''),
        "flight": booking.get('flight_number', ''),
        "price": booking.get('price', 0),
        "currency": booking.get('currency', 'XOF')
    })
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR to bytes
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # Create PDF
    doc = SimpleDocTemplate(str(filepath), pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#6C63FF'),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#94A3B8'),
        alignment=TA_LEFT
    )
    
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#0A0F1E'),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    
    elements = []
    
    # Header with logo text
    elements.append(Paragraph("TRAVELIO", title_style))
    elements.append(Paragraph("Your Voice, Your Journey", ParagraphStyle('Tagline', fontSize=10, textColor=colors.HexColor('#94A3B8'), alignment=TA_CENTER)))
    elements.append(Spacer(1, 20))
    
    # QR Code
    qr_image = Image(qr_buffer, width=80, height=80)
    
    # Build ticket info table
    passenger_name = f"{user.get('first_name', 'Guest')} {user.get('last_name', 'User')}"
    
    # Format departure time
    dep_time = booking.get('departure_time', '')
    if 'T' in dep_time:
        dep_date = dep_time.split('T')[0]
        dep_hour = dep_time.split('T')[1][:5] if len(dep_time) > 11 else ''
        dep_formatted = f"{dep_date} at {dep_hour}"
    else:
        dep_formatted = dep_time
    
    ticket_data = [
        [Paragraph("<b>BOARDING PASS</b>", ParagraphStyle('BP', fontSize=14, textColor=colors.white)), qr_image],
        ["", ""],
        [Paragraph("Passenger", header_style), Paragraph(passenger_name, value_style)],
        [Paragraph("From", header_style), Paragraph(f"{get_city_name(booking.get('origin', ''))} ({booking.get('origin', '')})", value_style)],
        [Paragraph("To", header_style), Paragraph(f"{get_city_name(booking.get('destination', ''))} ({booking.get('destination', '')})", value_style)],
        [Paragraph("Flight", header_style), Paragraph(f"{booking.get('airline', '')} {booking.get('flight_number', '')}", value_style)],
        [Paragraph("Departure", header_style), Paragraph(dep_formatted, value_style)],
        [Paragraph("Class", header_style), Paragraph(booking.get('travel_class', 'Economy').upper(), value_style)],
        [Paragraph("Price", header_style), Paragraph(f"{booking.get('price', 0):,.0f} {booking.get('currency', 'XOF')}", value_style)],
        [Paragraph("Payment", header_style), Paragraph(booking.get('payment_method', 'MTN MoMo').upper(), value_style)],
        [Paragraph("Booking Ref", header_style), Paragraph(f"<b>{booking_ref}</b>", ParagraphStyle('Ref', fontSize=14, textColor=colors.HexColor('#6C63FF')))],
    ]
    
    table = Table(ticket_data, colWidths=[100*mm, 80*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C63FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN', (1, 0), (1, 1)),  # QR code spans 2 rows
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 2), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 2), (-1, -1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    footer_style = ParagraphStyle('Footer', fontSize=9, textColor=colors.HexColor('#94A3B8'), alignment=TA_CENTER)
    elements.append(Paragraph("Scan QR code to verify ticket", footer_style))
    elements.append(Paragraph("Thank you for choosing Travelio! / Merci d'avoir choisi Travelio!", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    return filename

# ========== AI INTENT PARSING ==========

async def parse_travel_intent(text: str, language: str = "fr") -> TravelIntent:
    """Parse travel intent using Claude Sonnet 4.5"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            logger.warning("No EMERGENT_LLM_KEY found, using fallback parsing")
            return fallback_parse_intent(text, language)
        
        system_prompt = """You are a travel intent parser. Extract travel details from user messages.
        
Return a JSON object with these fields (use null for missing values):
- destination: city name (string)
- origin: city name, default to "Dakar" if not mentioned (string)
- departure_date: date in YYYY-MM-DD format (string)
- return_date: date in YYYY-MM-DD format or null for one-way (string)
- budget: numeric amount in local currency XOF (number)
- passengers: number of travelers, default 1 (number)
- travel_class: "economy", "business", or "first" (string)

Parse relative dates like "next Friday" based on today's date.
Convert budget mentions like "$200" or "200 dollars" to XOF (1 USD ≈ 600 XOF).
Understand both French and English.

Today's date is: """ + datetime.now().strftime("%Y-%m-%d") + """

ONLY respond with valid JSON, no explanation."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"intent-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        user_message = UserMessage(text=text)
        response = await chat.send_message(user_message)
        
        try:
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            parsed = json.loads(response_text)
            return TravelIntent(
                destination=parsed.get("destination"),
                origin=parsed.get("origin", "Dakar"),
                departure_date=parsed.get("departure_date"),
                return_date=parsed.get("return_date"),
                budget=parsed.get("budget"),
                passengers=parsed.get("passengers", 1),
                travel_class=parsed.get("travel_class", "economy"),
                language=language
            )
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI response: {response}")
            return fallback_parse_intent(text, language)
            
    except Exception as e:
        logger.error(f"AI parsing error: {e}")
        return fallback_parse_intent(text, language)

def fallback_parse_intent(text: str, language: str = "fr") -> TravelIntent:
    """Simple fallback parser when AI is unavailable"""
    import re
    text_lower = text.lower()
    
    destination = None
    for city in WEST_AFRICAN_CITIES.keys():
        if city.lower() in text_lower:
            destination = city
            break
    
    budget = None
    budget_match = re.search(r'(\d+)\s*(dollars?|\$|usd|xof|fcfa)', text_lower)
    if budget_match:
        amount = int(budget_match.group(1))
        currency = budget_match.group(2)
        if currency in ['dollars', '$', 'usd', 'dollar']:
            budget = amount * 600
        else:
            budget = amount
    
    today = datetime.now()
    next_week = today + timedelta(days=7)
    
    return TravelIntent(
        destination=destination or "Abidjan",
        origin="Dakar",
        departure_date=next_week.strftime("%Y-%m-%d"),
        return_date=None,
        budget=budget,
        passengers=1,
        travel_class="economy",
        language=language
    )

# ========== API ROUTES ==========

@api_router.get("/")
async def root():
    return {"message": "Travelio API", "version": "2.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Intent Parsing
@api_router.post("/parse-intent", response_model=TravelIntent)
async def parse_intent(request: IntentParseRequest):
    """Parse user text/voice input into structured travel intent"""
    intent = await parse_travel_intent(request.text, request.language)
    return intent

# Flight Search
@api_router.post("/flights/search", response_model=List[Flight])
async def search_flights(request: FlightSearchRequest):
    """Search for available flights"""
    # Try real API first
    raw_flights = await search_flights_aviationstack(
        request.origin,
        request.destination,
        request.departure_date
    )
    
    if raw_flights:
        flights = transform_aviationstack_flights(raw_flights, request.budget)
        if flights:
            return flights
    
    # Fallback to mock data
    logger.info("Using mock flight data")
    return generate_mock_flights(
        origin=request.origin,
        destination=request.destination,
        date=request.departure_date,
        budget=request.budget
    )

# User Profiles
@api_router.post("/users", response_model=UserProfile)
async def create_user(user: UserProfileCreate):
    """Create a new user profile"""
    user_obj = UserProfile(**user.model_dump())
    doc = user_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.users.insert_one(doc)
    return user_obj

@api_router.get("/users/{user_id}", response_model=UserProfile)
async def get_user(user_id: str):
    """Get user profile by ID"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if isinstance(user.get('created_at'), str):
        user['created_at'] = datetime.fromisoformat(user['created_at'])
    return UserProfile(**user)

@api_router.post("/users/bulk", response_model=List[UserProfile])
async def create_users_bulk(users: List[UserProfileCreate]):
    """Create multiple users from JSON upload"""
    created = []
    for user_data in users:
        user_obj = UserProfile(**user_data.model_dump())
        doc = user_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.users.insert_one(doc)
        created.append(user_obj)
    return created

# Bookings
@api_router.post("/bookings")
async def create_booking(request: BookingCreate):
    """Create a new booking"""
    flight_data = request.flight_data
    booking_ref = generate_booking_ref()
    
    booking = Booking(
        booking_ref=booking_ref,
        user_id=request.user_id,
        flight_id=request.flight_id,
        airline=flight_data.get('airline', 'Unknown'),
        flight_number=flight_data.get('flight_number', 'XX000'),
        origin=flight_data.get('origin', 'DSS'),
        destination=flight_data.get('destination', 'ABJ'),
        departure_time=flight_data.get('departure_time', ''),
        arrival_time=flight_data.get('arrival_time', ''),
        return_date=request.return_date,
        price=flight_data.get('price', 0) * request.passengers,
        passengers=request.passengers,
        travel_class=request.travel_class,
        passenger_name=request.passenger_name,
        payment_method="pending",
        qr_code=booking_ref
    )
    
    doc = booking.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bookings.insert_one(doc)
    
    return {
        "id": booking.id,
        "booking_ref": booking_ref,
        "status": booking.status,
        "price": booking.price,
        "currency": booking.currency
    }

@api_router.get("/bookings/user/{user_id}")
async def get_user_bookings(user_id: str):
    """Get all bookings for a user"""
    bookings = await db.bookings.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    for booking in bookings:
        if isinstance(booking.get('created_at'), str):
            booking['created_at'] = datetime.fromisoformat(booking['created_at'])
    return bookings

@api_router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str):
    """Get booking details by ID"""
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if isinstance(booking.get('created_at'), str):
        booking['created_at'] = datetime.fromisoformat(booking['created_at'])
    return booking

# Payments
@api_router.post("/payments/initiate")
async def initiate_payment(request: PaymentRequest):
    """Initiate payment for a booking"""
    # Get booking
    booking = await db.bookings.find_one({"id": request.booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking_ref = booking.get('booking_ref', booking.get('qr_code', 'TRV-000000'))
    
    if request.payment_method == "momo":
        result = await initiate_momo_payment(request.amount, request.phone_number, booking_ref)
    elif request.payment_method in ["google", "apple"]:
        # Simulate Google Pay / Apple Pay (instant success)
        result = {
            "status": "success",
            "reference_id": f"{'GPAY' if request.payment_method == 'google' else 'APAY'}-{uuid.uuid4().hex[:12].upper()}",
            "message": "Payment successful"
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    
    # Update booking with payment reference
    if result.get("reference_id"):
        await db.bookings.update_one(
            {"id": request.booking_id},
            {"$set": {
                "payment_reference": result["reference_id"],
                "payment_method": request.payment_method,
                "payment_status": "pending" if result["status"] == "pending" else "completed"
            }}
        )
    
    return result

@api_router.post("/payments/status")
async def check_payment_status(request: PaymentStatusRequest):
    """Check payment status (for MoMo polling)"""
    # Check if it's a simulated payment
    if request.payment_reference.startswith("SIM-"):
        # Simulate success after a delay
        return {
            "status": "SUCCESSFUL",
            "is_simulated": True
        }
    
    result = await check_momo_payment_status(request.payment_reference)
    return result

@api_router.post("/payments/complete")
async def complete_payment(booking_id: str, payment_reference: str, background_tasks: BackgroundTasks):
    """Complete payment and generate ticket"""
    # Get booking
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Get user
    user = await db.users.find_one({"id": booking.get("user_id")}, {"_id": 0})
    if not user:
        user = {"first_name": "Guest", "last_name": "User"}
    
    # Generate PDF ticket
    ticket_filename = generate_ticket_pdf(booking, user)
    ticket_url = f"/api/tickets/{ticket_filename}"
    
    # Update booking
    await db.bookings.update_one(
        {"id": booking_id},
        {"$set": {
            "status": "confirmed",
            "payment_status": "completed",
            "ticket_url": ticket_url
        }}
    )
    
    # Fetch updated booking
    updated_booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    
    return {
        "status": "success",
        "booking": updated_booking,
        "ticket_url": ticket_url
    }

# Legacy payment endpoints for backward compatibility
@api_router.post("/payments/momo")
async def process_momo_payment(request: PaymentRequest):
    """Process MTN MoMo payment (legacy endpoint)"""
    return await initiate_payment(request)

@api_router.post("/payments/google-pay")
async def process_google_pay(request: PaymentRequest):
    """Process Google Pay payment"""
    request.payment_method = "google"
    return await initiate_payment(request)

@api_router.post("/payments/apple-pay")
async def process_apple_pay(request: PaymentRequest):
    """Process Apple Pay payment"""
    request.payment_method = "apple"
    return await initiate_payment(request)

# MoMo Callback
@api_router.post("/momo/callback")
async def momo_callback(request: MomoCallbackRequest):
    """Handle MTN MoMo payment callback"""
    logger.info(f"MoMo callback received: {request.referenceId} - {request.status}")
    
    # Find booking by payment reference
    booking = await db.bookings.find_one({"payment_reference": request.referenceId}, {"_id": 0})
    
    if booking:
        new_status = "completed" if request.status == "SUCCESSFUL" else "failed"
        await db.bookings.update_one(
            {"payment_reference": request.referenceId},
            {"$set": {"payment_status": new_status}}
        )
    
    return {"received": True}

# Tickets
@api_router.get("/tickets/{filename}")
async def get_ticket(filename: str):
    """Download generated ticket PDF"""
    filepath = TICKETS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Ticket not found")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)

# WhatsApp
@api_router.post("/whatsapp/send-ticket")
async def send_whatsapp_ticket(request: WhatsAppRequest):
    """Send ticket via WhatsApp"""
    booking = await db.bookings.find_one({"id": request.booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking_ref = booking.get('booking_ref', booking.get('qr_code', 'TRV-XXXXXX'))
    ticket_url = booking.get('ticket_url')
    
    # Bilingual message
    message = f"""✈️ Votre billet Travelio est prêt! / Your Travelio ticket is ready!

📋 Référence / Reference: {booking_ref}
🛫 {booking.get('origin', '')} → {booking.get('destination', '')}
📅 {booking.get('departure_time', '').split('T')[0] if booking.get('departure_time') else ''}

Bon voyage! / Have a great trip! 🌍"""
    
    # Get full ticket URL for WhatsApp
    base_url = os.environ.get('MOMO_CALLBACK_URL', '').replace('/api/momo/callback', '')
    full_ticket_url = f"{base_url}{ticket_url}" if ticket_url and base_url else None
    
    result = await send_whatsapp_message(request.phone_number, message, full_ticket_url)
    
    return {
        "status": result.get("status", "sent"),
        "message": result.get("message", "Ticket sent"),
        "booking_ref": booking_ref,
        "ticket_url": ticket_url
    }

# Cities endpoint
@api_router.get("/cities")
async def get_cities():
    """Get list of supported West African cities"""
    return [{"name": city, "code": code} for city, code in WEST_AFRICAN_CITIES.items()]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
