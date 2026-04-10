from fastapi import FastAPI, APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import random
import asyncio
import httpx
import json
import string
import hashlib
import hmac

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'travelio')]

# Create the main app
app = FastAPI(title="Travelio WhatsApp Agent", version="3.0.0")

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

# ========== CONFIGURATION ==========

WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'travelio_verify_2024')
WHATSAPP_APP_SECRET = os.environ.get('WHATSAPP_APP_SECRET', '')

# West African cities
WEST_AFRICAN_CITIES = {
    "dakar": {"name": "Dakar", "code": "DSS", "country": "Senegal"},
    "lagos": {"name": "Lagos", "code": "LOS", "country": "Nigeria"},
    "accra": {"name": "Accra", "code": "ACC", "country": "Ghana"},
    "abidjan": {"name": "Abidjan", "code": "ABJ", "country": "Côte d'Ivoire"},
    "ouagadougou": {"name": "Ouagadougou", "code": "OUA", "country": "Burkina Faso"},
    "bamako": {"name": "Bamako", "code": "BKO", "country": "Mali"},
    "conakry": {"name": "Conakry", "code": "CKY", "country": "Guinea"},
    "niamey": {"name": "Niamey", "code": "NIM", "country": "Niger"},
    "cotonou": {"name": "Cotonou", "code": "COO", "country": "Benin"},
    "lome": {"name": "Lomé", "code": "LFW", "country": "Togo"}
}

AIRLINES = [
    {"name": "Air Senegal", "code": "HC"},
    {"name": "ASKY Airlines", "code": "KP"},
    {"name": "Royal Air Maroc", "code": "AT"},
    {"name": "Ethiopian Airlines", "code": "ET"},
    {"name": "Air Côte d'Ivoire", "code": "HF"}
]

# ========== MODELS ==========

class ConversationState:
    """Track conversation state for each user"""
    IDLE = "idle"
    AWAITING_FLIGHT_SELECTION = "awaiting_flight_selection"
    AWAITING_PAYMENT_CONFIRMATION = "awaiting_payment_confirmation"
    AWAITING_MOMO_APPROVAL = "awaiting_momo_approval"

class UserSession(BaseModel):
    phone: str
    state: str = ConversationState.IDLE
    language: str = "fr"  # Default French
    intent: Optional[Dict[str, Any]] = None
    flights: Optional[List[Dict[str, Any]]] = None
    selected_flight: Optional[Dict[str, Any]] = None
    booking_id: Optional[str] = None
    payment_reference: Optional[str] = None
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ========== HELPER FUNCTIONS ==========

def generate_booking_ref() -> str:
    """Generate booking reference: TRV-XXXXXX"""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=6))
    return f"TRV-{suffix}"

def get_city_info(name: str) -> Optional[Dict]:
    """Get city info from name"""
    name_lower = name.lower().strip()
    for key, city in WEST_AFRICAN_CITIES.items():
        if key in name_lower or city["name"].lower() in name_lower:
            return city
    return None

def format_price(amount: float) -> str:
    """Format price with thousands separator"""
    return f"{int(amount):,}".replace(",", " ")

def detect_language(text: str) -> str:
    """Simple language detection based on common words"""
    french_words = ["je", "veux", "aller", "à", "pour", "le", "la", "un", "une", "merci", "bonjour", "oui", "non"]
    text_lower = text.lower()
    french_count = sum(1 for word in french_words if word in text_lower)
    return "fr" if french_count >= 2 else "en"

# ========== SESSION MANAGEMENT ==========

async def get_or_create_session(phone: str) -> UserSession:
    """Get or create user session"""
    session_data = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    
    if session_data:
        # Update last activity
        await db.sessions.update_one(
            {"phone": phone},
            {"$set": {"last_activity": datetime.now(timezone.utc).isoformat()}}
        )
        return UserSession(**session_data)
    
    # Create new session
    session = UserSession(phone=phone)
    await db.sessions.insert_one({
        **session.model_dump(),
        "last_activity": session.last_activity.isoformat()
    })
    return session

async def update_session(phone: str, updates: Dict):
    """Update user session"""
    updates["last_activity"] = datetime.now(timezone.utc).isoformat()
    await db.sessions.update_one({"phone": phone}, {"$set": updates})

async def clear_session(phone: str):
    """Reset session to idle state"""
    await db.sessions.update_one(
        {"phone": phone},
        {"$set": {
            "state": ConversationState.IDLE,
            "intent": None,
            "flights": None,
            "selected_flight": None,
            "booking_id": None,
            "payment_reference": None,
            "last_activity": datetime.now(timezone.utc).isoformat()
        }}
    )

# ========== WHATSAPP API ==========

async def send_whatsapp_message(to: str, message: str):
    """Send text message via WhatsApp"""
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN:
        logger.warning(f"WhatsApp not configured. Would send to {to}: {message[:100]}...")
        return {"status": "simulated", "message": message}
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Format phone number
    phone = to.replace("+", "").replace(" ", "").replace("-", "")
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"WhatsApp message sent to {phone}")
                return {"status": "sent"}
            else:
                logger.error(f"WhatsApp send failed: {response.status_code} - {response.text}")
                return {"status": "failed", "error": response.text}
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return {"status": "failed", "error": str(e)}

async def send_whatsapp_document(to: str, document_url: str, filename: str, caption: str = ""):
    """Send document via WhatsApp"""
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN:
        logger.warning(f"WhatsApp not configured. Would send document to {to}")
        return {"status": "simulated"}
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    phone = to.replace("+", "").replace(" ", "").replace("-", "")
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename,
            "caption": caption
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp document send error: {e}")
        return {"status": "failed", "error": str(e)}

async def send_whatsapp_interactive(to: str, body_text: str, buttons: List[Dict]):
    """Send interactive button message via WhatsApp"""
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN:
        logger.warning(f"WhatsApp not configured. Would send interactive to {to}")
        return {"status": "simulated"}
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    phone = to.replace("+", "").replace(" ", "").replace("-", "")
    
    # WhatsApp allows max 3 buttons
    button_list = [
        {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"][:20]}}
        for btn in buttons[:3]
    ]
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": button_list}
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp interactive send error: {e}")
        return {"status": "failed", "error": str(e)}

# ========== AI INTENT PARSING ==========

async def parse_travel_intent(text: str, language: str = "fr") -> Dict[str, Any]:
    """Parse travel intent using Claude Sonnet 4.5"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            logger.warning("No EMERGENT_LLM_KEY, using fallback parser")
            return fallback_parse_intent(text, language)
        
        system_prompt = f"""You are a travel booking assistant parsing user messages.
        
Extract travel details and return ONLY a JSON object:
{{
  "destination": "city name or null",
  "origin": "city name, default Dakar if not mentioned",
  "departure_date": "YYYY-MM-DD or null",
  "return_date": "YYYY-MM-DD or null for one-way",
  "budget": number in XOF or null,
  "passengers": number (default 1),
  "travel_class": "economy", "business", or "first"
}}

Supported cities: Dakar, Lagos, Accra, Abidjan, Ouagadougou, Bamako, Conakry, Niamey, Cotonou, Lomé

Parse relative dates (next Friday, tomorrow, etc.) from today: {datetime.now().strftime("%Y-%m-%d")}
Convert USD to XOF: 1 USD ≈ 600 XOF

ONLY output valid JSON, no explanation."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"intent-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=text))
        
        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"AI parsing error: {e}")
        return fallback_parse_intent(text, language)

def fallback_parse_intent(text: str, language: str) -> Dict[str, Any]:
    """Simple fallback parser"""
    import re
    text_lower = text.lower()
    
    # Find destination
    destination = None
    for key, city in WEST_AFRICAN_CITIES.items():
        if key in text_lower or city["name"].lower() in text_lower:
            destination = city["name"]
            break
    
    # Find budget
    budget = None
    budget_match = re.search(r'(\d+)\s*(dollars?|\$|usd|xof|fcfa|francs?)', text_lower)
    if budget_match:
        amount = int(budget_match.group(1))
        currency = budget_match.group(2)
        budget = amount * 600 if currency in ['dollars', '$', 'usd', 'dollar'] else amount
    
    # Default date
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    return {
        "destination": destination,
        "origin": "Dakar",
        "departure_date": next_week,
        "return_date": None,
        "budget": budget,
        "passengers": 1,
        "travel_class": "economy"
    }

# ========== FLIGHT SEARCH ==========

async def search_flights_aviationstack(origin: str, destination: str, date: str) -> List[Dict]:
    """Search real flights using AviationStack API"""
    api_key = os.environ.get('AVIATIONSTACK_API_KEY')
    
    if not api_key or api_key == 'your_key_here':
        return []
    
    origin_city = get_city_info(origin)
    dest_city = get_city_info(destination)
    
    if not origin_city or not dest_city:
        return []
    
    url = "http://api.aviationstack.com/v1/flights"
    params = {
        "access_key": api_key,
        "dep_iata": origin_city["code"],
        "arr_iata": dest_city["code"],
        "flight_date": date
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
    except Exception as e:
        logger.error(f"AviationStack error: {e}")
    
    return []

def generate_mock_flights(origin: str, destination: str, date: str, budget: Optional[float] = None) -> List[Dict]:
    """Generate mock flight options"""
    origin_city = get_city_info(origin) or {"name": origin, "code": "DSS"}
    dest_city = get_city_info(destination) or {"name": destination, "code": "ABJ"}
    
    tiers = [
        {"tier": "ECO", "label_fr": "Économique", "label_en": "Economy", "price_mult": 1.0, "stops": 1, "duration": "4h 30m"},
        {"tier": "FAST", "label_fr": "Direct", "label_en": "Direct", "price_mult": 1.4, "stops": 0, "duration": "2h 15m"},
        {"tier": "PREMIUM", "label_fr": "Premium", "label_en": "Premium", "price_mult": 2.2, "stops": 0, "duration": "2h 00m"}
    ]
    
    base_price = random.randint(45000, 85000)
    flights = []
    
    for i, tier_info in enumerate(tiers):
        airline = AIRLINES[i % len(AIRLINES)]
        price = int(base_price * tier_info["price_mult"])
        
        if budget and price > budget:
            price = int(budget * 0.95)
        
        dep_hour = 6 + (i * 4)
        flights.append({
            "id": str(uuid.uuid4()),
            "option_number": i + 1,
            "airline": airline["name"],
            "flight_number": f"{airline['code']}{random.randint(100, 999)}",
            "origin": origin_city["code"],
            "origin_city": origin_city["name"],
            "destination": dest_city["code"],
            "destination_city": dest_city["name"],
            "departure_time": f"{date}T{dep_hour:02d}:00:00",
            "arrival_time": f"{date}T{dep_hour + 2:02d}:30:00",
            "duration": tier_info["duration"],
            "price": price,
            "currency": "XOF",
            "tier": tier_info["tier"],
            "tier_label_fr": tier_info["label_fr"],
            "tier_label_en": tier_info["label_en"],
            "stops": tier_info["stops"],
            "is_demo": True
        })
    
    return flights

async def search_flights(origin: str, destination: str, date: str, budget: Optional[float] = None) -> List[Dict]:
    """Search flights with fallback to mock data"""
    # Try real API first
    real_flights = await search_flights_aviationstack(origin, destination, date)
    
    if real_flights:
        # Transform to our format
        flights = []
        for i, flight in enumerate(real_flights[:3]):
            dep = flight.get("departure", {})
            arr = flight.get("arrival", {})
            airline = flight.get("airline", {})
            
            flights.append({
                "id": str(uuid.uuid4()),
                "option_number": i + 1,
                "airline": airline.get("name", "Unknown"),
                "flight_number": flight.get("flight", {}).get("iata", "XX000"),
                "origin": dep.get("iata", "DSS"),
                "destination": arr.get("iata", "ABJ"),
                "departure_time": dep.get("scheduled", ""),
                "arrival_time": arr.get("scheduled", ""),
                "duration": "2h 30m",
                "price": random.randint(50000, 120000),
                "currency": "XOF",
                "tier": ["ECO", "FAST", "PREMIUM"][i],
                "stops": 0,
                "is_demo": False
            })
        return flights
    
    # Fallback to mock
    return generate_mock_flights(origin, destination, date, budget)

# ========== MTN MOMO INTEGRATION ==========

async def get_momo_access_token() -> Optional[str]:
    """Get MTN MoMo API access token"""
    api_user = os.environ.get('MOMO_API_USER')
    api_key = os.environ.get('MOMO_API_KEY')
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL', 'https://sandbox.momodeveloper.mtn.com')
    
    if not all([api_user, api_key, subscription_key]) or api_user == 'your_uuid_here':
        return None
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/collection/token/",
                auth=(api_user, api_key),
                headers={"Ocp-Apim-Subscription-Key": subscription_key}
            )
            if response.status_code == 200:
                return response.json().get("access_token")
    except Exception as e:
        logger.error(f"MoMo token error: {e}")
    
    return None

async def initiate_momo_payment(phone: str, amount: float, booking_ref: str) -> Dict:
    """Initiate MTN MoMo collection"""
    token = await get_momo_access_token()
    
    if not token:
        # Simulate payment
        return {
            "status": "pending",
            "reference_id": f"SIM-{uuid.uuid4().hex[:12].upper()}",
            "is_simulated": True
        }
    
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL')
    environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
    currency = os.environ.get('MOMO_CURRENCY', 'XOF')
    
    reference_id = str(uuid.uuid4())
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    
    payload = {
        "amount": str(int(amount)),
        "currency": currency,
        "externalId": booking_ref,
        "payer": {"partyIdType": "MSISDN", "partyId": phone_clean},
        "payerMessage": f"Travelio {booking_ref}",
        "payeeNote": "Flight booking"
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/collection/v1_0/requesttopay",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Reference-Id": reference_id,
                    "X-Target-Environment": environment,
                    "Ocp-Apim-Subscription-Key": subscription_key,
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 202:
                return {"status": "pending", "reference_id": reference_id, "is_simulated": False}
    except Exception as e:
        logger.error(f"MoMo payment error: {e}")
    
    # Fallback to simulation
    return {
        "status": "pending",
        "reference_id": f"SIM-{uuid.uuid4().hex[:12].upper()}",
        "is_simulated": True
    }

async def check_momo_status(reference_id: str) -> str:
    """Check MoMo payment status"""
    if reference_id.startswith("SIM-"):
        return "SUCCESSFUL"  # Simulated always succeeds
    
    token = await get_momo_access_token()
    if not token:
        return "SUCCESSFUL"
    
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL')
    environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                f"{base_url}/collection/v1_0/requesttopay/{reference_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Target-Environment": environment,
                    "Ocp-Apim-Subscription-Key": subscription_key
                }
            )
            if response.status_code == 200:
                return response.json().get("status", "PENDING")
    except Exception as e:
        logger.error(f"MoMo status error: {e}")
    
    return "PENDING"

# ========== PDF TICKET GENERATION ==========

def generate_ticket_pdf(booking: Dict) -> str:
    """Generate PDF ticket with QR code"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import qrcode
    from io import BytesIO
    
    booking_ref = booking.get('booking_ref', 'TRV-XXXXXX')
    filename = f"travelio_ticket_{booking_ref}.pdf"
    filepath = TICKETS_DIR / filename
    
    # Create QR code
    qr_data = json.dumps({
        "ref": booking_ref,
        "passenger": booking.get('passenger_name', ''),
        "route": f"{booking.get('origin', '')} → {booking.get('destination', '')}",
        "date": booking.get('departure_date', ''),
        "flight": booking.get('flight_number', '')
    })
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # Create PDF
    doc = SimpleDocTemplate(str(filepath), pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, 
                                  textColor=colors.HexColor('#6C63FF'), alignment=TA_CENTER)
    header_style = ParagraphStyle('Header', fontSize=10, textColor=colors.gray)
    value_style = ParagraphStyle('Value', fontSize=12, fontName='Helvetica-Bold')
    
    elements = []
    elements.append(Paragraph("✈️ TRAVELIO", title_style))
    elements.append(Paragraph("Votre billet électronique / Your e-ticket", 
                              ParagraphStyle('Sub', fontSize=10, textColor=colors.gray, alignment=TA_CENTER)))
    elements.append(Spacer(1, 20))
    
    qr_image = Image(qr_buffer, width=80, height=80)
    
    ticket_data = [
        [Paragraph("<b>BOARDING PASS</b>", ParagraphStyle('BP', fontSize=14, textColor=colors.white)), qr_image],
        ["", ""],
        [Paragraph("Passenger / Passager", header_style), Paragraph(booking.get('passenger_name', 'Guest'), value_style)],
        [Paragraph("From / De", header_style), Paragraph(f"{booking.get('origin_city', '')} ({booking.get('origin', '')})", value_style)],
        [Paragraph("To / À", header_style), Paragraph(f"{booking.get('destination_city', '')} ({booking.get('destination', '')})", value_style)],
        [Paragraph("Flight / Vol", header_style), Paragraph(f"{booking.get('airline', '')} {booking.get('flight_number', '')}", value_style)],
        [Paragraph("Date", header_style), Paragraph(booking.get('departure_date', ''), value_style)],
        [Paragraph("Class / Classe", header_style), Paragraph(booking.get('tier', 'ECO'), value_style)],
        [Paragraph("Price / Prix", header_style), Paragraph(f"{format_price(booking.get('price', 0))} XOF", value_style)],
        [Paragraph("Payment / Paiement", header_style), Paragraph("MTN MoMo ✓", value_style)],
        [Paragraph("Reference", header_style), Paragraph(f"<b>{booking_ref}</b>", ParagraphStyle('Ref', fontSize=14, textColor=colors.HexColor('#6C63FF')))],
    ]
    
    table = Table(ticket_data, colWidths=[100*mm, 80*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C63FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('SPAN', (1, 0), (1, 1)),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 2), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 2), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Scannez le QR code pour vérifier / Scan QR to verify", 
                              ParagraphStyle('Footer', fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))
    elements.append(Paragraph("Merci d'avoir choisi Travelio! / Thank you for choosing Travelio! 🌍", 
                              ParagraphStyle('Footer2', fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))
    
    doc.build(elements)
    return filename

# ========== CONVERSATION HANDLERS ==========

def get_welcome_message(language: str) -> str:
    """Get welcome message"""
    if language == "fr":
        return """✈️ *Bienvenue sur Travelio!*

Je suis votre assistant de voyage. Dites-moi simplement où vous voulez aller!

Exemple: "Je veux aller à Dakar vendredi prochain pour 100 000 francs"

🌍 Destinations: Dakar, Lagos, Accra, Abidjan, Bamako, Ouagadougou, Conakry, Niamey, Cotonou, Lomé"""
    else:
        return """✈️ *Welcome to Travelio!*

I'm your travel assistant. Just tell me where you want to go!

Example: "I want to fly to Lagos next Friday under $200"

🌍 Destinations: Dakar, Lagos, Accra, Abidjan, Bamako, Ouagadougou, Conakry, Niamey, Cotonou, Lomé"""

def format_flight_options(flights: List[Dict], language: str) -> str:
    """Format flight options for WhatsApp"""
    if language == "fr":
        header = "✈️ *Voici vos options de vol:*\n\n"
        footer = "\n\n💬 Répondez avec le numéro (1, 2, ou 3) pour réserver"
    else:
        header = "✈️ *Here are your flight options:*\n\n"
        footer = "\n\n💬 Reply with the number (1, 2, or 3) to book"
    
    options = []
    for flight in flights:
        tier_label = flight.get(f'tier_label_{language}', flight.get('tier', ''))
        demo = " 🔸Demo" if flight.get('is_demo') else ""
        
        option = f"""*Option {flight['option_number']}* - {tier_label}{demo}
🛫 {flight['airline']} {flight['flight_number']}
📍 {flight.get('origin_city', flight['origin'])} → {flight.get('destination_city', flight['destination'])}
⏰ {flight['duration']} {'(1 escale)' if flight.get('stops', 0) > 0 else '(direct)'}
💰 *{format_price(flight['price'])} XOF*"""
        options.append(option)
    
    return header + "\n\n".join(options) + footer

def format_payment_request(flight: Dict, language: str) -> str:
    """Format payment confirmation request"""
    if language == "fr":
        return f"""✅ *Vol sélectionné:*

🛫 {flight['airline']} {flight['flight_number']}
📍 {flight.get('origin_city', flight['origin'])} → {flight.get('destination_city', flight['destination'])}
📅 {flight.get('departure_time', '').split('T')[0]}
💰 *{format_price(flight['price'])} XOF*

📱 *Paiement MTN MoMo*
Répondez *OUI* pour payer maintenant
Répondez *NON* pour annuler"""
    else:
        return f"""✅ *Selected flight:*

🛫 {flight['airline']} {flight['flight_number']}
📍 {flight.get('origin_city', flight['origin'])} → {flight.get('destination_city', flight['destination'])}
📅 {flight.get('departure_time', '').split('T')[0]}
💰 *{format_price(flight['price'])} XOF*

📱 *MTN MoMo Payment*
Reply *YES* to pay now
Reply *NO* to cancel"""

def format_payment_initiated(booking_ref: str, language: str, is_simulated: bool) -> str:
    """Format payment initiated message"""
    sim_note = "\n\n🔸 _Mode simulation - Paiement auto-approuvé_" if is_simulated else ""
    sim_note_en = "\n\n🔸 _Simulation mode - Payment auto-approved_" if is_simulated else ""
    
    if language == "fr":
        return f"""💳 *Paiement en cours...*

📲 Une demande de paiement a été envoyée sur votre téléphone MTN.

1️⃣ Ouvrez l'application MTN MoMo
2️⃣ Approuvez le paiement
3️⃣ Entrez votre code PIN

Référence: {booking_ref}

⏳ En attente de confirmation...{sim_note}"""
    else:
        return f"""💳 *Processing payment...*

📲 A payment request has been sent to your MTN phone.

1️⃣ Open MTN MoMo app
2️⃣ Approve the payment
3️⃣ Enter your PIN

Reference: {booking_ref}

⏳ Waiting for confirmation...{sim_note_en}"""

def format_booking_confirmed(booking: Dict, language: str) -> str:
    """Format booking confirmation message"""
    if language == "fr":
        return f"""🎉 *Réservation Confirmée!*

✅ Votre billet est prêt!

📋 *Détails:*
• Référence: *{booking['booking_ref']}*
• Vol: {booking['airline']} {booking['flight_number']}
• Route: {booking.get('origin_city', booking['origin'])} → {booking.get('destination_city', booking['destination'])}
• Date: {booking.get('departure_date', '')}
• Prix: {format_price(booking['price'])} XOF

📄 Votre billet PDF arrive dans quelques secondes...

Bon voyage! ✈️🌍"""
    else:
        return f"""🎉 *Booking Confirmed!*

✅ Your ticket is ready!

📋 *Details:*
• Reference: *{booking['booking_ref']}*
• Flight: {booking['airline']} {booking['flight_number']}
• Route: {booking.get('origin_city', booking['origin'])} → {booking.get('destination_city', booking['destination'])}
• Date: {booking.get('departure_date', '')}
• Price: {format_price(booking['price'])} XOF

📄 Your PDF ticket is coming in a few seconds...

Have a great trip! ✈️🌍"""

async def handle_message(phone: str, message_text: str, message_type: str = "text"):
    """Main message handler - the brain of the conversational agent"""
    session = await get_or_create_session(phone)
    text = message_text.strip().lower()
    original_text = message_text.strip()
    
    # Detect language from first message or use session language
    if session.state == ConversationState.IDLE:
        session.language = detect_language(original_text)
    
    lang = session.language
    
    # Handle commands
    if text in ["start", "bonjour", "hello", "hi", "salut", "aide", "help"]:
        await clear_session(phone)
        await send_whatsapp_message(phone, get_welcome_message(lang))
        return
    
    if text in ["annuler", "cancel", "reset", "stop"]:
        await clear_session(phone)
        msg = "❌ Réservation annulée. Envoyez un message pour recommencer." if lang == "fr" else "❌ Booking cancelled. Send a message to start again."
        await send_whatsapp_message(phone, msg)
        return
    
    # State machine
    if session.state == ConversationState.IDLE:
        # Parse travel intent
        intent = await parse_travel_intent(original_text, lang)
        
        if not intent.get("destination"):
            msg = "🤔 Je n'ai pas compris votre destination. Essayez: 'Je veux aller à Dakar vendredi'" if lang == "fr" else "🤔 I didn't understand your destination. Try: 'I want to fly to Lagos on Friday'"
            await send_whatsapp_message(phone, msg)
            return
        
        # Search flights
        flights = await search_flights(
            intent.get("origin", "Dakar"),
            intent["destination"],
            intent.get("departure_date", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
            intent.get("budget")
        )
        
        if not flights:
            msg = "😔 Aucun vol trouvé. Essayez une autre destination." if lang == "fr" else "😔 No flights found. Try another destination."
            await send_whatsapp_message(phone, msg)
            return
        
        # Update session
        await update_session(phone, {
            "state": ConversationState.AWAITING_FLIGHT_SELECTION,
            "language": lang,
            "intent": intent,
            "flights": flights
        })
        
        # Send flight options
        await send_whatsapp_message(phone, format_flight_options(flights, lang))
        
    elif session.state == ConversationState.AWAITING_FLIGHT_SELECTION:
        # User selecting a flight
        flights = session.flights or []
        
        # Try to parse selection
        selection = None
        if text in ["1", "one", "un", "premier", "first", "option 1"]:
            selection = 0
        elif text in ["2", "two", "deux", "deuxième", "second", "option 2"]:
            selection = 1
        elif text in ["3", "three", "trois", "troisième", "third", "option 3"]:
            selection = 2
        
        if selection is None or selection >= len(flights):
            msg = "❓ Répondez 1, 2 ou 3 pour choisir un vol" if lang == "fr" else "❓ Reply 1, 2, or 3 to select a flight"
            await send_whatsapp_message(phone, msg)
            return
        
        selected_flight = flights[selection]
        
        await update_session(phone, {
            "state": ConversationState.AWAITING_PAYMENT_CONFIRMATION,
            "selected_flight": selected_flight
        })
        
        await send_whatsapp_message(phone, format_payment_request(selected_flight, lang))
        
    elif session.state == ConversationState.AWAITING_PAYMENT_CONFIRMATION:
        # User confirming payment
        if text in ["oui", "yes", "ok", "payer", "pay", "confirmer", "confirm", "o", "y"]:
            selected_flight = session.selected_flight
            
            if not selected_flight:
                await clear_session(phone)
                msg = "❌ Session expirée. Recommencez." if lang == "fr" else "❌ Session expired. Start again."
                await send_whatsapp_message(phone, msg)
                return
            
            # Create booking
            booking_ref = generate_booking_ref()
            booking = {
                "id": str(uuid.uuid4()),
                "booking_ref": booking_ref,
                "phone": phone,
                "passenger_name": phone,  # In real app, ask for name
                "airline": selected_flight["airline"],
                "flight_number": selected_flight["flight_number"],
                "origin": selected_flight["origin"],
                "origin_city": selected_flight.get("origin_city", selected_flight["origin"]),
                "destination": selected_flight["destination"],
                "destination_city": selected_flight.get("destination_city", selected_flight["destination"]),
                "departure_date": selected_flight.get("departure_time", "").split("T")[0],
                "departure_time": selected_flight.get("departure_time", ""),
                "price": selected_flight["price"],
                "tier": selected_flight.get("tier", "ECO"),
                "status": "pending_payment",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.bookings.insert_one(booking)
            
            # Initiate MoMo payment
            payment_result = await initiate_momo_payment(phone, selected_flight["price"], booking_ref)
            
            await update_session(phone, {
                "state": ConversationState.AWAITING_MOMO_APPROVAL,
                "booking_id": booking["id"],
                "payment_reference": payment_result["reference_id"]
            })
            
            await send_whatsapp_message(phone, format_payment_initiated(booking_ref, lang, payment_result.get("is_simulated", False)))
            
            # Start payment status check (in background)
            asyncio.create_task(poll_payment_and_complete(phone, booking, payment_result["reference_id"], lang))
            
        elif text in ["non", "no", "annuler", "cancel", "n"]:
            await clear_session(phone)
            msg = "❌ Réservation annulée. Envoyez un message pour recommencer." if lang == "fr" else "❌ Booking cancelled. Send a message to start again."
            await send_whatsapp_message(phone, msg)
        else:
            msg = "❓ Répondez OUI pour payer ou NON pour annuler" if lang == "fr" else "❓ Reply YES to pay or NO to cancel"
            await send_whatsapp_message(phone, msg)
            
    elif session.state == ConversationState.AWAITING_MOMO_APPROVAL:
        # User waiting for MoMo - just acknowledge
        msg = "⏳ Paiement en cours... Veuillez approuver sur votre téléphone MTN" if lang == "fr" else "⏳ Payment in progress... Please approve on your MTN phone"
        await send_whatsapp_message(phone, msg)

async def poll_payment_and_complete(phone: str, booking: Dict, reference_id: str, language: str):
    """Poll payment status and complete booking"""
    max_attempts = 10
    
    for attempt in range(max_attempts):
        await asyncio.sleep(3)  # Wait 3 seconds between polls
        
        status = await check_momo_status(reference_id)
        
        if status == "SUCCESSFUL":
            # Update booking
            await db.bookings.update_one(
                {"id": booking["id"]},
                {"$set": {"status": "confirmed", "payment_status": "completed"}}
            )
            
            # Generate ticket
            ticket_filename = generate_ticket_pdf(booking)
            
            # Send confirmation
            await send_whatsapp_message(phone, format_booking_confirmed(booking, language))
            
            # Send PDF ticket
            base_url = os.environ.get('APP_BASE_URL', 'https://voice-travel-booking.preview.emergentagent.com')
            ticket_url = f"{base_url}/api/tickets/{ticket_filename}"
            
            await asyncio.sleep(2)
            await send_whatsapp_document(
                phone,
                ticket_url,
                ticket_filename,
                f"🎫 Travelio Ticket - {booking['booking_ref']}"
            )
            
            # Clear session
            await clear_session(phone)
            return
            
        elif status == "FAILED":
            await db.bookings.update_one(
                {"id": booking["id"]},
                {"$set": {"status": "payment_failed"}}
            )
            
            msg = "❌ Paiement échoué. Réessayez en envoyant un nouveau message." if language == "fr" else "❌ Payment failed. Try again by sending a new message."
            await send_whatsapp_message(phone, msg)
            await clear_session(phone)
            return
    
    # Timeout
    msg = "⏰ Délai dépassé. Le paiement n'a pas été confirmé. Réessayez." if language == "fr" else "⏰ Timeout. Payment was not confirmed. Please try again."
    await send_whatsapp_message(phone, msg)
    await clear_session(phone)

# ========== WEBHOOK ROUTES ==========

@api_router.get("/webhook")
async def verify_webhook(request: Request):
    """WhatsApp webhook verification"""
    params = dict(request.query_params)
    
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return JSONResponse(content=int(challenge), media_type="text/plain")
    
    raise HTTPException(status_code=403, detail="Verification failed")

@api_router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive WhatsApp messages"""
    try:
        body = await request.json()
        logger.info(f"Webhook received: {json.dumps(body)[:500]}")
        
        # Extract message
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        for message in messages:
            phone = message.get("from", "")
            msg_type = message.get("type", "text")
            
            # Extract text
            if msg_type == "text":
                text = message.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                # Button reply
                interactive = message.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    text = interactive.get("button_reply", {}).get("id", "")
                else:
                    text = interactive.get("list_reply", {}).get("id", "")
            elif msg_type == "audio":
                # Voice message - would need transcription
                # For now, send a message asking for text
                await send_whatsapp_message(phone, "🎤 Les messages vocaux seront bientôt supportés. Veuillez taper votre message. / Voice messages coming soon. Please type your message.")
                continue
            else:
                continue
            
            if phone and text:
                # Process in background to respond quickly
                background_tasks.add_task(handle_message, phone, text, msg_type)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

# ========== OTHER API ROUTES ==========

@api_router.get("/")
async def root():
    return {"message": "Travelio WhatsApp Agent", "version": "3.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "type": "whatsapp_agent"}

@api_router.get("/tickets/{filename}")
async def get_ticket(filename: str):
    """Serve ticket PDF"""
    filepath = TICKETS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Ticket not found")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)

@api_router.get("/bookings/{booking_ref}")
async def get_booking(booking_ref: str):
    """Get booking by reference"""
    booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

@api_router.get("/sessions/{phone}")
async def get_session(phone: str):
    """Get user session (for debugging)"""
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return session or {"status": "no session"}

# Test endpoint to simulate incoming message
@api_router.post("/test/message")
async def test_message(phone: str, message: str):
    """Test endpoint to simulate WhatsApp message"""
    await handle_message(phone, message, "text")
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return {"status": "processed", "session_state": session.get("state") if session else "none"}

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
