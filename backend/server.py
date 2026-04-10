from fastapi import FastAPI, APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
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
import stripe
import math

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'travelio')]

# Create the main app
app = FastAPI(title="Travelio WhatsApp Agent", version="5.0.0")
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directories
TICKETS_DIR = ROOT_DIR / 'tickets'
TICKETS_DIR.mkdir(exist_ok=True)

# Constants
API_TIMEOUT = 10.0
EUR_TO_XOF = 655.957

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

# ========== CONFIGURATION ==========

WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'travelio_verify_2024')
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'https://voice-travel-booking.preview.emergentagent.com')

# Airport codes
AIRPORT_CODES = {
    "dakar": "DSS", "lagos": "LOS", "accra": "ACC", "abidjan": "ABJ",
    "ouagadougou": "OUA", "bamako": "BKO", "conakry": "CKY", "niamey": "NIM",
    "cotonou": "COO", "lome": "LFW", "paris": "CDG", "london": "LHR",
    "casablanca": "CMN", "addis ababa": "ADD", "nairobi": "NBO", "dubai": "DXB",
    "new york": "JFK", "douala": "DLA", "libreville": "LBV", "bruxelles": "BRU"
}
CODE_TO_CITY = {v: k.title() for k, v in AIRPORT_CODES.items()}

AIRLINES = [("Air France", "AF"), ("Ethiopian Airlines", "ET"), ("Royal Air Maroc", "AT"), ("Brussels Airlines", "SN")]


# ========== PAYMENT SERVICE ==========

class PaymentOperator:
    MTN_MOMO = "mtn_momo"
    MOOV_MONEY = "moov_money"
    GOOGLE_PAY = "google_pay"
    APPLE_PAY = "apple_pay"
    CELTIIS_CASH = "celtiis_cash"  # Future - not active


class PaymentService:
    """
    Unified payment service abstraction.
    Supports: MTN MoMo, Moov Money, Google Pay, Apple Pay
    Future: Celtiis Cash (stub only)
    """
    
    def __init__(self):
        self.logger = logging.getLogger("PaymentService")
    
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Convert phone to format: 22967000000 (no + prefix)"""
        phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        # Remove leading 00 if present
        if phone.startswith("00"):
            phone = phone[2:]
        # Add country code if missing (assume Benin 229)
        if len(phone) == 8:
            phone = "229" + phone
        return phone
    
    @staticmethod
    def _eur_to_xof(amount_eur: float) -> int:
        """Convert EUR to XOF, round up to nearest 5"""
        xof = amount_eur * EUR_TO_XOF
        # Round up to nearest 5
        return int(math.ceil(xof / 5) * 5)
    
    async def request_payment(
        self, 
        operator: str, 
        phone: str, 
        amount_eur: float, 
        booking_id: str,
        destination: str = ""
    ) -> Dict[str, Any]:
        """
        Main entry point - dispatches to correct handler based on operator.
        Returns: {status, reference_id, payment_url (for card), is_simulated}
        """
        amount_xof = self._eur_to_xof(amount_eur)
        phone_normalized = self._normalize_phone(phone)
        
        self.logger.info(f"Payment request: {operator} | {amount_eur}€ ({amount_xof} XOF) | {booking_id}")
        
        try:
            if operator == PaymentOperator.MTN_MOMO:
                return await self._momo_pay(phone_normalized, amount_xof, booking_id, destination)
            
            elif operator == PaymentOperator.MOOV_MONEY:
                return await self._moov_pay(phone_normalized, amount_xof, booking_id, destination)
            
            elif operator == PaymentOperator.GOOGLE_PAY:
                return await self._google_pay(amount_eur, booking_id)
            
            elif operator == PaymentOperator.APPLE_PAY:
                return await self._apple_pay(amount_eur, booking_id)
            
            elif operator == PaymentOperator.CELTIIS_CASH:
                return await self._celtiis_pay(phone_normalized, amount_xof, booking_id)
            
            else:
                raise ValueError(f"Unknown operator: {operator}")
                
        except Exception as e:
            self.logger.error(f"Payment error ({operator}): {e}")
            return {"status": "error", "error": str(e), "is_simulated": False}
    
    async def _momo_pay(self, phone: str, amount_xof: int, booking_id: str, destination: str) -> Dict:
        """MTN MoMo Collection API"""
        api_user = os.environ.get('MOMO_API_USER')
        api_key = os.environ.get('MOMO_API_KEY')
        subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
        base_url = os.environ.get('MOMO_BASE_URL', 'https://sandbox.momodeveloper.mtn.com')
        environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
        
        # Check if configured
        if not all([api_user, api_key, subscription_key]) or api_user == 'your_uuid_here':
            self.logger.warning("MTN MoMo not configured - simulating")
            return {
                "status": "pending",
                "reference_id": f"MOMO-SIM-{uuid.uuid4().hex[:8].upper()}",
                "is_simulated": True,
                "operator": PaymentOperator.MTN_MOMO
            }
        
        # Get access token
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                token_response = await client.post(
                    f"{base_url}/collection/token/",
                    auth=(api_user, api_key),
                    headers={"Ocp-Apim-Subscription-Key": subscription_key}
                )
                if token_response.status_code != 200:
                    raise Exception(f"Token failed: {token_response.status_code}")
                token = token_response.json().get("access_token")
        except Exception as e:
            self.logger.error(f"MoMo token error: {e}")
            return {
                "status": "pending",
                "reference_id": f"MOMO-SIM-{uuid.uuid4().hex[:8].upper()}",
                "is_simulated": True,
                "operator": PaymentOperator.MTN_MOMO
            }
        
        # Request payment
        reference_id = str(uuid.uuid4())
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(
                    f"{base_url}/collection/v1_0/requesttopay",
                    json={
                        "amount": str(amount_xof),
                        "currency": "XOF",
                        "externalId": booking_id,
                        "payer": {"partyIdType": "MSISDN", "partyId": phone},
                        "payerMessage": f"Travelio - Vol {destination}",
                        "payeeNote": f"Booking {booking_id}"
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Reference-Id": reference_id,
                        "X-Target-Environment": environment,
                        "Ocp-Apim-Subscription-Key": subscription_key,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 202:
                    return {
                        "status": "pending",
                        "reference_id": reference_id,
                        "is_simulated": False,
                        "operator": PaymentOperator.MTN_MOMO
                    }
        except Exception as e:
            self.logger.error(f"MoMo request error: {e}")
        
        # Fallback to simulation
        return {
            "status": "pending",
            "reference_id": f"MOMO-SIM-{uuid.uuid4().hex[:8].upper()}",
            "is_simulated": True,
            "operator": PaymentOperator.MTN_MOMO
        }
    
    async def _moov_pay(self, phone: str, amount_xof: int, booking_id: str, destination: str) -> Dict:
        """Moov Money (Flooz) API"""
        api_key = os.environ.get('MOOV_API_KEY')
        base_url = os.environ.get('MOOV_BASE_URL', 'https://api.moov-africa.bj')
        
        if not api_key or api_key == 'your_key_here':
            self.logger.warning("Moov Money not configured - simulating")
            return {
                "status": "pending",
                "reference_id": f"MOOV-SIM-{uuid.uuid4().hex[:8].upper()}",
                "is_simulated": True,
                "operator": PaymentOperator.MOOV_MONEY
            }
        
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(
                    f"{base_url}/v1/cash-in",
                    json={
                        "amount": amount_xof,
                        "currency": "XOF",
                        "msisdn": phone,
                        "description": f"Travelio - Vol {destination}",
                        "externalRef": booking_id
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code in [200, 201, 202]:
                    data = response.json()
                    return {
                        "status": "pending",
                        "reference_id": data.get("transactionId", booking_id),
                        "is_simulated": False,
                        "operator": PaymentOperator.MOOV_MONEY
                    }
        except Exception as e:
            self.logger.error(f"Moov request error: {e}")
        
        # Mock response if API unreachable
        return {
            "status": "pending",
            "reference_id": f"MOOV-SIM-{uuid.uuid4().hex[:8].upper()}",
            "is_simulated": True,
            "operator": PaymentOperator.MOOV_MONEY
        }
    
    async def _google_pay(self, amount_eur: float, booking_id: str) -> Dict:
        """Google Pay via Stripe Payment Intent"""
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        
        if not stripe_key or stripe_key == 'your_stripe_secret_key_here':
            self.logger.warning("Stripe not configured - simulating")
            return {
                "status": "pending_redirect",
                "reference_id": f"GPAY-SIM-{uuid.uuid4().hex[:8].upper()}",
                "payment_url": f"{APP_BASE_URL}/pay/{booking_id}?sim=1",
                "is_simulated": True,
                "operator": PaymentOperator.GOOGLE_PAY
            }
        
        try:
            # Create Stripe PaymentIntent
            amount_cents = int(amount_eur * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="eur",
                payment_method_types=["card"],
                metadata={
                    "booking_id": booking_id,
                    "operator": "google_pay"
                }
            )
            
            # Store intent for later verification
            await db.payment_intents.insert_one({
                "booking_id": booking_id,
                "stripe_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount_eur": amount_eur,
                "status": "pending",
                "operator": PaymentOperator.GOOGLE_PAY,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "status": "pending_redirect",
                "reference_id": intent.id,
                "payment_url": f"{APP_BASE_URL}/pay/{booking_id}",
                "is_simulated": False,
                "operator": PaymentOperator.GOOGLE_PAY
            }
        except Exception as e:
            self.logger.error(f"Stripe error: {e}")
            return {
                "status": "pending_redirect",
                "reference_id": f"GPAY-SIM-{uuid.uuid4().hex[:8].upper()}",
                "payment_url": f"{APP_BASE_URL}/pay/{booking_id}?sim=1",
                "is_simulated": True,
                "operator": PaymentOperator.GOOGLE_PAY
            }
    
    async def _apple_pay(self, amount_eur: float, booking_id: str) -> Dict:
        """Apple Pay via Stripe (same flow as Google Pay)"""
        # Apple Pay uses same Stripe integration
        result = await self._google_pay(amount_eur, booking_id)
        result["operator"] = PaymentOperator.APPLE_PAY
        return result
    
    async def _celtiis_pay(self, phone: str, amount_xof: int, booking_id: str) -> Dict:
        """
        Celtiis Cash - FUTURE IMPLEMENTATION
        
        TODO: Pending partner agreement with Hermann / SBIN
        Contact: dyarakou@celtiis.bj
        
        DO NOT expose to users yet.
        """
        raise NotImplementedError(
            "Celtiis Cash — pending partner agreement. "
            "Contact: dyarakou@celtiis.bj"
        )
    
    async def poll_status(self, operator: str, reference_id: str, max_attempts: int = 10) -> str:
        """Poll payment status - mobile money only"""
        for attempt in range(max_attempts):
            await asyncio.sleep(3)
            
            status = await self._check_status(operator, reference_id)
            self.logger.info(f"Poll {attempt + 1}/{max_attempts}: {operator} {reference_id} = {status}")
            
            if status in ["SUCCESSFUL", "SUCCESS", "COMPLETED"]:
                return "SUCCESSFUL"
            elif status in ["FAILED", "REJECTED", "CANCELLED"]:
                return "FAILED"
        
        return "TIMEOUT"
    
    async def _check_status(self, operator: str, reference_id: str) -> str:
        """Check payment status for specific operator"""
        
        # Simulated payments always succeed
        if "-SIM-" in reference_id:
            return "SUCCESSFUL"
        
        if operator == PaymentOperator.MTN_MOMO:
            return await self._check_momo_status(reference_id)
        elif operator == PaymentOperator.MOOV_MONEY:
            return await self._check_moov_status(reference_id)
        
        return "PENDING"
    
    async def _check_momo_status(self, reference_id: str) -> str:
        """Check MTN MoMo payment status"""
        api_user = os.environ.get('MOMO_API_USER')
        api_key = os.environ.get('MOMO_API_KEY')
        subscription_key = os.environ.get('MOMO_SUBSCRIPTION_KEY')
        base_url = os.environ.get('MOMO_BASE_URL')
        environment = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
        
        if not all([api_user, api_key, subscription_key]):
            return "SUCCESSFUL"
        
        try:
            # Get token
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                token_resp = await client.post(
                    f"{base_url}/collection/token/",
                    auth=(api_user, api_key),
                    headers={"Ocp-Apim-Subscription-Key": subscription_key}
                )
                token = token_resp.json().get("access_token")
                
                # Check status
                status_resp = await client.get(
                    f"{base_url}/collection/v1_0/requesttopay/{reference_id}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Target-Environment": environment,
                        "Ocp-Apim-Subscription-Key": subscription_key
                    }
                )
                
                if status_resp.status_code == 200:
                    return status_resp.json().get("status", "PENDING")
        except Exception as e:
            self.logger.error(f"MoMo status check error: {e}")
        
        return "PENDING"
    
    async def _check_moov_status(self, reference_id: str) -> str:
        """Check Moov Money payment status"""
        api_key = os.environ.get('MOOV_API_KEY')
        base_url = os.environ.get('MOOV_BASE_URL')
        
        if not api_key or api_key == 'your_key_here':
            return "SUCCESSFUL"
        
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    f"{base_url}/v1/transaction/{reference_id}",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "PENDING")
                    # Normalize status
                    if status.upper() in ["SUCCESS", "COMPLETED", "SUCCESSFUL"]:
                        return "SUCCESSFUL"
                    elif status.upper() in ["FAILED", "REJECTED", "CANCELLED"]:
                        return "FAILED"
                    return "PENDING"
        except Exception as e:
            self.logger.error(f"Moov status check error: {e}")
        
        return "PENDING"


# Global payment service instance
payment_service = PaymentService()


# ========== CONVERSATION STATES ==========

class ConversationState:
    IDLE = "idle"
    AWAITING_DESTINATION = "awaiting_destination"
    AWAITING_DATE = "awaiting_date"
    AWAITING_FLIGHT_SELECTION = "awaiting_flight_selection"
    AWAITING_PAYMENT_METHOD = "awaiting_payment_method"
    AWAITING_PAYMENT_CONFIRMATION = "awaiting_payment_confirmation"
    AWAITING_MOBILE_PAYMENT = "awaiting_mobile_payment"
    AWAITING_CARD_PAYMENT = "awaiting_card_payment"


# ========== HELPER FUNCTIONS ==========

def generate_booking_ref() -> str:
    chars = string.ascii_uppercase + string.digits
    return f"TRV-{''.join(random.choices(chars, k=6))}"

def get_airport_code(city_name: str) -> Optional[str]:
    name_lower = city_name.lower().strip()
    for city, code in AIRPORT_CODES.items():
        if city in name_lower or name_lower in city:
            return code
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

def format_duration(iso_duration: str) -> str:
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return f"{hours}h{minutes:02d}" if hours else f"0h{minutes:02d}"
    return iso_duration

def parse_duration_minutes(iso_duration: str) -> int:
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if match:
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    return 9999

def apply_travelio_margin(amadeus_price: float) -> float:
    return round(amadeus_price + 15 + (amadeus_price * 0.05), 2)

def eur_to_xof(eur: float) -> int:
    return int(math.ceil(eur * EUR_TO_XOF / 5) * 5)


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
        "selected_payment_method": None,
        "booking_id": None,
        "booking_ref": None,
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
        "selected_payment_method": None,
        "booking_id": None,
        "booking_ref": None,
        "payment_reference": None,
        "last_activity": datetime.now(timezone.utc).isoformat()
    }})


# ========== WHATSAPP API ==========

async def send_whatsapp_message(to: str, message: str) -> Dict:
    if not WHATSAPP_PHONE_ID or not WHATSAPP_TOKEN or WHATSAPP_PHONE_ID == 'your_phone_id_here':
        logger.info(f"[WhatsApp SIM] To {to}:\n{message[:500]}...")
        return {"status": "simulated"}
    
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
        return {"status": "failed"}

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


# ========== AI INTENT PARSING ==========

async def parse_travel_intent(text: str, language: str = "fr") -> Dict[str, Any]:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            return fallback_parse_intent(text, language)
        
        system_prompt = f"""Tu es un assistant de réservation de vols. Extrais les informations de voyage.

Retourne UNIQUEMENT un JSON valide:
{{
  "origin": "code IATA ou ville (défaut: COO si non mentionné)",
  "destination": "code IATA ou ville ou null",
  "departure_date": "YYYY-MM-DD ou null",
  "return_date": "YYYY-MM-DD ou null",
  "passengers": nombre (défaut: 1)
}}

Codes IATA: DSS (Dakar), COO (Cotonou), LOS (Lagos), ACC (Accra), ABJ (Abidjan), CDG (Paris), LHR (Londres)
Aujourd'hui: {datetime.now().strftime("%Y-%m-%d")}

UNIQUEMENT le JSON."""

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
    import re
    text_lower = text.lower()
    
    destination = None
    origin = "COO"
    
    for city, code in AIRPORT_CODES.items():
        if city in text_lower:
            if destination is None:
                destination = code
            else:
                origin = code
    
    departure_date = None
    today = datetime.now()
    if "demain" in text_lower or "tomorrow" in text_lower:
        departure_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "vendredi" in text_lower or "friday" in text_lower:
        days_ahead = (4 - today.weekday()) % 7 or 7
        departure_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    
    passengers = 1
    pax_match = re.search(r'(\d+)\s*(passager|personne|adulte|people|passenger|adult)', text_lower)
    if pax_match:
        passengers = int(pax_match.group(1))
    
    return {"origin": origin, "destination": destination, "departure_date": departure_date, "passengers": passengers}


# ========== AMADEUS FLIGHT SEARCH ==========

async def get_amadeus_token() -> Optional[str]:
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
    token = await get_amadeus_token()
    base_url = os.environ.get('AMADEUS_BASE_URL', 'https://test.api.amadeus.com')
    
    if not token:
        return generate_mock_flights(origin, destination, departure_date, adults)
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                f"{base_url}/v2/shopping/flight-offers",
                params={"originLocationCode": origin, "destinationLocationCode": destination,
                        "departureDate": departure_date, "adults": adults, "currencyCode": "EUR", "max": 20},
                headers={"Authorization": f"Bearer {token}"})
            
            if response.status_code == 200:
                return parse_amadeus_response(response.json().get("data", []))
    except Exception as e:
        logger.error(f"Amadeus search error: {e}")
    
    return generate_mock_flights(origin, destination, departure_date, adults)

def parse_amadeus_response(offers: List[Dict]) -> List[Dict]:
    flights = []
    airline_names = {"AF": "Air France", "KL": "KLM", "LH": "Lufthansa", "BA": "British Airways",
                     "ET": "Ethiopian Airlines", "AT": "Royal Air Maroc", "HF": "Air Côte d'Ivoire",
                     "QR": "Qatar Airways", "EK": "Emirates", "TK": "Turkish Airlines", "SN": "Brussels Airlines"}
    
    for offer in offers:
        try:
            amadeus_price = float(offer.get("price", {}).get("total", 0))
            final_price = apply_travelio_margin(amadeus_price)
            
            itineraries = offer.get("itineraries", [])
            if not itineraries:
                continue
            
            outbound = itineraries[0]
            segments = outbound.get("segments", [])
            if not segments:
                continue
            
            first_seg, last_seg = segments[0], segments[-1]
            carrier_code = first_seg.get("carrierCode", "XX")
            
            flights.append({
                "id": offer.get("id", str(uuid.uuid4())),
                "amadeus_price": amadeus_price,
                "final_price": final_price,
                "price_xof": eur_to_xof(final_price),
                "airline": airline_names.get(carrier_code, carrier_code),
                "carrier_code": carrier_code,
                "flight_number": f"{carrier_code}{first_seg.get('number', '000')}",
                "origin": first_seg.get("departure", {}).get("iataCode", ""),
                "destination": last_seg.get("arrival", {}).get("iataCode", ""),
                "departure_time": first_seg.get("departure", {}).get("at", ""),
                "arrival_time": last_seg.get("arrival", {}).get("at", ""),
                "duration": outbound.get("duration", "PT0H0M"),
                "duration_formatted": format_duration(outbound.get("duration", "PT0H0M")),
                "duration_minutes": parse_duration_minutes(outbound.get("duration", "PT0H0M")),
                "stops": len(segments) - 1,
                "stops_text": "Direct" if len(segments) == 1 else f"{len(segments) - 1} escale{'s' if len(segments) > 2 else ''}",
                "is_demo": False
            })
        except Exception as e:
            logger.error(f"Parse error: {e}")
    return flights

def generate_mock_flights(origin: str, destination: str, date: str, adults: int = 1) -> List[Dict]:
    flights = []
    base_prices = [185, 220, 310, 275, 195]
    durations = [("PT5H30M", 1), ("PT3H15M", 0), ("PT4H00M", 0), ("PT6H45M", 2), ("PT4H30M", 1)]
    
    for i in range(min(5, len(base_prices))):
        airline_name, carrier = random.choice(AIRLINES)
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
    if not flights:
        return {}
    
    by_price = sorted(flights, key=lambda f: f["final_price"])
    by_duration = sorted(flights, key=lambda f: f["duration_minutes"])
    
    max_price = max(f["final_price"] for f in flights)
    max_duration = max(f["duration_minutes"] for f in flights)
    
    def get_score(f):
        price_score = (max_price - f["final_price"]) / max_price if max_price > 0 else 0
        duration_score = (max_duration - f["duration_minutes"]) / max_duration if max_duration > 0 else 0
        direct_bonus = 1.0 if f.get("stops", 0) == 0 else (0.5 if f.get("stops") == 1 else 0)
        return (price_score * 0.4) + (duration_score * 0.4) + (direct_bonus * 0.2)
    
    by_score = sorted(flights, key=get_score, reverse=True)
    
    result = {}
    used_ids = set()
    
    for f in by_price:
        if f["id"] not in used_ids:
            result["PLUS_BAS"] = {**f, "category": "PLUS_BAS", "label": "💚 LE PLUS BAS"}
            used_ids.add(f["id"])
            break
    
    for f in by_duration:
        if f["id"] not in used_ids:
            result["PLUS_RAPIDE"] = {**f, "category": "PLUS_RAPIDE", "label": "⚡ LE PLUS RAPIDE"}
            used_ids.add(f["id"])
            break
    
    for f in by_score:
        if f["id"] not in used_ids:
            result["PREMIUM"] = {**f, "category": "PREMIUM", "label": "👑 PREMIUM"}
            used_ids.add(f["id"])
            break
    
    return result


# ========== PDF TICKET GENERATION ==========

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
    
    payment_method_display = {
        PaymentOperator.MTN_MOMO: "MTN MoMo",
        PaymentOperator.MOOV_MONEY: "Moov Money",
        PaymentOperator.GOOGLE_PAY: "Google Pay",
        PaymentOperator.APPLE_PAY: "Apple Pay"
    }.get(booking.get('payment_method'), booking.get('payment_method', 'N/A'))
    
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
        ["Paiement", payment_method_display],
        ["Référence", f"*{booking_ref}*"],
    ]
    
    table = Table(ticket_data, colWidths=[80*mm, 80*mm])
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
    elements.append(Paragraph("Scannez le QR code pour vérifier • Bon voyage! 🌍", ParagraphStyle('Footer', fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))
    
    doc.build(elements)
    return filename


# ========== MESSAGE FORMATTING ==========

def format_flight_options_message(categorized: Dict, origin: str, destination: str, date: str) -> str:
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

def format_payment_method_selection(amount_eur: float, lang: str) -> str:
    amount_xof = eur_to_xof(amount_eur)
    
    if lang == "fr":
        return f"""💳 *Choisissez votre moyen de paiement*
Montant : *{amount_eur}€* ({amount_xof:,} XOF)

1️⃣ MTN MoMo
2️⃣ Moov Money (Flooz)
3️⃣ Google Pay
4️⃣ Apple Pay

Répondez 1, 2, 3 ou 4"""
    else:
        return f"""💳 *Choose your payment method*
Amount: *{amount_eur}€* ({amount_xof:,} XOF)

1️⃣ MTN MoMo
2️⃣ Moov Money (Flooz)
3️⃣ Google Pay
4️⃣ Apple Pay

Reply 1, 2, 3, or 4"""

def format_mobile_payment_initiated(operator: str, booking_ref: str, amount_xof: int, lang: str, is_sim: bool) -> str:
    operator_name = "MTN MoMo" if operator == PaymentOperator.MTN_MOMO else "Moov Money"
    sim_note = "\n\n🔸 _Mode simulation - paiement auto-approuvé_" if is_sim else ""
    
    if lang == "fr":
        return f"""💳 *Paiement {operator_name} en cours...*

📲 Une demande de paiement a été envoyée.

1️⃣ Ouvrez l'application {operator_name}
2️⃣ Approuvez le paiement de {amount_xof:,} XOF
3️⃣ Entrez votre code PIN

Référence : {booking_ref}
⏳ En attente de confirmation...{sim_note}"""
    else:
        sim_note_en = "\n\n🔸 _Simulation mode - payment auto-approved_" if is_sim else ""
        return f"""💳 *{operator_name} payment in progress...*

📲 A payment request has been sent.

1️⃣ Open {operator_name} app
2️⃣ Approve payment of {amount_xof:,} XOF
3️⃣ Enter your PIN

Reference: {booking_ref}
⏳ Waiting for confirmation...{sim_note_en}"""

def format_card_payment_link(payment_url: str, lang: str) -> str:
    if lang == "fr":
        return f"""🔗 Finalisez votre paiement ici :
{payment_url}

✅ Google Pay disponible sur Android
✅ Apple Pay disponible sur iPhone / Mac
💳 Carte bancaire acceptée sur tous les appareils

⏳ Lien valable 15 minutes."""
    else:
        return f"""🔗 Complete your payment here:
{payment_url}

✅ Google Pay available on Android
✅ Apple Pay available on iPhone / Mac
💳 Card payment accepted on all devices

⏳ Link valid for 15 minutes."""

def format_payment_success(lang: str) -> str:
    if lang == "fr":
        return """✅ Paiement confirmé !
🎫 Génération de votre billet en cours...
Vous le recevrez dans quelques secondes."""
    else:
        return """✅ Payment confirmed!
🎫 Generating your ticket...
You'll receive it in a few seconds."""

def format_payment_failed(operator: str, lang: str) -> str:
    operator_name = {"mtn_momo": "MTN MoMo", "moov_money": "Moov Money"}.get(operator, operator)
    
    if lang == "fr":
        return f"""❌ Paiement {operator_name} échoué.
Réessayez ou choisissez une autre méthode."""
    else:
        return f"""❌ {operator_name} payment failed.
Try again or choose another method."""

def format_retry_options(operator: str, lang: str) -> str:
    operator_name = {"mtn_momo": "MTN MoMo", "moov_money": "Moov Money", "google_pay": "Google Pay", "apple_pay": "Apple Pay"}.get(operator, operator)
    
    if lang == "fr":
        return f"""Souhaitez-vous réessayer ?

1️⃣ Réessayer avec {operator_name}
2️⃣ Choisir une autre méthode
3️⃣ Annuler la réservation"""
    else:
        return f"""Would you like to retry?

1️⃣ Retry with {operator_name}
2️⃣ Choose another method
3️⃣ Cancel booking"""

def format_booking_confirmed(booking: Dict, lang: str) -> str:
    if lang == "fr":
        return f"""✈️ Votre billet Travelio est prêt !
Vol {get_city_name(booking['origin'])} → {get_city_name(booking['destination'])}
📅 {booking['departure_date']}
🎫 Réservation : {booking['booking_ref']}
Bon voyage ! 🌍"""
    else:
        return f"""✈️ Your Travelio ticket is ready!
Flight {get_city_name(booking['origin'])} → {get_city_name(booking['destination'])}
📅 {booking['departure_date']}
🎫 Booking: {booking['booking_ref']}
Have a great trip! 🌍"""


# ========== MAIN CONVERSATION HANDLER ==========

async def handle_message(phone: str, message_text: str, audio_id: str = None):
    session = await get_or_create_session(phone)
    
    text = message_text.strip().lower()
    original_text = message_text.strip()
    
    if session.get("state") == ConversationState.IDLE:
        lang = detect_language(original_text)
        await update_session(phone, {"language": lang})
    else:
        lang = session.get("language", "fr")
    
    # Handle commands
    if text in ["start", "bonjour", "hello", "hi", "salut", "aide", "help", "menu"]:
        await clear_session(phone)
        msg = """✈️ *Bienvenue sur Travelio!*

Je suis votre assistant de réservation de vols.

💬 Dites-moi simplement où vous voulez aller:
_"Je veux un vol pour Paris vendredi prochain"_
_"Billet Cotonou-Dakar pour 2 personnes demain"_

🌍 Destinations: Paris, Dakar, Lagos, Accra, Abidjan...""" if lang == "fr" else """✈️ *Welcome to Travelio!*

I'm your flight booking assistant.

💬 Just tell me where you want to go:
_"I need a flight to Paris next Friday"_
_"Ticket Lagos to Accra for 2 people tomorrow"_

🌍 Destinations: Paris, Dakar, Lagos, Accra, Abidjan..."""
        await send_whatsapp_message(phone, msg)
        return
    
    if text in ["annuler", "cancel", "stop", "reset", "3"] and session.get("state") in [ConversationState.AWAITING_PAYMENT_METHOD, "retry"]:
        await clear_session(phone)
        msg = "❌ Réservation annulée. Envoyez un message pour recommencer." if lang == "fr" else "❌ Booking cancelled. Send a message to start again."
        await send_whatsapp_message(phone, msg)
        return
    
    state = session.get("state", ConversationState.IDLE)
    
    # STATE: IDLE - Parse travel intent
    if state == ConversationState.IDLE:
        intent = await parse_travel_intent(original_text, lang)
        
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
        
        await search_and_show_flights(phone, intent, lang)
        return
    
    # STATE: AWAITING_DESTINATION
    if state == ConversationState.AWAITING_DESTINATION:
        intent = session.get("intent", {})
        dest_code = get_airport_code(original_text)
        if dest_code:
            intent["destination"] = dest_code
        else:
            parsed = await parse_travel_intent(original_text, lang)
            if parsed.get("destination"):
                intent["destination"] = get_airport_code(parsed["destination"]) or parsed["destination"]
            else:
                msg = "❓ Je n'ai pas reconnu cette ville. Essayez: Paris, Dakar, Lagos..." if lang == "fr" else "❓ I didn't recognize that city. Try: Paris, Dakar, Lagos..."
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
        parsed = await parse_travel_intent(f"vol {original_text}", lang)
        if parsed.get("departure_date"):
            intent["departure_date"] = parsed["departure_date"]
        else:
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
        if text in ["1", "un", "one", "premier", "plus bas"]:
            selection = "PLUS_BAS"
        elif text in ["2", "deux", "two", "deuxième", "rapide"]:
            selection = "PLUS_RAPIDE"
        elif text in ["3", "trois", "three", "troisième", "premium"]:
            selection = "PREMIUM"
        
        if not selection:
            msg = "❓ Tapez 1, 2 ou 3 pour choisir un vol" if lang == "fr" else "❓ Type 1, 2, or 3 to select a flight"
            await send_whatsapp_message(phone, msg)
            return
        
        selected = next((f for f in flights if f.get("category") == selection), None)
        if not selected:
            msg = "❌ Option non disponible." if lang == "fr" else "❌ Option not available."
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
            "status": "awaiting_payment",
            "payment_method": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.bookings.insert_one(booking)
        
        await update_session(phone, {
            "state": ConversationState.AWAITING_PAYMENT_METHOD,
            "selected_flight": selected,
            "booking_id": booking["id"],
            "booking_ref": booking_ref
        })
        
        await send_whatsapp_message(phone, format_payment_method_selection(selected["final_price"], lang))
        return
    
    # STATE: AWAITING_PAYMENT_METHOD
    if state == ConversationState.AWAITING_PAYMENT_METHOD:
        selected = session.get("selected_flight")
        booking_ref = session.get("booking_ref")
        booking_id = session.get("booking_id")
        
        if not selected or not booking_ref:
            await clear_session(phone)
            msg = "❌ Session expirée. Recommencez." if lang == "fr" else "❌ Session expired. Start again."
            await send_whatsapp_message(phone, msg)
            return
        
        operator = None
        if text in ["1", "mtn", "momo", "mtn momo"]:
            operator = PaymentOperator.MTN_MOMO
        elif text in ["2", "moov", "flooz", "moov money"]:
            operator = PaymentOperator.MOOV_MONEY
        elif text in ["3", "google", "google pay", "gpay"]:
            operator = PaymentOperator.GOOGLE_PAY
        elif text in ["4", "apple", "apple pay", "apay"]:
            operator = PaymentOperator.APPLE_PAY
        
        if not operator:
            msg = "❓ Répondez 1, 2, 3 ou 4" if lang == "fr" else "❓ Reply 1, 2, 3, or 4"
            await send_whatsapp_message(phone, msg)
            return
        
        # Update booking with payment method
        await db.bookings.update_one({"id": booking_id}, {"$set": {"payment_method": operator}})
        
        # Initiate payment
        result = await payment_service.request_payment(
            operator=operator,
            phone=phone,
            amount_eur=selected["final_price"],
            booking_id=booking_ref,
            destination=get_city_name(selected["destination"])
        )
        
        if result.get("status") == "error":
            await send_whatsapp_message(phone, format_payment_failed(operator, lang))
            await send_whatsapp_message(phone, format_retry_options(operator, lang))
            await update_session(phone, {"state": "retry", "selected_payment_method": operator})
            return
        
        await update_session(phone, {
            "payment_reference": result.get("reference_id"),
            "selected_payment_method": operator
        })
        
        if operator in [PaymentOperator.MTN_MOMO, PaymentOperator.MOOV_MONEY]:
            # Mobile money - send notification and poll
            amount_xof = eur_to_xof(selected["final_price"])
            await send_whatsapp_message(phone, format_mobile_payment_initiated(operator, booking_ref, amount_xof, lang, result.get("is_simulated", False)))
            
            await update_session(phone, {"state": ConversationState.AWAITING_MOBILE_PAYMENT})
            
            # Start polling in background
            asyncio.create_task(poll_and_complete_payment(
                phone, booking_id, booking_ref, operator, result["reference_id"], lang
            ))
        else:
            # Card payment - send link
            await send_whatsapp_message(phone, format_card_payment_link(result["payment_url"], lang))
            await update_session(phone, {"state": ConversationState.AWAITING_CARD_PAYMENT})
        
        return
    
    # STATE: Retry
    if state == "retry":
        last_operator = session.get("selected_payment_method")
        
        if text == "1":
            # Retry same method
            await update_session(phone, {"state": ConversationState.AWAITING_PAYMENT_METHOD})
            await handle_message(phone, last_operator.replace("_", " ") if last_operator else "1")
        elif text == "2":
            # Choose different method
            selected = session.get("selected_flight")
            if selected:
                await update_session(phone, {"state": ConversationState.AWAITING_PAYMENT_METHOD})
                await send_whatsapp_message(phone, format_payment_method_selection(selected["final_price"], lang))
            else:
                await clear_session(phone)
        else:
            # Show retry options again
            await send_whatsapp_message(phone, format_retry_options(last_operator or "payment", lang))
        return
    
    # STATE: AWAITING_MOBILE_PAYMENT
    if state == ConversationState.AWAITING_MOBILE_PAYMENT:
        msg = "⏳ Paiement en cours... Approuvez sur votre téléphone." if lang == "fr" else "⏳ Payment in progress... Approve on your phone."
        await send_whatsapp_message(phone, msg)
        return
    
    # STATE: AWAITING_CARD_PAYMENT
    if state == ConversationState.AWAITING_CARD_PAYMENT:
        booking_ref = session.get("booking_ref")
        msg = f"⏳ En attente du paiement...\nUtilisez le lien envoyé pour payer.\nRéférence : {booking_ref}" if lang == "fr" else f"⏳ Waiting for payment...\nUse the link sent to complete payment.\nReference: {booking_ref}"
        await send_whatsapp_message(phone, msg)
        return


async def search_and_show_flights(phone: str, intent: Dict, lang: str):
    origin = get_airport_code(intent.get("origin", "Cotonou")) or "COO"
    destination = get_airport_code(intent["destination"]) or intent["destination"].upper()[:3]
    date = intent["departure_date"]
    passengers = intent.get("passengers", 1)
    
    msg = f"🔍 Recherche de vols {get_city_name(origin)} → {get_city_name(destination)}..." if lang == "fr" else f"🔍 Searching flights {get_city_name(origin)} → {get_city_name(destination)}..."
    await send_whatsapp_message(phone, msg)
    
    flights = await search_amadeus_flights(origin, destination, date, passengers)
    
    if not flights:
        await clear_session(phone)
        msg = "😔 Recherche indisponible, réessayez." if lang == "fr" else "😔 Search unavailable, please try again."
        await send_whatsapp_message(phone, msg)
        return
    
    categorized = categorize_flights(flights)
    
    if not categorized:
        await clear_session(phone)
        msg = "😔 Aucun vol trouvé." if lang == "fr" else "😔 No flights found."
        await send_whatsapp_message(phone, msg)
        return
    
    flights_with_cat = list(categorized.values())
    
    await update_session(phone, {
        "state": ConversationState.AWAITING_FLIGHT_SELECTION,
        "intent": intent,
        "flights": flights_with_cat
    })
    
    await send_whatsapp_message(phone, format_flight_options_message(categorized, origin, destination, date))


async def poll_and_complete_payment(phone: str, booking_id: str, booking_ref: str, operator: str, reference_id: str, lang: str):
    """Poll mobile money payment and complete booking on success"""
    status = await payment_service.poll_status(operator, reference_id, max_attempts=10)
    
    if status == "SUCCESSFUL":
        # Get booking
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            return
        
        # Update booking status
        await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "confirmed"}})
        
        # Send success message
        await send_whatsapp_message(phone, format_payment_success(lang))
        
        # Generate ticket
        ticket_filename = generate_ticket_pdf(booking)
        
        # Send ticket
        await asyncio.sleep(2)
        await send_whatsapp_document(
            phone,
            f"{APP_BASE_URL}/api/tickets/{ticket_filename}",
            ticket_filename,
            format_booking_confirmed(booking, lang)
        )
        
        await clear_session(phone)
    else:
        # Payment failed or timed out
        await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "payment_failed"}})
        await send_whatsapp_message(phone, format_payment_failed(operator, lang))
        await send_whatsapp_message(phone, format_retry_options(operator, lang))
        await update_session(phone, {"state": "retry"})


async def complete_card_payment(booking_id: str, stripe_intent_id: str):
    """Called by Stripe webhook on successful card payment"""
    # Find booking by payment intent
    payment_intent = await db.payment_intents.find_one({"stripe_intent_id": stripe_intent_id}, {"_id": 0})
    if not payment_intent:
        logger.error(f"Payment intent not found: {stripe_intent_id}")
        return
    
    booking_id = payment_intent.get("booking_id")
    booking = await db.bookings.find_one({"booking_ref": booking_id}, {"_id": 0})
    if not booking:
        # Try by id
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    
    if not booking:
        logger.error(f"Booking not found for intent: {stripe_intent_id}")
        return
    
    phone = booking.get("phone")
    lang = "fr"  # Default to French
    
    # Get session for language
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    if session:
        lang = session.get("language", "fr")
    
    # Update booking
    await db.bookings.update_one({"id": booking["id"]}, {"$set": {"status": "confirmed"}})
    
    # Send success message
    await send_whatsapp_message(phone, format_payment_success(lang))
    
    # Generate and send ticket
    ticket_filename = generate_ticket_pdf(booking)
    await asyncio.sleep(2)
    await send_whatsapp_document(
        phone,
        f"{APP_BASE_URL}/api/tickets/{ticket_filename}",
        ticket_filename,
        format_booking_confirmed(booking, lang)
    )
    
    await clear_session(phone)


# ========== API ROUTES ==========

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

@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Stripe payment webhooks"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    
    try:
        if webhook_secret and webhook_secret != 'your_webhook_secret_here':
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    if event.get("type") == "payment_intent.succeeded":
        intent = event.get("data", {}).get("object", {})
        intent_id = intent.get("id")
        logger.info(f"Payment succeeded: {intent_id}")
        background_tasks.add_task(complete_card_payment, intent.get("metadata", {}).get("booking_id"), intent_id)
    
    return {"received": True}

@api_router.post("/momo/callback")
async def momo_callback(request: Request):
    """Handle MTN MoMo callbacks"""
    body = await request.json()
    logger.info(f"MoMo callback: {body}")
    return {"received": True}

@api_router.post("/moov/callback")
async def moov_callback(request: Request):
    """Handle Moov Money callbacks"""
    body = await request.json()
    logger.info(f"Moov callback: {body}")
    return {"received": True}

@api_router.get("/")
async def root():
    return {"message": "Travelio WhatsApp Agent", "version": "5.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "type": "whatsapp_agent", "version": "5.0.0", "payment_operators": ["mtn_momo", "moov_money", "google_pay", "apple_pay"]}

@api_router.get("/tickets/{filename}")
async def get_ticket(filename: str):
    filepath = TICKETS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Ticket not found")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)

@api_router.get("/pay/{booking_ref}")
async def payment_page(booking_ref: str, sim: int = 0):
    """Stripe payment page for Google Pay / Apple Pay"""
    publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    
    # Get payment intent
    intent = await db.payment_intents.find_one({"booking_id": booking_ref}, {"_id": 0})
    
    if not intent and sim:
        # Simulation mode
        client_secret = "sim_secret"
        amount = 100
    elif intent:
        client_secret = intent.get("client_secret", "")
        amount = intent.get("amount_eur", 0)
    else:
        return HTMLResponse("<html><body><h1>Payment not found</h1></body></html>", status_code=404)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Travelio Payment</title>
    <script src="https://js.stripe.com/v3/"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0A0F1E; color: #F8FAFC; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ max-width: 400px; width: 100%; }}
        .logo {{ text-align: center; font-size: 28px; font-weight: bold; background: linear-gradient(135deg, #6C63FF, #00D4FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }}
        .subtitle {{ text-align: center; color: #94A3B8; margin-bottom: 24px; }}
        .card {{ background: #111827; border-radius: 16px; padding: 24px; border: 1px solid rgba(255,255,255,0.08); }}
        .amount {{ text-align: center; font-size: 32px; font-weight: bold; color: #00D4FF; margin-bottom: 8px; }}
        .booking-ref {{ text-align: center; color: #94A3B8; font-size: 14px; margin-bottom: 24px; }}
        #payment-element {{ margin-bottom: 24px; }}
        button {{ width: 100%; padding: 16px; border: none; border-radius: 100px; background: linear-gradient(135deg, #6C63FF, #00D4FF); color: white; font-size: 16px; font-weight: 600; cursor: pointer; }}
        button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .error {{ color: #FF4D6D; text-align: center; margin-top: 16px; font-size: 14px; }}
        .success {{ text-align: center; padding: 40px 20px; }}
        .success-icon {{ font-size: 64px; margin-bottom: 16px; }}
        .success h2 {{ color: #00E5A0; margin-bottom: 8px; }}
        .success p {{ color: #94A3B8; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">✈️ Travelio</div>
        <div class="subtitle">Paiement sécurisé</div>
        
        <div class="card" id="payment-form">
            <div class="amount">{amount}€</div>
            <div class="booking-ref">Réservation : {booking_ref}</div>
            <div id="payment-element"></div>
            <button id="submit" type="button">Payer maintenant</button>
            <div id="error-message" class="error"></div>
        </div>
        
        <div class="success" id="success" style="display: none;">
            <div class="success-icon">✅</div>
            <h2>Paiement réussi !</h2>
            <p>Votre billet est en cours de génération.<br>Vous le recevrez sur WhatsApp.</p>
        </div>
    </div>
    
    <script>
        const stripe = Stripe('{publishable_key}');
        const clientSecret = '{client_secret}';
        
        if (clientSecret && clientSecret !== 'sim_secret') {{
            const elements = stripe.elements({{ clientSecret }});
            const paymentElement = elements.create('payment', {{
                wallets: {{ applePay: 'auto', googlePay: 'auto' }}
            }});
            paymentElement.mount('#payment-element');
            
            document.getElementById('submit').addEventListener('click', async () => {{
                const btn = document.getElementById('submit');
                btn.disabled = true;
                btn.textContent = 'Traitement...';
                
                const {{ error }} = await stripe.confirmPayment({{
                    elements,
                    confirmParams: {{ return_url: window.location.href }},
                    redirect: 'if_required'
                }});
                
                if (error) {{
                    document.getElementById('error-message').textContent = error.message;
                    btn.disabled = false;
                    btn.textContent = 'Payer maintenant';
                }} else {{
                    document.getElementById('payment-form').style.display = 'none';
                    document.getElementById('success').style.display = 'block';
                }}
            }});
        }} else {{
            // Simulation mode
            document.getElementById('submit').addEventListener('click', () => {{
                document.getElementById('payment-form').style.display = 'none';
                document.getElementById('success').style.display = 'block';
            }});
        }}
    </script>
</body>
</html>
"""
    return HTMLResponse(html)

@api_router.post("/test/message")
async def test_message(phone: str, message: str):
    await handle_message(phone, message, None)
    session = await db.sessions.find_one({"phone": phone}, {"_id": 0})
    return {"status": "processed", "session": session}

@api_router.get("/test/flights")
async def test_flights(origin: str = "COO", destination: str = "CDG", date: str = None):
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
