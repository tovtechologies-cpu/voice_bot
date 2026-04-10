from fastapi import FastAPI, APIRouter, HTTPException
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
    user_id: str
    flight_id: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: float
    currency: str = "XOF"
    passengers: int
    status: str = "confirmed"
    payment_method: str
    payment_status: str = "completed"
    qr_code: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BookingCreate(BaseModel):
    user_id: str
    flight_id: str
    passengers: int = 1
    payment_method: str = "momo"

class PaymentRequest(BaseModel):
    booking_id: str
    amount: float
    currency: str = "XOF"
    phone_number: str
    payment_method: str = "momo"

class WhatsAppRequest(BaseModel):
    phone_number: str
    booking_id: str

# ========== MOCK DATA GENERATORS ==========

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

AIRLINES = [
    {"name": "Air Senegal", "code": "HC"},
    {"name": "ASKY Airlines", "code": "KP"},
    {"name": "Royal Air Maroc", "code": "AT"},
    {"name": "Ethiopian Airlines", "code": "ET"},
    {"name": "Air Côte d'Ivoire", "code": "HF"}
]

def generate_mock_flights(origin: str, destination: str, date: str, budget: Optional[float] = None) -> List[Flight]:
    """Generate 3 mock flight options: ECO, FAST, PREMIUM"""
    flights = []
    
    origin_code = WEST_AFRICAN_CITIES.get(origin, "DSS")
    dest_code = WEST_AFRICAN_CITIES.get(destination, "ABJ")
    
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
        
        flight = Flight(
            airline=airline["name"],
            flight_number=f"{airline['code']}{random.randint(100, 999)}",
            origin=origin_code,
            destination=dest_code,
            departure_time=f"{date}T{random.randint(6, 18):02d}:00:00",
            arrival_time=f"{date}T{random.randint(10, 22):02d}:00:00",
            duration=tier_info["duration"],
            price=price,
            tier=tier_info["tier"],
            stops=tier_info["stops"],
            available_seats=random.randint(5, 50)
        )
        flights.append(flight)
    
    return flights

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
        
        import json
        try:
            # Clean the response
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
    text_lower = text.lower()
    
    # Detect destination
    destination = None
    for city in WEST_AFRICAN_CITIES.keys():
        if city.lower() in text_lower:
            destination = city
            break
    
    # Simple budget extraction
    budget = None
    import re
    budget_match = re.search(r'(\d+)\s*(dollars?|\$|usd|xof|fcfa)', text_lower)
    if budget_match:
        amount = int(budget_match.group(1))
        currency = budget_match.group(2)
        if currency in ['dollars', '$', 'usd', 'dollar']:
            budget = amount * 600  # Convert to XOF
        else:
            budget = amount
    
    # Default dates
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
    return {"message": "Travelio API", "version": "1.0.0"}

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
    """Search for available flights (mock data)"""
    flights = generate_mock_flights(
        origin=request.origin,
        destination=request.destination,
        date=request.departure_date,
        budget=request.budget
    )
    return flights

@api_router.get("/flights/{flight_id}", response_model=Flight)
async def get_flight(flight_id: str):
    """Get flight details by ID"""
    # In a real app, this would fetch from DB/API
    # For mock, generate a sample
    return Flight(
        id=flight_id,
        airline="Air Senegal",
        flight_number="HC123",
        origin="DSS",
        destination="ABJ",
        departure_time="2024-01-15T08:00:00",
        arrival_time="2024-01-15T10:15:00",
        duration="2h 15m",
        price=75000,
        tier="FAST",
        stops=0,
        available_seats=25
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
@api_router.post("/bookings", response_model=Booking)
async def create_booking(request: BookingCreate):
    """Create a new booking"""
    # Generate mock flight details
    flight = await get_flight(request.flight_id)
    
    booking = Booking(
        user_id=request.user_id,
        flight_id=request.flight_id,
        airline=flight.airline,
        flight_number=flight.flight_number,
        origin=flight.origin,
        destination=flight.destination,
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        price=flight.price * request.passengers,
        passengers=request.passengers,
        payment_method=request.payment_method,
        qr_code=f"TRAVELIO-{uuid.uuid4().hex[:8].upper()}"
    )
    
    doc = booking.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bookings.insert_one(doc)
    
    return booking

@api_router.get("/bookings/user/{user_id}", response_model=List[Booking])
async def get_user_bookings(user_id: str):
    """Get all bookings for a user"""
    bookings = await db.bookings.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    for booking in bookings:
        if isinstance(booking.get('created_at'), str):
            booking['created_at'] = datetime.fromisoformat(booking['created_at'])
    return bookings

@api_router.get("/bookings/{booking_id}", response_model=Booking)
async def get_booking(booking_id: str):
    """Get booking details by ID"""
    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if isinstance(booking.get('created_at'), str):
        booking['created_at'] = datetime.fromisoformat(booking['created_at'])
    return Booking(**booking)

# Payments (Mock)
@api_router.post("/payments/momo")
async def process_momo_payment(request: PaymentRequest):
    """Process MTN MoMo payment (simulated)"""
    # Simulate payment processing
    await asyncio.sleep(1)  # Simulate network delay
    
    success = random.random() > 0.1  # 90% success rate
    
    if success:
        return {
            "status": "success",
            "transaction_id": f"MOMO-{uuid.uuid4().hex[:12].upper()}",
            "amount": request.amount,
            "currency": request.currency,
            "message": "Paiement réussi" if random.random() > 0.5 else "Payment successful"
        }
    else:
        raise HTTPException(status_code=400, detail="Payment failed. Please try again.")

@api_router.post("/payments/google-pay")
async def process_google_pay(request: PaymentRequest):
    """Process Google Pay payment (simulated)"""
    return {
        "status": "success",
        "transaction_id": f"GPAY-{uuid.uuid4().hex[:12].upper()}",
        "amount": request.amount,
        "currency": request.currency,
        "message": "Payment successful"
    }

@api_router.post("/payments/apple-pay")
async def process_apple_pay(request: PaymentRequest):
    """Process Apple Pay payment (simulated)"""
    return {
        "status": "success",
        "transaction_id": f"APAY-{uuid.uuid4().hex[:12].upper()}",
        "amount": request.amount,
        "currency": request.currency,
        "message": "Payment successful"
    }

# WhatsApp (Mock)
@api_router.post("/whatsapp/send-ticket")
async def send_whatsapp_ticket(request: WhatsAppRequest):
    """Send ticket via WhatsApp (simulated)"""
    booking = await db.bookings.find_one({"id": request.booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "status": "sent",
        "phone_number": request.phone_number,
        "message": f"Ticket sent to {request.phone_number} via WhatsApp (simulated)",
        "booking_ref": booking.get("qr_code", "N/A")
    }

# Cities endpoint for autocomplete
@api_router.get("/cities")
async def get_cities():
    """Get list of supported West African cities"""
    return [{"name": city, "code": code} for city, code in WEST_AFRICAN_CITIES.items()]

# Import asyncio for sleep
import asyncio

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
