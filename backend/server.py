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
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'travelio')]

# Create the main app
app = FastAPI(title="Travelio WhatsApp Agent", version="4.0.0")
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directories
TICKETS_DIR = ROOT_DIR / 'tickets'
TICKETS_DIR.mkdir(exist_ok=True)

# Constants
API_TIMEOUT = 10.0
EUR_TO_XOF = 655.957  # Fixed rate

# ========== CONFIGURATION ==========

WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'travelio_verify_2024')

# Airport codes for West Africa and common destinations
AIRPORT_CODES = {
    "dakar": "DSS", "lagos": "LOS", "accra": "ACC", "abidjan": "ABJ",
    "ouagadougou": "OUA", "bamako": "BKO", "conakry": "CKY", "niamey": "NIM",
    "cotonou": "COO", "lome": "LFW", "paris": "CDG", "london": "LHR",
    "casablanca": "CMN", "addis ababa": "ADD", "nairobi": "NBO", "dubai": "DXB",
    "new york": "JFK", "douala": "DLA", "libreville": "LBV", "bruxelles": "BRU"
}

CODE_TO_CITY = {v: k.title() for k, v in AIRPORT_CODES.items()}

# ========== MODELS ==========

class ConversationState:
    IDLE = "idle"
    AWAITING_DESTINATION = "awaiting_destination"
    AWAITING_DATE = "awaiting_date"
    AWAITING_PASSENGERS = "awaiting_passengers"
    AWAITING_FLIGHT_SELECTION = "awaiting_flight_selection"
    AWAITING_PAYMENT_CONFIRMATION = "awaiting_payment_confirmation"
    AWAITING_MOMO_APPROVAL = "awaiting_momo_approval"

# ========== HELPER FUNCTIONS ==========

def generate_booking_ref() -> str:
    chars = string.ascii_uppercase + string.digits
    return f"TRV-{''.join(random.choices(chars, k=6))}"

def get_airport_code(city_name: str) -> Optional[str]:
    name_lower = city_name.lower().strip()
    for city, code in AIRPORT_CODES.items():
        if city in name_lower or name_lower in city:
            return code
    # Check if already a code
    if name_lower.upper() in CODE_TO_CITY:
        return name_lower.upper()
    return None

def get_city_name(code: str) -> str:
    return CODE_TO_CITY.get(code.upper(), code)

def detect_language(text: str) -> str:
    french_words = ["je", "veux", "aller", "pour", "le", "la", "un", "une", "merci", "bonjour", "oui", "non", "vol", "billet"]
    text_lower = text.lower()
    french_count = sum(1 for word in french_words if f" {word} " in f" {text_lower} " or text_lower.startswith(word) or text_lower.endswith(word))
    return "fr" if french_count >= 1 else "en"

def apply_travelio_margin(amadeus_price: float) -> float:
    """Apply Travelio pricing rule: final = amadeus_price + 15 + (amadeus_price * 0.05)"""
    final = amadeus_price + 15 + (amadeus_price * 0.05)
    return round(final, 2)

def eur_to_xof(eur: float) -> int:
    return int(round(eur * EUR_TO_XOF))

def format_duration(iso_duration: str) -> str:
    """Convert ISO 8601 duration (PT2H30M) to readable format"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        if hours and minutes:
            return f"{hours}h{minutes:02d}"
        elif hours:
            return f"{hours}h00"
        else:
            return f"0h{minutes:02d}"
    return iso_duration

def parse_duration_minutes(iso_duration: str) -> int:
    """Convert ISO duration to total minutes for comparison"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return hours * 60 + minutes
    return 9999

# ========== SESSION MANAGEMENT ==========

async def get_or_create_session(phone: str) -> Dict:
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    if session:
        await db.sessions.update_one({"phone": phone}, {"$set": {"last_activity": datetime.now(timezone.utc).isoformat()}})
        return session
    
    new_session = {
        "phone": phone,
        "state": ConversationState.IDLE,
        "language": "fr",
        "intent": {},
        "flights": [],
        "selected_flight": None,
        "booking_id": None,
        "payment_reference": None,
        "last_activity": datetime.now(timezone.utc).isoformat()
    }
    await db.sessions.insert_one(new_session)
    return new_session

async def update_session(phone: str, updates: Dict):
    updates["last_activity"] = datetime.now(timezone.utc).isoformat()
    await db.sessions.update_one({"phone": phone}, {"$set": updates})

async def clear_session(phone: str):
    await db.sessions.update_one({"phone": phone}, {"$set": {
        "state": ConversationState.IDLE,
        "intent": {},
        "flights": [],
        "selected_flight": None,
        "booking_id": None,
        "payment_reference": None,
        "last_activity": datetime.now(timezone.utc).isoformat()
    }})

# ========== WHATSAPP API ==========

async def send_whatsapp_message(to: str, message: str) -> Dict:
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN or WHATSAPP_PHONE_ID == 'your_phone_id_here':
        logger.info(f"[WhatsApp SIM] To {to}:\n{message[:500]}...")
        return {"status": "simulated", "message": message}
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    phone = to.replace("+", "").replace(" ", "").replace("-", "")
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url, 
                json={"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": message}},
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return {"status": "failed", "error": str(e)}

async def send_whatsapp_document(to: str, document_url: str, filename: str, caption: str = "") -> Dict:
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN or WHATSAPP_PHONE_ID == 'your_phone_id_here':
        logger.info(f"[WhatsApp SIM] Document to {to}: {filename}")
        return {"status": "simulated"}
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    phone = to.replace("+", "").replace(" ", "").replace("-", "")
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(url,
                json={"messaging_product": "whatsapp", "to": phone, "type": "document",
                      "document": {"link": document_url, "filename": filename, "caption": caption}},
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
            return {"status": "sent" if response.status_code == 200 else "failed"}
    except Exception as e:
        logger.error(f"WhatsApp document error: {e}")
        return {"status": "failed"}

# ========== WHISPER TRANSCRIPTION ==========

async def transcribe_audio(audio_url: str, audio_id: str) -> Optional[str]:
    """Transcribe voice message using OpenAI Whisper"""
    openai_key = os.environ.get('OPENAI_API_KEY')
    if not openai_key or openai_key == 'your_whisper_key_here':
        logger.warning("Whisper API not configured")
        return None
    
    try:
        # First download audio from WhatsApp
        async with httpx.AsyncClient(timeout=30) as client:
            # Get media URL
            media_response = await client.get(
                f"https://graph.facebook.com/v18.0/{audio_id}",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
            
            if media_response.status_code != 200:
                return None
            
            media_url = media_response.json().get("url")
            
            # Download audio
            audio_response = await client.get(media_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
            audio_data = audio_response.content
            
            # Send to Whisper
            files = {"file": ("audio.ogg", audio_data, "audio/ogg")}
            whisper_response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {openai_key}"},
                files=files,
                data={"model": "whisper-1", "language": "fr"})
            
            if whisper_response.status_code == 200:
                return whisper_response.json().get("text")
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
    
    return None

# ========== AMADEUS API ==========

async def get_amadeus_token() -> Optional[str]:
    """Get Amadeus OAuth token"""
    api_key = os.environ.get('AMADEUS_API_KEY')
    api_secret = os.environ.get('AMADEUS_API_SECRET')
    base_url = os.environ.get('AMADEUS_BASE_URL', 'https://test.api.amadeus.com')
    
    if not api_key or not api_secret or api_key == 'your_key_here':
        return None
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/v1/security/oauth2/token",
                data={"grant_type": "client_credentials", "client_id": api_key, "client_secret": api_secret},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            
            if response.status_code == 200:
                return response.json().get("access_token")
    except Exception as e:
        logger.error(f"Amadeus token error: {e}")
    
    return None

async def search_amadeus_flights(origin: str, destination: str, departure_date: str, adults: int = 1) -> List[Dict]:
    """Search flights using Amadeus Flight Offers API"""
    token = await get_amadeus_token()
    base_url = os.environ.get('AMADEUS_BASE_URL', 'https://test.api.amadeus.com')
    
    if not token:
        logger.warning("Amadeus not configured, using mock data")
        return generate_mock_flights(origin, destination, departure_date, adults)
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                f"{base_url}/v2/shopping/flight-offers",
                params={
                    "originLocationCode": origin,
                    "destinationLocationCode": destination,
                    "departureDate": departure_date,
                    "adults": adults,
                    "currencyCode": "EUR",
                    "max": 20
                },
                headers={"Authorization": f"Bearer {token}"})
            
            if response.status_code == 200:
                data = response.json()
                return parse_amadeus_response(data.get("data", []))
            else:
                logger.error(f"Amadeus API error: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        logger.error(f"Amadeus search error: {e}")
    
    return generate_mock_flights(origin, destination, departure_date, adults)

def parse_amadeus_response(offers: List[Dict]) -> List[Dict]:
    """Parse Amadeus flight offers into our format"""
    flights = []
    
    for offer in offers:
        try:
            # Get price
            amadeus_price = float(offer.get("price", {}).get("total", 0))
            final_price = apply_travelio_margin(amadeus_price)
            
            # Parse itineraries
            itineraries = offer.get("itineraries", [])
            if not itineraries:
                continue
            
            outbound = itineraries[0]
            segments = outbound.get("segments", [])
            if not segments:
                continue
            
            # Calculate total duration and stops
            total_duration = outbound.get("duration", "PT0H0M")
            num_stops = len(segments) - 1
            
            # Get first and last segment for origin/destination
            first_seg = segments[0]
            last_seg = segments[-1]
            
            # Get airline
            carrier_code = first_seg.get("carrierCode", "XX")
            airline_names = {
                "AF": "Air France", "KL": "KLM", "LH": "Lufthansa", "BA": "British Airways",
                "ET": "Ethiopian Airlines", "AT": "Royal Air Maroc", "W3": "Arik Air",
                "HF": "Air Côte d'Ivoire", "KC": "Air Astana", "QR": "Qatar Airways",
                "EK": "Emirates", "TK": "Turkish Airlines", "SN": "Brussels Airlines"
            }
            airline = airline_names.get(carrier_code, carrier_code)
            
            flight = {
                "id": offer.get("id", str(uuid.uuid4())),
                "amadeus_price": amadeus_price,
                "final_price": final_price,
                "price_xof": eur_to_xof(final_price),
                "airline": airline,
                "carrier_code": carrier_code,
                "flight_number": f"{carrier_code}{first_seg.get('number', '000')}",
                "origin": first_seg.get("departure", {}).get("iataCode", ""),
                "destination": last_seg.get("arrival", {}).get("iataCode", ""),
                "departure_time": first_seg.get("departure", {}).get("at", ""),
                "arrival_time": last_seg.get("arrival", {}).get("at", ""),
                "duration": total_duration,
                "duration_formatted": format_duration(total_duration),
                "duration_minutes": parse_duration_minutes(total_duration),
                "stops": num_stops,
                "stops_text": "Direct" if num_stops == 0 else f"{num_stops} escale{'s' if num_stops > 1 else ''}",
                "is_demo": False
            }
            flights.append(flight)
        except Exception as e:
            logger.error(f"Error parsing flight offer: {e}")
            continue
    
    return flights

def generate_mock_flights(origin: str, destination: str, date: str, adults: int = 1) -> List[Dict]:
    """Generate mock flight data for testing"""
    airlines = [
        ("Air France", "AF"), ("Ethiopian Airlines", "ET"), 
        ("Royal Air Maroc", "AT"), ("Brussels Airlines", "SN")
    ]
    
    flights = []
    base_prices = [185, 220, 310, 275, 195]
    durations = [("PT5H30M", 1), ("PT3H15M", 0), ("PT4H00M", 0), ("PT6H45M", 2), ("PT4H30M", 1)]
    
    for i in range(min(5, len(base_prices))):
        airline_name, carrier = random.choice(airlines)
        amadeus_price = base_prices[i] + random.randint(-20, 30)
        final_price = apply_travelio_margin(amadeus_price)
        duration, stops = durations[i]
        
        flights.append({
            "id": str(uuid.uuid4()),
            "amadeus_price": amadeus_price,
            "final_price": final_price,
            "price_xof": eur_to_xof(final_price),
            "airline": airline_name,
            "carrier_code": carrier,
            "flight_number": f"{carrier}{random.randint(100, 999)}",
            "origin": origin,
            "destination": destination,
            "departure_time": f"{date}T{8 + i*2:02d}:00:00",
            "arrival_time": f"{date}T{14 + i*2:02d}:30:00",
            "duration": duration,
            "duration_formatted": format_duration(duration),
            "duration_minutes": parse_duration_minutes(duration),
            "stops": stops,
            "stops_text": "Direct" if stops == 0 else f"{stops} escale{'s' if stops > 1 else ''}",
            "is_demo": True
        })
    
    return flights

def categorize_flights(flights: List[Dict]) -> Dict[str, Dict]:
    """
    Autonomous flight categorization:
    - PLUS_BAS: Lowest final_price
    - PLUS_RAPIDE: Shortest duration
    - PREMIUM: Best score (price 40%, duration 40%, direct bonus 20%)
    """
    if not flights:
        return {}
    
    # Sort for each category
    by_price = sorted(flights, key=lambda f: f["final_price"])
    by_duration = sorted(flights, key=lambda f: f["duration_minutes"])
    
    # Calculate PREMIUM score
    max_price = max(f["final_price"] for f in flights)
    max_duration = max(f["duration_minutes"] for f in flights)
    
    def get_score(f):
        price_score = (max_price - f["final_price"]) / max_price if max_price > 0 else 0
        duration_score = (max_duration - f["duration_minutes"]) / max_duration if max_duration > 0 else 0
        
        stops = f.get("stops", 0)
        direct_bonus = 1.0 if stops == 0 else (0.5 if stops == 1 else 0)
        
        return (price_score * 0.4) + (duration_score * 0.4) + (direct_bonus * 0.2)
    
    by_score = sorted(flights, key=get_score, reverse=True)
    
    # Assign categories, avoiding duplicates
    result = {}
    used_ids = set()
    
    # PLUS_BAS first
    for f in by_price:
        if f["id"] not in used_ids:
            result["PLUS_BAS"] = {**f, "category": "PLUS_BAS", "label": "💚 LE PLUS BAS"}
            used_ids.add(f["id"])
            break
    
    # PLUS_RAPIDE second
    for f in by_duration:
        if f["id"] not in used_ids:
            result["PLUS_RAPIDE"] = {**f, "category": "PLUS_RAPIDE", "label": "⚡ LE PLUS RAPIDE"}
            used_ids.add(f["id"])
            break
    
    # PREMIUM third
    for f in by_score:
        if f["id"] not in used_ids:
            result["PREMIUM"] = {**f, "category": "PREMIUM", "label": "👑 PREMIUM"}
            used_ids.add(f["id"])
            break
    
    # Fill remaining if we don't have 3
    if len(result) < 3:
        for f in flights:
            if f["id"] not in used_ids:
                if "PLUS_BAS" not in result:
                    result["PLUS_BAS"] = {**f, "category": "PLUS_BAS", "label": "💚 LE PLUS BAS"}
                elif "PLUS_RAPIDE" not in result:
                    result["PLUS_RAPIDE"] = {**f, "category": "PLUS_RAPIDE", "label": "⚡ LE PLUS RAPIDE"}
                elif "PREMIUM" not in result:
                    result["PREMIUM"] = {**f, "category": "PREMIUM", "label": "👑 PREMIUM"}
                used_ids.add(f["id"])
                if len(result) >= 3:
                    break
    
    return result

# ========== AI INTENT PARSING ==========

async def parse_travel_intent(text: str, language: str = "fr") -> Dict[str, Any]:
    """Parse travel intent using Claude"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            return fallback_parse_intent(text, language)
        
        system_prompt = f"""Tu es un assistant de réservation de vols. Extrais les informations de voyage.

Retourne UNIQUEMENT un JSON valide:
{{
  "origin": "code IATA ou ville (défaut: DSS si non mentionné)",
  "destination": "code IATA ou ville ou null",
  "departure_date": "YYYY-MM-DD ou null",
  "return_date": "YYYY-MM-DD ou null",
  "passengers": nombre (défaut: 1),
  "budget_hint": nombre en EUR ou null
}}

Codes IATA courants: DSS (Dakar), COO (Cotonou), LOS (Lagos), ACC (Accra), ABJ (Abidjan), CDG (Paris), LHR (Londres)
Aujourd'hui: {datetime.now().strftime("%Y-%m-%d")}
Parse les dates relatives (vendredi prochain, demain, etc.)

UNIQUEMENT le JSON, pas d'explication."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"intent-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=text))
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"AI parsing error: {e}")
        return fallback_parse_intent(text, language)

def fallback_parse_intent(text: str, language: str) -> Dict:
    """Simple fallback parser"""
    import re
    text_lower = text.lower()
    
    # Find destination
    destination = None
    origin = "DSS"  # Default Dakar
    
    for city, code in AIRPORT_CODES.items():
        if city in text_lower:
            if destination is None:
                destination = code
            else:
                origin = code
    
    # Find date
    departure_date = None
    today = datetime.now()
    
    if "demain" in text_lower or "tomorrow" in text_lower:
        departure_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "vendredi" in text_lower or "friday" in text_lower:
        days_ahead = (4 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        departure_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    
    # Find passengers
    passengers = 1
    pax_match = re.search(r'(\d+)\s*(passager|personne|adulte|people|passenger|adult)', text_lower)
    if pax_match:
        passengers = int(pax_match.group(1))
    
    return {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": None,
        "passengers": passengers,
        "budget_hint": None
    }

# ========== MTN MOMO ==========

async def get_momo_token() -> Optional[str]:
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
                headers={"Ocp-Apim-Subscription-Key": subscription_key})
            if response.status_code == 200:
                return response.json().get("access_token")
    except Exception as e:
        logger.error(f"MoMo token error: {e}")
    return None

async def initiate_momo_payment(phone: str, amount: float, booking_ref: str) -> Dict:
    token = await get_momo_token()
    
    if not token:
        return {"status": "pending", "reference_id": f"SIM-{uuid.uuid4().hex[:12].upper()}", "is_simulated": True}
    
    subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
    base_url = os.environ.get('MOMO_BASE_URL')
    environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
    
    reference_id = str(uuid.uuid4())
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/collection/v1_0/requesttopay",
                json={
                    "amount": str(int(amount * EUR_TO_XOF)),  # Convert EUR to XOF for MoMo
                    "currency": "XOF",
                    "externalId": booking_ref,
                    "payer": {"partyIdType": "MSISDN", "partyId": phone_clean},
                    "payerMessage": f"Travelio {booking_ref}",
                    "payeeNote": "Vol réservé"
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Reference-Id": reference_id,
                    "X-Target-Environment": environment,
                    "Ocp-Apim-Subscription-Key": subscription_key,
                    "Content-Type": "application/json"
                })
            
            if response.status_code == 202:
                return {"status": "pending", "reference_id": reference_id, "is_simulated": False}
    except Exception as e:
        logger.error(f"MoMo payment error: {e}")
    
    return {"status": "pending", "reference_id": f"SIM-{uuid.uuid4().hex[:12].upper()}", "is_simulated": True}

async def check_momo_status(reference_id: str) -> str:
    if reference_id.startswith("SIM-"):
        return "SUCCESSFUL"
    
    token = await get_momo_token()
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
                })
            if response.status_code == 200:
                return response.json().get("status", "PENDING")
    except Exception as e:
        logger.error(f"MoMo status error: {e}")
    return "PENDING"

# ========== PDF TICKET ==========

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
    
    qr_data = json.dumps({
        "ref": booking_ref,
        "route": f"{booking.get('origin')} → {booking.get('destination')}",
        "date": booking.get('departure_date'),
        "price": f"{booking.get('price_eur')}€"
    })
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    doc = SimpleDocTemplate(str(filepath), pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#6C63FF'), alignment=TA_CENTER)
    
    elements = []
    elements.append(Paragraph("✈️ TRAVELIO", title_style))
    elements.append(Paragraph("Votre billet électronique", ParagraphStyle('Sub', fontSize=12, textColor=colors.gray, alignment=TA_CENTER)))
    elements.append(Spacer(1, 20))
    
    qr_image = Image(qr_buffer, width=80, height=80)
    
    ticket_data = [
        [Paragraph("<b>BOARDING PASS</b>", ParagraphStyle('BP', fontSize=14, textColor=colors.white)), qr_image],
        ["", ""],
        ["Passager", booking.get('passenger_name', 'Guest')],
        ["De", f"{get_city_name(booking.get('origin', ''))} ({booking.get('origin')})"],
        ["À", f"{get_city_name(booking.get('destination', ''))} ({booking.get('destination')})"],
        ["Vol", f"{booking.get('airline')} {booking.get('flight_number')}"],
        ["Date", booking.get('departure_date')],
        ["Catégorie", booking.get('category', 'Standard')],
        ["Prix", f"{booking.get('price_eur')}€ ({booking.get('price_xof'):,} XOF)"],
        ["Référence", f"*{booking_ref}*"],
    ]
    
    table = Table(ticket_data, colWidths=[80*mm, 80*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C63FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('SPAN', (1, 0), (1, 1)),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('FONTNAME', (0, 2), (0, -1), 'Helvetica'),
        ('FONTNAME', (1, 2), (1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 2), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 2), (-1, -1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Scannez le QR code pour vérifier • Bon voyage! 🌍", ParagraphStyle('Footer', fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))
    
    doc.build(elements)
    return filename

# ========== MESSAGE FORMATTING ==========

def format_flight_options_message(categorized: Dict, origin: str, destination: str, date: str) -> str:
    """Format flight options using exact template"""
    origin_city = get_city_name(origin)
    dest_city = get_city_name(destination)
    
    msg = f"""✈️ *Travelio — 3 options trouvées*
{origin_city} → {dest_city} | {date}

━━━━━━━━━━━━━━━━━━━━"""
    
    option_num = 1
    for cat in ["PLUS_BAS", "PLUS_RAPIDE", "PREMIUM"]:
        if cat in categorized:
            f = categorized[cat]
            demo = " 🔸Demo" if f.get("is_demo") else ""
            msg += f"""
{f['label']}{demo}
{f['airline']} | {f['stops_text']}
Durée : {f['duration_formatted']}
Prix : *{f['final_price']}€* ({f['price_xof']:,} XOF)
Taper *{option_num}* pour sélectionner
"""
            option_num += 1
    
    msg += """━━━━━━━━━━━━━━━━━━━━
Répondez 1, 2 ou 3 pour continuer."""
    
    return msg

def format_confirmation_request(flight: Dict, lang: str) -> str:
    if lang == "fr":
        return f"""✅ *Vol sélectionné : {flight['label']}*

🛫 {flight['airline']} {flight['flight_number']}
📍 {get_city_name(flight['origin'])} → {get_city_name(flight['destination'])}
⏱️ Durée : {flight['duration_formatted']} | {flight['stops_text']}
💰 Prix : *{flight['final_price']}€* ({flight['price_xof']:,} XOF)

Confirmer ce vol pour {flight['final_price']}€ ? (oui/non)"""
    else:
        return f"""✅ *Selected flight: {flight['label']}*

🛫 {flight['airline']} {flight['flight_number']}
📍 {get_city_name(flight['origin'])} → {get_city_name(flight['destination'])}
⏱️ Duration: {flight['duration_formatted']} | {flight['stops_text']}
💰 Price: *{flight['final_price']}€* ({flight['price_xof']:,} XOF)

Confirm this flight for {flight['final_price']}€? (yes/no)"""

def format_payment_initiated(booking_ref: str, amount: float, lang: str, is_sim: bool) -> str:
    sim_note = "\n\n🔸 _Mode simulation - paiement auto-approuvé_" if is_sim else ""
    if lang == "fr":
        return f"""💳 *Paiement en cours...*

📲 Une demande de paiement MTN MoMo a été envoyée.

1️⃣ Ouvrez l'application MTN MoMo
2️⃣ Approuvez le paiement de {int(amount * EUR_TO_XOF):,} XOF
3️⃣ Entrez votre code PIN

Référence : {booking_ref}
⏳ En attente de confirmation...{sim_note}"""
    else:
        sim_note_en = "\n\n🔸 _Simulation mode - payment auto-approved_" if is_sim else ""
        return f"""💳 *Processing payment...*

📲 An MTN MoMo payment request has been sent.

1️⃣ Open MTN MoMo app
2️⃣ Approve payment of {int(amount * EUR_TO_XOF):,} XOF
3️⃣ Enter your PIN

Reference: {booking_ref}
⏳ Waiting for confirmation...{sim_note_en}"""

def format_booking_confirmed(booking: Dict, lang: str) -> str:
    if lang == "fr":
        return f"""🎉 *Réservation Confirmée!*

✅ Votre billet {booking['booking_ref']} est prêt!

📋 *Détails :*
• Vol : {booking['airline']} {booking['flight_number']}
• Route : {get_city_name(booking['origin'])} → {get_city_name(booking['destination'])}
• Date : {booking['departure_date']}
• Catégorie : {booking['category']}
• Prix : {booking['price_eur']}€ ({booking['price_xof']:,} XOF)

📄 Votre billet PDF arrive...

Bon voyage! ✈️🌍"""
    else:
        return f"""🎉 *Booking Confirmed!*

✅ Your ticket {booking['booking_ref']} is ready!

📋 *Details:*
• Flight: {booking['airline']} {booking['flight_number']}
• Route: {get_city_name(booking['origin'])} → {get_city_name(booking['destination'])}
• Date: {booking['departure_date']}
• Category: {booking['category']}
• Price: {booking['price_eur']}€ ({booking['price_xof']:,} XOF)

📄 Your PDF ticket is coming...

Have a great trip! ✈️🌍"""

# ========== MAIN CONVERSATION HANDLER ==========

async def handle_message(phone: str, message_text: str, audio_id: str = None):
    """Main conversation handler"""
    session = await get_or_create_session(phone)
    
    # Handle voice message
    if audio_id:
        transcription = await transcribe_audio(None, audio_id)
        if transcription:
            message_text = transcription
            await send_whatsapp_message(phone, f"🎤 _\"{transcription}\"_")
        else:
            msg = "🎤 Les messages vocaux seront bientôt disponibles. Veuillez taper votre demande." if session.get("language", "fr") == "fr" else "🎤 Voice messages coming soon. Please type your request."
            await send_whatsapp_message(phone, msg)
            return
    
    text = message_text.strip().lower()
    original_text = message_text.strip()
    
    # Detect language
    if session.get("state") == ConversationState.IDLE:
        lang = detect_language(original_text)
        await update_session(phone, {"language": lang})
    else:
        lang = session.get("language", "fr")
    
    # Handle commands
    if text in ["start", "bonjour", "hello", "hi", "salut", "aide", "help", "menu"]:
        await clear_session(phone)
        if lang == "fr":
            msg = """✈️ *Bienvenue sur Travelio!*

Je suis votre assistant de réservation de vols.

💬 Dites-moi simplement où vous voulez aller:
_"Je veux un vol pour Paris vendredi prochain"_
_"Billet Cotonou-Dakar pour 2 personnes demain"_

🌍 Destinations populaires: Paris, Dakar, Lagos, Accra, Abidjan, Casablanca, Dubai..."""
        else:
            msg = """✈️ *Welcome to Travelio!*

I'm your flight booking assistant.

💬 Just tell me where you want to go:
_"I need a flight to Paris next Friday"_
_"Ticket Lagos to Accra for 2 people tomorrow"_

🌍 Popular destinations: Paris, Dakar, Lagos, Accra, Abidjan, Casablanca, Dubai..."""
        await send_whatsapp_message(phone, msg)
        return
    
    if text in ["annuler", "cancel", "stop", "reset"]:
        await clear_session(phone)
        msg = "❌ Recherche annulée. Envoyez un message pour recommencer." if lang == "fr" else "❌ Search cancelled. Send a message to start again."
        await send_whatsapp_message(phone, msg)
        return
    
    state = session.get("state", ConversationState.IDLE)
    
    # STATE: IDLE - Parse travel intent
    if state == ConversationState.IDLE:
        intent = await parse_travel_intent(original_text, lang)
        
        # Check for missing required fields
        if not intent.get("destination"):
            msg = "🤔 Quelle est votre destination ? (ex: Paris, Dakar, Lagos...)" if lang == "fr" else "🤔 What's your destination? (e.g., Paris, Dakar, Lagos...)"
            await update_session(phone, {"state": ConversationState.AWAITING_DESTINATION, "intent": intent})
            await send_whatsapp_message(phone, msg)
            return
        
        if not intent.get("departure_date"):
            msg = "📅 Quelle est votre date de départ ? (ex: demain, vendredi, 15 janvier...)" if lang == "fr" else "📅 When do you want to depart? (e.g., tomorrow, Friday, January 15...)"
            await update_session(phone, {"state": ConversationState.AWAITING_DATE, "intent": intent})
            await send_whatsapp_message(phone, msg)
            return
        
        # Search flights
        await search_and_show_flights(phone, intent, lang)
        return
    
    # STATE: AWAITING_DESTINATION
    if state == ConversationState.AWAITING_DESTINATION:
        intent = session.get("intent", {})
        
        # Try to extract destination
        dest_code = get_airport_code(original_text)
        if dest_code:
            intent["destination"] = dest_code
        else:
            # Use AI to parse
            parsed = await parse_travel_intent(original_text, lang)
            if parsed.get("destination"):
                intent["destination"] = get_airport_code(parsed["destination"]) or parsed["destination"]
            else:
                msg = "❓ Je n'ai pas reconnu cette ville. Essayez: Paris, Dakar, Lagos, Accra..." if lang == "fr" else "❓ I didn't recognize that city. Try: Paris, Dakar, Lagos, Accra..."
                await send_whatsapp_message(phone, msg)
                return
        
        if not intent.get("departure_date"):
            msg = "📅 Quelle est votre date de départ ?" if lang == "fr" else "📅 When do you want to depart?"
            await update_session(phone, {"state": ConversationState.AWAITING_DATE, "intent": intent})
            await send_whatsapp_message(phone, msg)
            return
        
        await search_and_show_flights(phone, intent, lang)
        return
    
    # STATE: AWAITING_DATE
    if state == ConversationState.AWAITING_DATE:
        intent = session.get("intent", {})
        
        # Parse date
        parsed = await parse_travel_intent(f"vol {original_text}", lang)
        if parsed.get("departure_date"):
            intent["departure_date"] = parsed["departure_date"]
        else:
            # Try simple date parsing
            today = datetime.now()
            if "demain" in text or "tomorrow" in text:
                intent["departure_date"] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            elif "après-demain" in text:
                intent["departure_date"] = (today + timedelta(days=2)).strftime("%Y-%m-%d")
            else:
                msg = "❓ Je n'ai pas compris la date. Essayez: demain, vendredi prochain, 15 janvier..." if lang == "fr" else "❓ I didn't understand the date. Try: tomorrow, next Friday, January 15..."
                await send_whatsapp_message(phone, msg)
                return
        
        await search_and_show_flights(phone, intent, lang)
        return
    
    # STATE: AWAITING_FLIGHT_SELECTION
    if state == ConversationState.AWAITING_FLIGHT_SELECTION:
        flights = session.get("flights", [])
        
        selection = None
        if text in ["1", "un", "one", "premier", "first", "plus bas", "le plus bas"]:
            selection = "PLUS_BAS"
        elif text in ["2", "deux", "two", "deuxième", "second", "rapide", "plus rapide"]:
            selection = "PLUS_RAPIDE"
        elif text in ["3", "trois", "three", "troisième", "third", "premium"]:
            selection = "PREMIUM"
        
        if not selection:
            msg = "❓ Tapez 1, 2 ou 3 pour choisir un vol" if lang == "fr" else "❓ Type 1, 2, or 3 to select a flight"
            await send_whatsapp_message(phone, msg)
            return
        
        selected = None
        for f in flights:
            if f.get("category") == selection:
                selected = f
                break
        
        if not selected:
            msg = "❌ Option non disponible. Réessayez." if lang == "fr" else "❌ Option not available. Try again."
            await send_whatsapp_message(phone, msg)
            return
        
        await update_session(phone, {"state": ConversationState.AWAITING_PAYMENT_CONFIRMATION, "selected_flight": selected})
        await send_whatsapp_message(phone, format_confirmation_request(selected, lang))
        return
    
    # STATE: AWAITING_PAYMENT_CONFIRMATION
    if state == ConversationState.AWAITING_PAYMENT_CONFIRMATION:
        selected = session.get("selected_flight")
        
        if text in ["oui", "yes", "ok", "o", "y", "confirmer", "confirm"]:
            if not selected:
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
                "passenger_name": phone,
                "airline": selected["airline"],
                "flight_number": selected["flight_number"],
                "origin": selected["origin"],
                "destination": selected["destination"],
                "departure_date": selected.get("departure_time", "").split("T")[0],
                "price_eur": selected["final_price"],
                "price_xof": selected["price_xof"],
                "category": selected["category"],
                "status": "pending_payment",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.bookings.insert_one(booking)
            
            # Initiate payment
            payment = await initiate_momo_payment(phone, selected["final_price"], booking_ref)
            
            await update_session(phone, {
                "state": ConversationState.AWAITING_MOMO_APPROVAL,
                "booking_id": booking["id"],
                "payment_reference": payment["reference_id"]
            })
            
            await send_whatsapp_message(phone, format_payment_initiated(booking_ref, selected["final_price"], lang, payment.get("is_simulated", False)))
            
            # Start payment polling
            asyncio.create_task(poll_payment_and_complete(phone, booking, payment["reference_id"], lang))
            
        elif text in ["non", "no", "n", "annuler", "cancel"]:
            # Go back to flight selection
            await update_session(phone, {"state": ConversationState.AWAITING_FLIGHT_SELECTION, "selected_flight": None})
            msg = "↩️ OK, choisissez un autre vol (1, 2 ou 3)" if lang == "fr" else "↩️ OK, choose another flight (1, 2, or 3)"
            await send_whatsapp_message(phone, msg)
        else:
            msg = "❓ Répondez oui ou non" if lang == "fr" else "❓ Reply yes or no"
            await send_whatsapp_message(phone, msg)
        return
    
    # STATE: AWAITING_MOMO_APPROVAL
    if state == ConversationState.AWAITING_MOMO_APPROVAL:
        msg = "⏳ Paiement en cours... Approuvez sur votre téléphone MTN." if lang == "fr" else "⏳ Payment in progress... Approve on your MTN phone."
        await send_whatsapp_message(phone, msg)
        return

async def search_and_show_flights(phone: str, intent: Dict, lang: str):
    """Search flights and show categorized options"""
    origin = get_airport_code(intent.get("origin", "Dakar")) or "DSS"
    destination = get_airport_code(intent["destination"]) or intent["destination"].upper()[:3]
    date = intent["departure_date"]
    passengers = intent.get("passengers", 1)
    
    # Send searching message
    msg = f"🔍 Recherche de vols {get_city_name(origin)} → {get_city_name(destination)}..." if lang == "fr" else f"🔍 Searching flights {get_city_name(origin)} → {get_city_name(destination)}..."
    await send_whatsapp_message(phone, msg)
    
    # Search Amadeus
    flights = await search_amadeus_flights(origin, destination, date, passengers)
    
    if not flights:
        await clear_session(phone)
        msg = "😔 Recherche indisponible, réessayez." if lang == "fr" else "😔 Search unavailable, please try again."
        await send_whatsapp_message(phone, msg)
        return
    
    # Categorize flights
    categorized = categorize_flights(flights)
    
    if not categorized:
        await clear_session(phone)
        msg = "😔 Aucun vol trouvé pour ces critères." if lang == "fr" else "😔 No flights found for these criteria."
        await send_whatsapp_message(phone, msg)
        return
    
    # Store flights with categories
    flights_with_cat = list(categorized.values())
    
    await update_session(phone, {
        "state": ConversationState.AWAITING_FLIGHT_SELECTION,
        "intent": intent,
        "flights": flights_with_cat
    })
    
    # Send formatted message
    await send_whatsapp_message(phone, format_flight_options_message(categorized, origin, destination, date))

async def poll_payment_and_complete(phone: str, booking: Dict, reference_id: str, lang: str):
    """Poll MoMo payment status and complete booking"""
    for attempt in range(10):
        await asyncio.sleep(3)
        
        status = await check_momo_status(reference_id)
        
        if status == "SUCCESSFUL":
            await db.bookings.update_one({"id": booking["id"]}, {"$set": {"status": "confirmed"}})
            
            # Generate ticket
            ticket_filename = generate_ticket_pdf(booking)
            
            # Send confirmation
            await send_whatsapp_message(phone, format_booking_confirmed(booking, lang))
            
            # Send PDF
            await asyncio.sleep(2)
            base_url = os.environ.get('APP_BASE_URL', 'https://voice-travel-booking.preview.emergentagent.com')
            await send_whatsapp_document(phone, f"{base_url}/api/tickets/{ticket_filename}", ticket_filename, f"🎫 {booking['booking_ref']}")
            
            await clear_session(phone)
            return
        
        elif status == "FAILED":
            await db.bookings.update_one({"id": booking["id"]}, {"$set": {"status": "payment_failed"}})
            msg = "❌ Paiement échoué. Réessayez ou changez de méthode." if lang == "fr" else "❌ Payment failed. Try again or use another method."
            await send_whatsapp_message(phone, msg)
            await clear_session(phone)
            return
    
    # Timeout
    msg = "⏰ Délai dépassé. Réessayez." if lang == "fr" else "⏰ Timeout. Please try again."
    await send_whatsapp_message(phone, msg)
    await clear_session(phone)

# ========== WEBHOOK ROUTES ==========

@api_router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN:
        return JSONResponse(content=int(params.get("hub.challenge", 0)), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

@api_router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        logger.info(f"Webhook: {json.dumps(body)[:300]}")
        
        messages = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
        
        for msg in messages:
            phone = msg.get("from", "")
            msg_type = msg.get("type", "text")
            
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
                background_tasks.add_task(handle_message, phone, text, None)
            elif msg_type == "audio":
                audio_id = msg.get("audio", {}).get("id")
                background_tasks.add_task(handle_message, phone, "", audio_id)
            elif msg_type == "interactive":
                interactive = msg.get("interactive", {})
                text = interactive.get("button_reply", {}).get("id", "") or interactive.get("list_reply", {}).get("id", "")
                background_tasks.add_task(handle_message, phone, text, None)
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# ========== OTHER ROUTES ==========

@api_router.get("/")
async def root():
    return {"message": "Travelio WhatsApp Agent", "version": "4.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "type": "whatsapp_agent", "version": "4.0.0"}

@api_router.get("/tickets/{filename}")
async def get_ticket(filename: str):
    filepath = TICKETS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Ticket not found")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)

@api_router.post("/test/message")
async def test_message(phone: str, message: str):
    """Test endpoint to simulate WhatsApp message"""
    await handle_message(phone, message, None)
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return {"status": "processed", "session": session}

@api_router.get("/test/flights")
async def test_flights(origin: str = "DSS", destination: str = "CDG", date: str = None):
    """Test Amadeus flight search"""
    if not date:
        date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    flights = await search_amadeus_flights(origin, destination, date, 1)
    categorized = categorize_flights(flights)
    return {"flights": flights, "categorized": categorized}

# Include router
app.include_router(api_router)

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("shutdown")
async def shutdown():
    client.close()
