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
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'travelioo_verify_2024')
WHATSAPP_WEBHOOK_SECRET = os.environ.get('WHATSAPP_WEBHOOK_SECRET', '')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v18.0')
WHATSAPP_BASE_URL = os.environ.get('WHATSAPP_BASE_URL', 'https://graph.facebook.com')
WHATSAPP_BUSINESS_PHONE = os.environ.get('WHATSAPP_BUSINESS_PHONE', '')
WHATSAPP_COUNTRY = os.environ.get('WHATSAPP_COUNTRY', 'BJ')
WHATSAPP_COUNTRY_CODE = os.environ.get('WHATSAPP_COUNTRY_CODE', '229')

# AI
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Duffel
DUFFEL_API_KEY = os.environ.get('DUFFEL_API_KEY', '')
DUFFEL_ENV = os.environ.get('DUFFEL_ENV', 'sandbox')

def get_duffel_mode() -> str:
    """Detect Duffel mode: PRODUCTION, SANDBOX, or MOCK."""
    if DUFFEL_API_KEY.startswith("duffel_live_"):
        return "PRODUCTION"
    elif DUFFEL_API_KEY.startswith("duffel_test_"):
        return "SANDBOX"
    elif DUFFEL_API_KEY and 'placeholder' not in DUFFEL_API_KEY and DUFFEL_ENV == 'production':
        return "PRODUCTION"
    elif DUFFEL_API_KEY and 'placeholder' not in DUFFEL_API_KEY:
        return "SANDBOX"
    else:
        return "MOCK"

def is_duffel_sandbox():
    return get_duffel_mode() != "PRODUCTION"

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


def get_momo_mode() -> str:
    """Detect MTN MoMo mode: PRODUCTION, SANDBOX, or MOCK."""
    has_keys = all([MOMO_SUBSCRIPTION_KEY, MOMO_API_USER, MOMO_API_KEY]) and MOMO_API_USER != 'your_uuid_here'
    if not has_keys:
        return "MOCK"
    if MOMO_ENVIRONMENT == "production" and "proxy.momoapi.mtn.com" in MOMO_BASE_URL:
        return "PRODUCTION"
    return "SANDBOX"


def get_moov_mode() -> str:
    """Detect Moov Money mode: PRODUCTION or MOCK."""
    if MOOV_API_KEY and MOOV_API_KEY != 'your_key_here':
        return "PRODUCTION"
    return "MOCK"


def get_stripe_mode() -> str:
    """Detect Stripe mode: LIVE, TEST, or MOCK."""
    if STRIPE_SECRET_KEY.startswith("sk_live_"):
        return "LIVE"
    elif STRIPE_SECRET_KEY.startswith("sk_test_"):
        return "TEST"
    elif STRIPE_SECRET_KEY and STRIPE_SECRET_KEY != 'your_stripe_secret_key_here':
        return "TEST"
    return "MOCK"

# Constants
API_TIMEOUT = 10.0
EUR_TO_XOF = 655.957
TRAVELIOO_FEE = 15.0
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
