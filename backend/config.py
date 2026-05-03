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

# Telegram (stub — token provided in Phase B)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')

# Celtiis Cash
CELTIIS_API_KEY = os.environ.get('CELTIIS_API_KEY', '')
CELTIIS_API_URL = os.environ.get('CELTIIS_API_URL', 'https://api.celtiis.bj')

# IP Geolocation
IPINFO_API_KEY = os.environ.get('IPINFO_API_KEY', '')

# Human-in-the-loop
HUMAN_REVIEW_WEBHOOK = os.environ.get('HUMAN_REVIEW_WEBHOOK', '')

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
SESSION_TIMEOUT_MINUTES = 30
MAX_THIRD_PARTY_PROFILES = 5
WHATSAPP_MSG_LIMIT = 900
SPLIT_PAYMENT_RECONCILIATION_FEE_EUR = 2.0
SPLIT_PAYMENT_RECONCILIATION_FEE_XOF = 1300
PRICE_LOCK_MINUTES = 10

# CFA zone countries (fixed rate 1 EUR = 655.957 XOF)
CFA_COUNTRIES = {"BJ", "TG", "SN", "CI", "ML", "BF", "NE", "GW", "CM", "CF", "TD", "CG", "GA", "GQ"}
UEMOA_COUNTRIES = {"BJ", "TG", "SN", "CI", "ML", "BF", "NE", "GW"}
SADC_COUNTRIES = {"ZA", "BW", "MZ", "ZW", "ZM", "MW", "AO", "NA", "TZ", "CD"}

# Directories
TICKETS_DIR = ROOT_DIR / 'tickets'
TICKETS_DIR.mkdir(exist_ok=True)

# Extended airport codes database.
# NOTE: list each city->code once; Porto-Novo uses COO (same airport as Cotonou) but must not override the reverse mapping.
AIRPORT_CODES = {
    # West Africa
    "cotonou": "COO", "porto-novo": "COO", "porto novo": "COO", "parakou": "PKO",
    "lome": "LFW", "lomé": "LFW",
    "dakar": "DSS", "abidjan": "ABJ", "accra": "ACC", "lagos": "LOS", "abuja": "ABV",
    "ouagadougou": "OUA", "bamako": "BKO", "conakry": "CKY", "niamey": "NIM",
    "nouakchott": "NKC", "banjul": "BJL", "freetown": "FNA",
    # Central Africa
    "douala": "DLA", "yaounde": "NSI", "libreville": "LBV", "kinshasa": "FIH",
    "ndjamena": "NDJ",
    # North Africa
    "casablanca": "CMN", "marrakech": "RAK", "rabat": "RBA",
    "tunis": "TUN", "alger": "ALG", "algiers": "ALG",
    "tripoli": "TIP", "le caire": "CAI", "cairo": "CAI",
    # East / South Africa
    "addis ababa": "ADD", "nairobi": "NBO", "dar es salaam": "DAR",
    "kampala": "EBB", "kigali": "KGL", "antananarivo": "TNR",
    "johannesburg": "JNB", "luanda": "LAD", "maputo": "MPM", "lusaka": "LUN",
    "harare": "HRE", "windhoek": "WDH", "gaborone": "GBE",
    # Europe
    "paris": "CDG", "marseille": "MRS", "lyon": "LYS", "nice": "NCE",
    "toulouse": "TLS", "bordeaux": "BOD", "nantes": "NTE", "strasbourg": "SXB", "lille": "LIL",
    "london": "LHR", "londres": "LHR",
    "bruxelles": "BRU", "brussels": "BRU",
    "amsterdam": "AMS", "madrid": "MAD", "barcelone": "BCN", "barcelona": "BCN",
    "lisbon": "LIS", "lisbonne": "LIS",
    "rome": "FCO", "milan": "MXP",
    "berlin": "BER", "francfort": "FRA", "frankfurt": "FRA", "munich": "MUC",
    "vienne": "VIE", "vienna": "VIE",
    "geneve": "GVA", "geneva": "GVA", "zurich": "ZRH",
    "istanbul": "IST",
    # Middle East / Asia
    "dubai": "DXB", "doha": "DOH", "abu dhabi": "AUH",
    "riyadh": "RUH", "jeddah": "JED",
    "bangkok": "BKK", "singapore": "SIN", "singapour": "SIN",
    "tokyo": "NRT", "pekin": "PEK", "beijing": "PEK", "shanghai": "PVG",
    "mumbai": "BOM", "delhi": "DEL", "hong kong": "HKG",
    # Americas
    "new york": "JFK", "washington": "IAD", "los angeles": "LAX",
    "miami": "MIA", "chicago": "ORD", "atlanta": "ATL", "houston": "IAH",
    "montreal": "YUL", "toronto": "YYZ",
    "sao paulo": "GRU", "rio de janeiro": "GIG", "mexico": "MEX",
    # Oceania
    "sydney": "SYD", "melbourne": "MEL", "auckland": "AKL",
}

# Explicit primary-city display name per IATA code (prevents "Cotonou -> Porto-Novo" bug from alias order).
CODE_TO_CITY = {
    "COO": "Cotonou", "PKO": "Parakou", "LFW": "Lomé",
    "DSS": "Dakar", "ABJ": "Abidjan", "ACC": "Accra", "LOS": "Lagos", "ABV": "Abuja",
    "OUA": "Ouagadougou", "BKO": "Bamako", "CKY": "Conakry", "NIM": "Niamey",
    "NKC": "Nouakchott", "BJL": "Banjul", "FNA": "Freetown",
    "DLA": "Douala", "NSI": "Yaoundé", "LBV": "Libreville", "FIH": "Kinshasa", "NDJ": "N'Djamena",
    "CMN": "Casablanca", "RAK": "Marrakech", "RBA": "Rabat",
    "TUN": "Tunis", "ALG": "Alger", "TIP": "Tripoli", "CAI": "Le Caire",
    "ADD": "Addis-Abeba", "NBO": "Nairobi", "DAR": "Dar es Salaam",
    "EBB": "Kampala", "KGL": "Kigali", "TNR": "Antananarivo",
    "JNB": "Johannesburg", "LAD": "Luanda", "MPM": "Maputo", "LUN": "Lusaka",
    "HRE": "Harare", "WDH": "Windhoek", "GBE": "Gaborone",
    "CDG": "Paris", "MRS": "Marseille", "LYS": "Lyon", "NCE": "Nice",
    "TLS": "Toulouse", "BOD": "Bordeaux", "NTE": "Nantes", "SXB": "Strasbourg", "LIL": "Lille",
    "LHR": "Londres", "BRU": "Bruxelles", "AMS": "Amsterdam", "MAD": "Madrid",
    "BCN": "Barcelone", "LIS": "Lisbonne", "FCO": "Rome", "MXP": "Milan",
    "BER": "Berlin", "FRA": "Francfort", "MUC": "Munich", "VIE": "Vienne",
    "GVA": "Genève", "ZRH": "Zurich", "IST": "Istanbul",
    "DXB": "Dubaï", "DOH": "Doha", "AUH": "Abu Dhabi", "RUH": "Riyadh", "JED": "Jeddah",
    "BKK": "Bangkok", "SIN": "Singapour",
    "NRT": "Tokyo", "PEK": "Pékin", "PVG": "Shanghai",
    "BOM": "Mumbai", "DEL": "Delhi", "HKG": "Hong Kong",
    "JFK": "New York", "IAD": "Washington", "LAX": "Los Angeles",
    "MIA": "Miami", "ORD": "Chicago", "ATL": "Atlanta", "IAH": "Houston",
    "YUL": "Montréal", "YYZ": "Toronto",
    "GRU": "São Paulo", "GIG": "Rio de Janeiro", "MEX": "Mexico",
    "SYD": "Sydney", "MEL": "Melbourne", "AKL": "Auckland",
}

AIRLINES = [
    ("Air France", "AF"), ("Ethiopian Airlines", "ET"),
    ("Royal Air Maroc", "AT"), ("Brussels Airlines", "SN"),
    ("Turkish Airlines", "TK"), ("Kenya Airways", "KQ"),
    ("ASKY Airlines", "KP"), ("Air Cote d'Ivoire", "HF"),
]
