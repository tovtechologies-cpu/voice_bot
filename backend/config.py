import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

# App
APP_BASE_URL = os.environ.get('APP_BASE_URL')
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

# WhatsApp
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'travelio_verify_2024')

# AI
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Duffel
DUFFEL_API_KEY = os.environ.get('DUFFEL_API_KEY', '')
DUFFEL_ENV = os.environ.get('DUFFEL_ENV', 'sandbox')

def is_duffel_sandbox():
    return 'placeholder' in DUFFEL_API_KEY or DUFFEL_ENV == 'sandbox'

# Stripe
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# MoMo
MOMO_SUBSCRIPTION_KEY = os.environ.get('MOMO_SUBSCRIPTION_KEY', '')
MOMO_API_USER = os.environ.get('MOMO_API_USER', '')
MOMO_API_KEY = os.environ.get('MOMO_API_KEY', '')
MOMO_BASE_URL = os.environ.get('MOMO_BASE_URL', 'https://sandbox.momodeveloper.mtn.com')
MOMO_ENVIRONMENT = os.environ.get('MOMO_ENVIRONMENT', 'sandbox')
MOMO_CURRENCY = os.environ.get('MOMO_CURRENCY', 'XOF')

# Moov
MOOV_API_KEY = os.environ.get('MOOV_API_KEY', '')
MOOV_BASE_URL = os.environ.get('MOOV_BASE_URL', 'https://api.moov-africa.bj')

# Google Pay / Apple Pay
GOOGLE_PAY_MERCHANT_ID = os.environ.get('GOOGLE_PAY_MERCHANT_ID', '')
GOOGLE_PAY_ENVIRONMENT = os.environ.get('GOOGLE_PAY_ENVIRONMENT', 'TEST')
APPLE_PAY_DOMAIN = os.environ.get('APPLE_PAY_DOMAIN', '')

# Security / Encryption
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', '')

# Constants
API_TIMEOUT = 10.0
EUR_TO_XOF = 655.957
TRAVELIO_FEE = 15.0
SESSION_TIMEOUT_MINUTES = 30
MAX_THIRD_PARTY_PROFILES = 5
WHATSAPP_MSG_LIMIT = 900

# Directories
TICKETS_DIR = ROOT_DIR / 'tickets'
TICKETS_DIR.mkdir(exist_ok=True)

# Extended airport codes database
AIRPORT_CODES = {
    "dakar": "DSS", "lagos": "LOS", "accra": "ACC", "abidjan": "ABJ",
    "ouagadougou": "OUA", "bamako": "BKO", "conakry": "CKY", "niamey": "NIM",
    "cotonou": "COO", "lome": "LFW", "paris": "CDG", "london": "LHR",
    "casablanca": "CMN", "addis ababa": "ADD", "nairobi": "NBO", "dubai": "DXB",
    "new york": "JFK", "douala": "DLA", "libreville": "LBV", "bruxelles": "BRU",
    "brussels": "BRU", "istanbul": "IST", "rome": "FCO", "madrid": "MAD",
    "amsterdam": "AMS", "lisbon": "LIS", "lisbonne": "LIS", "tunis": "TUN",
    "alger": "ALG", "algiers": "ALG", "johannesburg": "JNB", "le caire": "CAI",
    "cairo": "CAI", "marrakech": "RAK", "kinshasa": "FIH", "dakar": "DSS",
    "abuja": "ABV", "dar es salaam": "DAR", "maputo": "MPM", "luanda": "LAD",
    "yaounde": "NSI", "freetown": "FNA", "banjul": "BJL", "nouakchott": "NKC",
    "porto-novo": "COO", "parakou": "PKO", "ndjamena": "NDJ", "tripoli": "TIP",
    "antananarivo": "TNR", "kampala": "EBB", "kigali": "KGL", "lusaka": "LUN",
    "harare": "HRE", "windhoek": "WDH", "gaborone": "GBE", "dakar": "DSS",
    "marseille": "MRS", "lyon": "LYS", "nice": "NCE", "toulouse": "TLS",
    "bordeaux": "BOD", "nantes": "NTE", "strasbourg": "SXB", "lille": "LIL",
    "montreal": "YUL", "toronto": "YYZ", "washington": "IAD", "los angeles": "LAX",
    "miami": "MIA", "chicago": "ORD", "atlanta": "ATL", "houston": "IAH",
    "sao paulo": "GRU", "rio de janeiro": "GIG", "mexico": "MEX",
    "doha": "DOH", "abu dhabi": "AUH", "riyadh": "RUH", "jeddah": "JED",
    "bangkok": "BKK", "singapore": "SIN", "singapour": "SIN",
    "tokyo": "NRT", "pekin": "PEK", "beijing": "PEK", "shanghai": "PVG",
    "mumbai": "BOM", "delhi": "DEL", "hong kong": "HKG",
    "sydney": "SYD", "melbourne": "MEL", "auckland": "AKL",
    "londres": "LHR", "geneve": "GVA", "geneva": "GVA", "zurich": "ZRH",
    "berlin": "BER", "francfort": "FRA", "frankfurt": "FRA",
    "munich": "MUC", "vienne": "VIE", "vienna": "VIE", "milan": "MXP",
    "barcelone": "BCN", "barcelona": "BCN",
}
CODE_TO_CITY = {v: k.title() for k, v in AIRPORT_CODES.items()}

AIRLINES = [
    ("Air France", "AF"), ("Ethiopian Airlines", "ET"),
    ("Royal Air Maroc", "AT"), ("Brussels Airlines", "SN"),
    ("Turkish Airlines", "TK"), ("Kenya Airways", "KQ"),
    ("ASKY Airlines", "KP"), ("Air Cote d'Ivoire", "HF"),
]
