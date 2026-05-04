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

# Extended airport codes database — curated global list.
# Porto-Novo intentionally omitted (no real airport; flights served from Cotonou / COO).
AIRPORT_CODES = {

    # ════════════════════════════════════════════════════════════════
    #  AFRIQUE DE L'OUEST
    # ════════════════════════════════════════════════════════════════

    # Bénin
    "cotonou": "COO",
    "parakou": "PKO",

    # Togo
    "lome": "LFW",          "lomé": "LFW",

    # Sénégal
    "dakar": "DSS",
    "ziguinchor": "ZIG",
    "saint-louis": "XLS",

    # Côte d'Ivoire
    "abidjan": "ABJ",
    "yamoussoukro": "ASK",
    "bouake": "BYK",        "bouaké": "BYK",
    "san pedro": "SPY",     "san-pedro": "SPY",

    # Ghana
    "accra": "ACC",
    "kumasi": "KMS",
    "tamale": "TML",

    # Nigeria
    "lagos": "LOS",
    "abuja": "ABV",
    "kano": "KAN",
    "port harcourt": "PHC",
    "enugu": "ENU",
    "calabar": "CBQ",
    "benin city": "BNI",
    "maiduguri": "MIU",
    "sokoto": "SKO",
    "kaduna": "KAD",

    # Burkina Faso
    "ouagadougou": "OUA",
    "bobo-dioulasso": "BOY", "bobo dioulasso": "BOY",

    # Mali
    "bamako": "BKO",
    "mopti": "MZI",
    "gao": "GAQ",
    "tombouctou": "TOM",    "timbuktu": "TOM",

    # Guinée
    "conakry": "CKY",
    "labe": "LEK",          "labé": "LEK",

    # Guinée-Bissau
    "bissau": "OXB",

    # Liberia
    "monrovia": "ROB",

    # Sierra Leone
    "freetown": "FNA",

    # Niger
    "niamey": "NIM",
    "zinder": "ZND",
    "agadez": "AJY",
    "maradi": "MFQ",
    "tahoua": "THZ",

    # Mauritanie
    "nouakchott": "NKC",
    "nouadhibou": "NDB",
    "atar": "ATR",

    # Gambie
    "banjul": "BJL",

    # Cabo Verde
    "praia": "RAI",
    "sal": "SID",
    "sao vicente": "VXE",   "são vicente": "VXE",

    # ════════════════════════════════════════════════════════════════
    #  AFRIQUE CENTRALE
    # ════════════════════════════════════════════════════════════════

    # Cameroun
    "douala": "DLA",
    "yaounde": "NSI",       "yaoundé": "NSI",
    "garoua": "GOU",
    "maroua": "MVR",
    "bafoussam": "BFX",

    # Gabon
    "libreville": "LBV",
    "port-gentil": "POG",   "port gentil": "POG",

    # Congo
    "brazzaville": "BZV",
    "pointe-noire": "PNR",  "pointe noire": "PNR",

    # République Centrafricaine
    "bangui": "BGF",

    # Guinée Équatoriale
    "malabo": "SSG",
    "bata": "BSG",

    # Sao Tomé-et-Principe
    "sao tome": "TMS",      "são tomé": "TMS",

    # RDC
    "kinshasa": "FIH",
    "lubumbashi": "FBM",
    "goma": "GOM",
    "kisangani": "FKI",
    "mbuji-mayi": "MJM",    "mbuji mayi": "MJM",

    # Tchad
    "ndjamena": "NDJ",
    "moundou": "MQQ",

    # ════════════════════════════════════════════════════════════════
    #  AFRIQUE DU NORD
    # ════════════════════════════════════════════════════════════════

    # Maroc
    "casablanca": "CMN",
    "marrakech": "RAK",     "marrakesh": "RAK",
    "rabat": "RBA",
    "agadir": "AGA",
    "fes": "FEZ",           "fès": "FEZ",           "fez": "FEZ",
    "tanger": "TNG",        "tangier": "TNG",
    "oujda": "OUD",
    "laayoune": "EUN",
    "nador": "NDR",

    # Algérie
    "alger": "ALG",         "algiers": "ALG",
    "oran": "ORN",
    "constantine": "CZL",
    "annaba": "AAE",
    "tlemcen": "TLM",

    # Tunisie
    "tunis": "TUN",
    "djerba": "DJE",
    "monastir": "MIR",
    "sfax": "SFA",
    "tozeur": "TOE",

    # Libye
    "tripoli": "TIP",
    "benghazi": "BEN",

    # Égypte
    "le caire": "CAI",      "cairo": "CAI",
    "alexandrie": "HBE",    "alexandria": "HBE",
    "hurghada": "HRG",
    "sharm el-sheikh": "SSH", "sharm el sheikh": "SSH",
    "louxor": "LXR",        "luxor": "LXR",
    "assouan": "ASW",       "aswan": "ASW",

    # Soudan
    "khartoum": "KRT",

    # Érythrée
    "asmara": "ASM",

    # ════════════════════════════════════════════════════════════════
    #  AFRIQUE DE L'EST
    # ════════════════════════════════════════════════════════════════

    # Éthiopie
    "addis ababa": "ADD",   "addis-abeba": "ADD",
    "dire dawa": "DIR",

    # Djibouti
    "djibouti": "JIB",

    # Somalie
    "mogadiscio": "MGQ",    "mogadishu": "MGQ",

    # Soudan du Sud
    "juba": "JUB",

    # Kenya
    "nairobi": "NBO",
    "mombasa": "MBA",
    "kisumu": "KIS",
    "eldoret": "EDL",

    # Tanzanie
    "dar es salaam": "DAR",
    "kilimanjaro": "JRO",
    "zanzibar": "ZNZ",
    "mwanza": "MWZ",

    # Ouganda
    "kampala": "EBB",

    # Rwanda
    "kigali": "KGL",

    # Burundi
    "bujumbura": "BJM",

    # ════════════════════════════════════════════════════════════════
    #  AFRIQUE AUSTRALE & ÎLES
    # ════════════════════════════════════════════════════════════════

    # Madagascar
    "antananarivo": "TNR",
    "nosy be": "NOS",
    "toamasina": "TMM",

    # Île Maurice
    "mauritius": "MRU",     "maurice": "MRU",       "port louis": "MRU",

    # La Réunion
    "la reunion": "RUN",    "la réunion": "RUN",    "saint-denis": "RUN",

    # Comores
    "moroni": "HAH",        "comores": "HAH",

    # Seychelles
    "seychelles": "SEZ",    "mahe": "SEZ",          "mahé": "SEZ",

    # Afrique du Sud
    "johannesburg": "JNB",
    "le cap": "CPT",        "cape town": "CPT",
    "durban": "DUR",
    "port elizabeth": "PLZ",
    "bloemfontein": "BFN",
    "george": "GRJ",

    # Zimbabwe
    "harare": "HRE",
    "bulawayo": "BUQ",
    "victoria falls": "VFA", "chutes victoria": "VFA",

    # Zambie
    "lusaka": "LUN",
    "livingstone": "LVI",
    "ndola": "NLA",

    # Malawi
    "lilongwe": "LLW",
    "blantyre": "BLZ",

    # Botswana
    "gaborone": "GBE",
    "maun": "MUB",

    # Namibie
    "windhoek": "WDH",

    # Angola
    "luanda": "LAD",
    "lubango": "SDD",

    # Mozambique
    "maputo": "MPM",
    "beira": "BEW",
    "nampula": "APL",

    # Eswatini
    "mbabane": "SHO",

    # Lesotho
    "maseru": "MSU",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – FRANCE
    # ════════════════════════════════════════════════════════════════

    "paris": "CDG",
    "paris orly": "ORY",    "orly": "ORY",
    "marseille": "MRS",
    "lyon": "LYS",
    "nice": "NCE",
    "toulouse": "TLS",
    "bordeaux": "BOD",
    "nantes": "NTE",
    "strasbourg": "SXB",
    "lille": "LIL",
    "montpellier": "MPL",
    "rennes": "RNS",
    "brest": "BES",
    "grenoble": "GNB",
    "clermont-ferrand": "CFE",
    "toulon": "TLN",
    "biarritz": "BIQ",
    "pau": "PUF",
    "perpignan": "PGF",
    "limoges": "LIG",
    "caen": "CFR",
    "chambery": "CMF",      "chambéry": "CMF",
    "ajaccio": "AJA",
    "bastia": "BIA",
    "figari": "FSC",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – ÎLES BRITANNIQUES
    # ════════════════════════════════════════════════════════════════

    "london": "LHR",        "londres": "LHR",
    "london gatwick": "LGW", "gatwick": "LGW",
    "london stansted": "STN", "stansted": "STN",
    "london city": "LCY",
    "manchester": "MAN",
    "birmingham": "BHX",
    "edinburgh": "EDI",     "edimbourg": "EDI",
    "glasgow": "GLA",
    "bristol": "BRS",
    "newcastle": "NCL",
    "leeds": "LBA",
    "liverpool": "LPL",
    "dublin": "DUB",
    "cork": "ORK",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – PÉNINSULE IBÉRIQUE
    # ════════════════════════════════════════════════════════════════

    "madrid": "MAD",
    "barcelone": "BCN",     "barcelona": "BCN",
    "palma de majorque": "PMI", "palma": "PMI", "mallorca": "PMI",
    "malaga": "AGP",        "málaga": "AGP",
    "alicante": "ALC",
    "valencia": "VLC",
    "seville": "SVQ",       "séville": "SVQ",       "sevilla": "SVQ",
    "bilbao": "BIO",
    "tenerife": "TFS",
    "las palmas": "LPA",    "gran canaria": "LPA",
    "ibiza": "IBZ",
    "minorque": "MAH",      "menorca": "MAH",
    "fuerteventura": "FUE",
    "lanzarote": "ACE",
    "lisbon": "LIS",        "lisbonne": "LIS",
    "porto": "OPO",
    "faro": "FAO",
    "funchal": "FNC",       "madere": "FNC",        "madeira": "FNC",
    "ponta delgada": "PDL", "acores": "PDL",        "azores": "PDL",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – ITALIE
    # ════════════════════════════════════════════════════════════════

    "rome": "FCO",
    "milan": "MXP",
    "milan linate": "LIN",  "linate": "LIN",
    "venise": "VCE",        "venice": "VCE",        "venezia": "VCE",
    "bologne": "BLQ",       "bologna": "BLQ",
    "florence": "FLR",      "firenze": "FLR",
    "naples": "NAP",        "napoli": "NAP",
    "catane": "CTA",        "catania": "CTA",
    "palerme": "PMO",       "palermo": "PMO",
    "turin": "TRN",         "torino": "TRN",
    "bari": "BRI",
    "genes": "GOA",         "gênes": "GOA",         "genoa": "GOA",
    "cagliari": "CAG",
    "brindisi": "BDS",
    "pise": "PSA",          "pisa": "PSA",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – ALLEMAGNE
    # ════════════════════════════════════════════════════════════════

    "berlin": "BER",
    "francfort": "FRA",     "frankfurt": "FRA",
    "munich": "MUC",
    "hambourg": "HAM",      "hamburg": "HAM",
    "dusseldorf": "DUS",    "düsseldorf": "DUS",
    "cologne": "CGN",       "koeln": "CGN",         "köln": "CGN",
    "stuttgart": "STR",
    "hanovre": "HAJ",       "hanover": "HAJ",       "hannover": "HAJ",
    "nuremberg": "NUE",     "nürnberg": "NUE",
    "leipzig": "LEJ",
    "breme": "BRE",         "brême": "BRE",         "bremen": "BRE",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – BENELUX & SUISSE & AUTRICHE
    # ════════════════════════════════════════════════════════════════

    "bruxelles": "BRU",     "brussels": "BRU",
    "liege": "LGG",         "liège": "LGG",
    "amsterdam": "AMS",
    "eindhoven": "EIN",
    "geneve": "GVA",        "geneva": "GVA",        "genève": "GVA",
    "zurich": "ZRH",
    "bale": "BSL",          "bâle": "BSL",          "basel": "BSL",
    "vienne": "VIE",        "vienna": "VIE",
    "innsbruck": "INN",
    "salzbourg": "SZG",     "salzburg": "SZG",
    "luxembourg": "LUX",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – SCANDINAVIE & PAYS BALTES
    # ════════════════════════════════════════════════════════════════

    "copenhague": "CPH",    "copenhagen": "CPH",
    "stockholm": "ARN",
    "gothenburg": "GOT",    "göteborg": "GOT",
    "oslo": "OSL",
    "bergen": "BGO",
    "trondheim": "TRD",
    "helsinki": "HEL",
    "reykjavik": "KEF",
    "vilnius": "VNO",
    "riga": "RIX",
    "tallinn": "TLL",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – CENTRALE & ORIENTALE
    # ════════════════════════════════════════════════════════════════

    "varsovie": "WAW",      "warsaw": "WAW",
    "cracovie": "KRK",      "krakow": "KRK",        "kraków": "KRK",
    "gdansk": "GDN",        "gdańsk": "GDN",
    "wroclaw": "WRO",       "wrocław": "WRO",
    "prague": "PRG",        "praga": "PRG",
    "budapest": "BUD",
    "bucarest": "OTP",      "bucharest": "OTP",
    "sofia": "SOF",
    "belgrade": "BEG",      "beograd": "BEG",
    "zagreb": "ZAG",
    "split": "SPU",
    "dubrovnik": "DBV",
    "bratislava": "BTS",
    "ljubljana": "LJU",
    "sarajevo": "SJJ",
    "podgorica": "TGD",
    "tirana": "TIA",
    "skopje": "SKP",
    "chisinau": "KIV",      "chișinău": "KIV",
    "minsk": "MSQ",
    "kyiv": "KBP",          "kiev": "KBP",
    "lviv": "LWO",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – MÉDITERRANÉE
    # ════════════════════════════════════════════════════════════════

    "istanbul": "IST",
    "ankara": "ESB",
    "antalya": "AYT",
    "izmir": "ADB",         "smyrne": "ADB",
    "bodrum": "BJV",
    "athenes": "ATH",       "athens": "ATH",        "athènes": "ATH",
    "thessalonique": "SKG", "thessaloniki": "SKG",
    "heraklion": "HER",     "irakleion": "HER",
    "rhodes": "RHO",        "rodos": "RHO",
    "corfou": "CFU",        "corfu": "CFU",
    "mykonos": "JMK",
    "santorin": "JTR",      "santorini": "JTR",
    "malte": "MLA",         "malta": "MLA",
    "larnaca": "LCA",
    "paphos": "PFO",

    # ════════════════════════════════════════════════════════════════
    #  EUROPE – RUSSIE & CAUCASE
    # ════════════════════════════════════════════════════════════════

    "moscou": "SVO",        "moscow": "SVO",
    "moscou domodedovo": "DME", "domodedovo": "DME",
    "saint-petersbourg": "LED", "saint petersburg": "LED", "st petersburg": "LED",
    "novosibirsk": "OVB",
    "iekaterinbourg": "SVX", "yekaterinburg": "SVX",
    "tbilissi": "TBS",      "tbilisi": "TBS",
    "erevan": "EVN",        "yerevan": "EVN",
    "baku": "GYD",          "bakou": "GYD",

    # ════════════════════════════════════════════════════════════════
    #  MOYEN-ORIENT
    # ════════════════════════════════════════════════════════════════

    "dubai": "DXB",         "dubaï": "DXB",
    "doha": "DOH",
    "abu dhabi": "AUH",
    "sharjah": "SHJ",
    "riyadh": "RUH",
    "jeddah": "JED",
    "medine": "MED",        "medina": "MED",
    "dammam": "DMM",
    "muscat": "MCT",
    "salalah": "SLL",
    "bahrain": "BAH",       "bahrein": "BAH",       "manama": "BAH",
    "kuwait": "KWI",        "koweït": "KWI",
    "beyrouth": "BEY",      "beirut": "BEY",
    "amman": "AMM",
    "aqaba": "AQJ",
    "tel aviv": "TLV",
    "bagdad": "BGW",        "baghdad": "BGW",
    "erbil": "EBL",
    "bassora": "BSR",       "basra": "BSR",
    "damas": "DAM",         "damascus": "DAM",
    "sanaa": "SAH",
    "aden": "ADE",
    "teheran": "IKA",       "tehran": "IKA",        "téhéran": "IKA",
    "mashhad": "MHD",
    "isfahan": "IFN",
    "shiraz": "SYZ",

    # ════════════════════════════════════════════════════════════════
    #  ASIE CENTRALE
    # ════════════════════════════════════════════════════════════════

    "almaty": "ALA",        "alma-ata": "ALA",
    "astana": "NQZ",        "nur-sultan": "NQZ",
    "tachkent": "TAS",      "tashkent": "TAS",
    "bichkek": "FRU",       "bishkek": "FRU",
    "douchanbé": "DYU",     "dushanbe": "DYU",
    "achgabat": "ASB",      "ashgabat": "ASB",

    # ════════════════════════════════════════════════════════════════
    #  ASIE DU SUD
    # ════════════════════════════════════════════════════════════════

    "delhi": "DEL",         "new delhi": "DEL",
    "mumbai": "BOM",        "bombay": "BOM",
    "bangalore": "BLR",     "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA",       "madras": "MAA",
    "kolkata": "CCU",       "calcutta": "CCU",
    "kochi": "COK",
    "ahmedabad": "AMD",
    "goa": "GOI",
    "jaipur": "JAI",
    "lucknow": "LKO",
    "amritsar": "ATQ",
    "thiruvananthapuram": "TRV", "trivandrum": "TRV",
    "pune": "PNQ",
    "karachi": "KHI",
    "lahore": "LHE",
    "islamabad": "ISB",
    "dhaka": "DAC",
    "colombo": "CMB",
    "kathmandu": "KTM",     "katmandou": "KTM",
    "male": "MLE",          "malé": "MLE",          "maldives": "MLE",
    "paro": "PBH",          "bhoutan": "PBH",

    # ════════════════════════════════════════════════════════════════
    #  ASIE DU SUD-EST
    # ════════════════════════════════════════════════════════════════

    "bangkok": "BKK",
    "chiang mai": "CNX",
    "phuket": "HKT",
    "krabi": "KBV",
    "hanoi": "HAN",         "hanoï": "HAN",
    "ho chi minh": "SGN",   "saigon": "SGN",        "ho-chi-minh-ville": "SGN",
    "da nang": "DAD",       "danang": "DAD",
    "phnom penh": "PNH",
    "siem reap": "REP",
    "vientiane": "VTE",
    "yangon": "RGN",        "rangoun": "RGN",
    "kuala lumpur": "KUL",
    "penang": "PEN",
    "kota kinabalu": "BKI",
    "kuching": "KCH",
    "singapore": "SIN",     "singapour": "SIN",
    "jakarta": "CGK",
    "bali": "DPS",          "denpasar": "DPS",
    "surabaya": "SUB",
    "medan": "KNO",
    "manille": "MNL",       "manila": "MNL",
    "cebu": "CEB",
    "davao": "DVO",

    # ════════════════════════════════════════════════════════════════
    #  ASIE DE L'EST
    # ════════════════════════════════════════════════════════════════

    "pekin": "PEK",         "beijing": "PEK",       "pékin": "PEK",
    "shanghai": "PVG",
    "shanghai hongqiao": "SHA", "hongqiao": "SHA",
    "guangzhou": "CAN",     "canton": "CAN",
    "shenzhen": "SZX",
    "chengdu": "CTU",
    "chongqing": "CKG",
    "hangzhou": "HGH",
    "kunming": "KMG",
    "xian": "XIY",          "xi'an": "XIY",
    "qingdao": "TAO",
    "xiamen": "XMN",
    "wuhan": "WUH",
    "nanjing": "NKG",
    "zhengzhou": "CGO",
    "tianjin": "TSN",
    "harbin": "HRB",
    "dalian": "DLC",
    "urumqi": "URC",
    "hong kong": "HKG",
    "macao": "MFM",         "macau": "MFM",
    "taipei": "TPE",
    "kaohsiung": "KHH",
    "tokyo": "NRT",         "narita": "NRT",
    "tokyo haneda": "HND",  "haneda": "HND",
    "osaka": "KIX",
    "osaka itami": "ITM",   "itami": "ITM",
    "nagoya": "NGO",
    "fukuoka": "FUK",
    "sapporo": "CTS",
    "okinawa": "OKA",
    "hiroshima": "HIJ",
    "seoul": "ICN",         "séoul": "ICN",
    "seoul gimpo": "GMP",   "gimpo": "GMP",
    "busan": "PUS",
    "jeju": "CJU",
    "ulaanbaatar": "ULN",   "oulan-bator": "ULN",

    # ════════════════════════════════════════════════════════════════
    #  AMÉRIQUES – ÉTATS-UNIS
    # ════════════════════════════════════════════════════════════════

    "new york": "JFK",
    "new york laguardia": "LGA", "laguardia": "LGA",
    "newark": "EWR",
    "los angeles": "LAX",
    "chicago": "ORD",
    "chicago midway": "MDW",
    "dallas": "DFW",
    "houston": "IAH",
    "miami": "MIA",
    "atlanta": "ATL",
    "san francisco": "SFO",
    "seattle": "SEA",
    "washington": "IAD",
    "washington reagan": "DCA", "reagan": "DCA",
    "boston": "BOS",
    "denver": "DEN",
    "phoenix": "PHX",
    "las vegas": "LAS",
    "orlando": "MCO",
    "minneapolis": "MSP",
    "detroit": "DTW",
    "philadelphia": "PHL",
    "charlotte": "CLT",
    "salt lake city": "SLC",
    "portland": "PDX",
    "tampa": "TPA",
    "baltimore": "BWI",
    "san diego": "SAN",
    "honolulu": "HNL",      "hawaii": "HNL",
    "anchorage": "ANC",     "alaska": "ANC",
    "new orleans": "MSY",
    "kansas city": "MCI",
    "nashville": "BNA",
    "austin": "AUS",
    "raleigh": "RDU",
    "pittsburgh": "PIT",

    # ════════════════════════════════════════════════════════════════
    #  AMÉRIQUES – CANADA
    # ════════════════════════════════════════════════════════════════

    "montreal": "YUL",      "montréal": "YUL",
    "toronto": "YYZ",
    "vancouver": "YVR",
    "calgary": "YYC",
    "edmonton": "YEG",
    "ottawa": "YOW",
    "winnipeg": "YWG",
    "quebec city": "YQB",   "québec": "YQB",
    "halifax": "YHZ",

    # ════════════════════════════════════════════════════════════════
    #  AMÉRIQUES – MEXIQUE & AMÉRIQUE CENTRALE
    # ════════════════════════════════════════════════════════════════

    "mexico": "MEX",        "mexico city": "MEX",
    "cancun": "CUN",        "cancún": "CUN",
    "guadalajara": "GDL",
    "monterrey": "MTY",
    "tijuana": "TIJ",
    "puerto vallarta": "PVR",
    "los cabos": "SJD",
    "guatemala city": "GUA", "guatemala": "GUA",
    "tegucigalpa": "TGU",
    "san salvador": "SAL",  "el salvador": "SAL",
    "managua": "MGA",
    "san jose": "SJO",      "costa rica": "SJO",
    "panama city": "PTY",   "panama": "PTY",

    # ════════════════════════════════════════════════════════════════
    #  AMÉRIQUES – CARAÏBES
    # ════════════════════════════════════════════════════════════════

    "havane": "HAV",        "havana": "HAV",
    "nassau": "NAS",
    "punta cana": "PUJ",
    "saint-domingue": "SDQ", "santo domingo": "SDQ",
    "kingston": "KIN",
    "montego bay": "MBJ",
    "san juan": "SJU",      "puerto rico": "SJU",
    "port-au-prince": "PAP", "port au prince": "PAP",
    "bridgetown": "BGI",    "barbade": "BGI",
    "port of spain": "POS", "trinidad": "POS",
    "pointe-a-pitre": "PTP", "guadeloupe": "PTP",
    "fort-de-france": "FDF", "martinique": "FDF",
    "cayenne": "CAY",       "guyane": "CAY",

    # ════════════════════════════════════════════════════════════════
    #  AMÉRIQUES DU SUD
    # ════════════════════════════════════════════════════════════════

    "sao paulo": "GRU",     "são paulo": "GRU",
    "sao paulo congonhas": "CGH", "congonhas": "CGH",
    "rio de janeiro": "GIG",
    "brasilia": "BSB",      "brasília": "BSB",
    "belo horizonte": "CNF",
    "salvador": "SSA",
    "recife": "REC",
    "fortaleza": "FOR",
    "manaus": "MAO",
    "porto alegre": "POA",
    "curitiba": "CWB",
    "belem": "BEL",         "belém": "BEL",
    "natal": "NAT",
    "buenos aires": "EZE",
    "buenos aires aeroparque": "AEP", "aeroparque": "AEP",
    "cordoba": "COR",       "córdoba": "COR",
    "mendoza": "MDZ",
    "bariloche": "BRC",
    "ushuaia": "USH",
    "santiago": "SCL",
    "lima": "LIM",
    "cusco": "CUZ",         "cuzco": "CUZ",
    "bogota": "BOG",        "bogotá": "BOG",
    "medellin": "MDE",      "medellín": "MDE",
    "cali": "CLO",
    "cartagena": "CTG",
    "caracas": "CCS",
    "quito": "UIO",
    "guayaquil": "GYE",
    "la paz": "LPB",
    "santa cruz": "VVI",
    "asuncion": "ASU",      "asunción": "ASU",
    "montevideo": "MVD",
    "paramaribo": "PBM",
    "georgetown": "GEO",

    # ════════════════════════════════════════════════════════════════
    #  OCÉANIE
    # ════════════════════════════════════════════════════════════════

    "sydney": "SYD",
    "melbourne": "MEL",
    "brisbane": "BNE",
    "perth": "PER",
    "adelaide": "ADL",
    "gold coast": "OOL",
    "cairns": "CNS",
    "darwin": "DRW",
    "hobart": "HBA",
    "auckland": "AKL",
    "wellington": "WLG",
    "christchurch": "CHC",
    "queenstown": "ZQN",
    "nadi": "NAN",          "fidji": "NAN",         "fiji": "NAN",
    "port moresby": "POM",  "papouasie": "POM",
    "noumea": "NOU",        "nouméa": "NOU",
    "papeete": "PPT",       "tahiti": "PPT",
    "guam": "GUM",
}

# ════════════════════════════════════════════════════════════════════
#  NOM D'AFFICHAGE PRINCIPAL PAR CODE IATA
# ════════════════════════════════════════════════════════════════════
CODE_TO_CITY = {
    # ── Afrique de l'Ouest
    "COO": "Cotonou",           "PKO": "Parakou",           "LFW": "Lomé",
    "DSS": "Dakar",             "ZIG": "Ziguinchor",        "XLS": "Saint-Louis",
    "ABJ": "Abidjan",           "ASK": "Yamoussoukro",      "BYK": "Bouaké",
    "SPY": "San-Pédro",         "ACC": "Accra",             "KMS": "Kumasi",
    "TML": "Tamale",            "LOS": "Lagos",             "ABV": "Abuja",
    "KAN": "Kano",              "PHC": "Port Harcourt",     "ENU": "Enugu",
    "CBQ": "Calabar",           "BNI": "Benin City",        "MIU": "Maiduguri",
    "SKO": "Sokoto",            "KAD": "Kaduna",            "OUA": "Ouagadougou",
    "BOY": "Bobo-Dioulasso",    "BKO": "Bamako",            "MZI": "Mopti",
    "GAQ": "Gao",               "TOM": "Tombouctou",        "CKY": "Conakry",
    "LEK": "Labé",              "OXB": "Bissau",            "ROB": "Monrovia",
    "FNA": "Freetown",          "NIM": "Niamey",            "ZND": "Zinder",
    "AJY": "Agadez",            "MFQ": "Maradi",            "THZ": "Tahoua",
    "NKC": "Nouakchott",        "NDB": "Nouadhibou",        "ATR": "Atar",
    "BJL": "Banjul",            "RAI": "Praia",             "SID": "Sal",
    "VXE": "São Vicente",

    # ── Afrique Centrale
    "DLA": "Douala",            "NSI": "Yaoundé",           "GOU": "Garoua",
    "MVR": "Maroua",            "BFX": "Bafoussam",         "LBV": "Libreville",
    "POG": "Port-Gentil",       "BZV": "Brazzaville",       "PNR": "Pointe-Noire",
    "BGF": "Bangui",            "SSG": "Malabo",            "BSG": "Bata",
    "TMS": "São Tomé",          "FIH": "Kinshasa",          "FBM": "Lubumbashi",
    "GOM": "Goma",              "FKI": "Kisangani",         "MJM": "Mbuji-Mayi",
    "NDJ": "N'Djamena",         "MQQ": "Moundou",

    # ── Afrique du Nord
    "CMN": "Casablanca",        "RAK": "Marrakech",         "RBA": "Rabat",
    "AGA": "Agadir",            "FEZ": "Fès",               "TNG": "Tanger",
    "OUD": "Oujda",             "EUN": "Laâyoune",          "NDR": "Nador",
    "ALG": "Alger",             "ORN": "Oran",              "CZL": "Constantine",
    "AAE": "Annaba",            "TLM": "Tlemcen",           "TUN": "Tunis",
    "DJE": "Djerba",            "MIR": "Monastir",          "SFA": "Sfax",
    "TOE": "Tozeur",            "TIP": "Tripoli",           "BEN": "Benghazi",
    "CAI": "Le Caire",          "HBE": "Alexandrie",        "HRG": "Hurghada",
    "SSH": "Sharm el-Sheikh",   "LXR": "Louxor",            "ASW": "Assouan",
    "KRT": "Khartoum",          "ASM": "Asmara",

    # ── Afrique de l'Est
    "ADD": "Addis-Abeba",       "DIR": "Dire Dawa",         "JIB": "Djibouti",
    "MGQ": "Mogadiscio",        "JUB": "Juba",              "NBO": "Nairobi",
    "MBA": "Mombasa",           "KIS": "Kisumu",            "EDL": "Eldoret",
    "DAR": "Dar es Salaam",     "JRO": "Kilimanjaro",       "ZNZ": "Zanzibar",
    "MWZ": "Mwanza",            "EBB": "Kampala",           "KGL": "Kigali",
    "BJM": "Bujumbura",

    # ── Afrique Australe & Îles
    "TNR": "Antananarivo",      "NOS": "Nosy Be",           "TMM": "Toamasina",
    "MRU": "Maurice",           "RUN": "La Réunion",        "HAH": "Moroni",
    "SEZ": "Seychelles",        "JNB": "Johannesburg",      "CPT": "Le Cap",
    "DUR": "Durban",            "PLZ": "Port Elizabeth",    "BFN": "Bloemfontein",
    "GRJ": "George",            "HRE": "Harare",            "BUQ": "Bulawayo",
    "VFA": "Victoria Falls",    "LUN": "Lusaka",            "LVI": "Livingstone",
    "NLA": "Ndola",             "LLW": "Lilongwe",          "BLZ": "Blantyre",
    "GBE": "Gaborone",          "MUB": "Maun",              "WDH": "Windhoek",
    "LAD": "Luanda",            "SDD": "Lubango",           "MPM": "Maputo",
    "BEW": "Beira",             "APL": "Nampula",           "SHO": "Mbabane",
    "MSU": "Maseru",

    # ── Europe France
    "CDG": "Paris",             "ORY": "Paris-Orly",        "MRS": "Marseille",
    "LYS": "Lyon",              "NCE": "Nice",              "TLS": "Toulouse",
    "BOD": "Bordeaux",          "NTE": "Nantes",            "SXB": "Strasbourg",
    "LIL": "Lille",             "MPL": "Montpellier",       "RNS": "Rennes",
    "BES": "Brest",             "GNB": "Grenoble",          "CFE": "Clermont-Ferrand",
    "TLN": "Toulon",            "BIQ": "Biarritz",          "PUF": "Pau",
    "PGF": "Perpignan",         "LIG": "Limoges",           "CFR": "Caen",
    "CMF": "Chambéry",          "AJA": "Ajaccio",           "BIA": "Bastia",
    "FSC": "Figari",

    # ── Europe Îles Britanniques
    "LHR": "Londres",           "LGW": "Londres-Gatwick",   "STN": "Londres-Stansted",
    "LCY": "Londres-City",      "MAN": "Manchester",        "BHX": "Birmingham",
    "EDI": "Édimbourg",         "GLA": "Glasgow",           "BRS": "Bristol",
    "NCL": "Newcastle",         "LBA": "Leeds",             "LPL": "Liverpool",
    "DUB": "Dublin",            "ORK": "Cork",

    # ── Europe Ibérique
    "MAD": "Madrid",            "BCN": "Barcelone",         "PMI": "Palma de Majorque",
    "AGP": "Málaga",            "ALC": "Alicante",          "VLC": "Valence",
    "SVQ": "Séville",           "BIO": "Bilbao",            "TFS": "Tenerife",
    "LPA": "Las Palmas",        "IBZ": "Ibiza",             "MAH": "Minorque",
    "FUE": "Fuerteventura",     "ACE": "Lanzarote",         "LIS": "Lisbonne",
    "OPO": "Porto",             "FAO": "Faro",              "FNC": "Funchal",
    "PDL": "Ponta Delgada",

    # ── Europe Italie
    "FCO": "Rome",              "MXP": "Milan",             "LIN": "Milan-Linate",
    "VCE": "Venise",            "BLQ": "Bologne",           "FLR": "Florence",
    "NAP": "Naples",            "CTA": "Catane",            "PMO": "Palerme",
    "TRN": "Turin",             "BRI": "Bari",              "GOA": "Gênes",
    "CAG": "Cagliari",          "BDS": "Brindisi",          "PSA": "Pise",

    # ── Europe Allemagne
    "BER": "Berlin",            "FRA": "Francfort",         "MUC": "Munich",
    "HAM": "Hambourg",          "DUS": "Düsseldorf",        "CGN": "Cologne",
    "STR": "Stuttgart",         "HAJ": "Hanovre",           "NUE": "Nuremberg",
    "LEJ": "Leipzig",           "BRE": "Brême",

    # ── Europe Benelux / Suisse / Autriche
    "BRU": "Bruxelles",         "LGG": "Liège",             "AMS": "Amsterdam",
    "EIN": "Eindhoven",         "GVA": "Genève",            "ZRH": "Zurich",
    "BSL": "Bâle",              "VIE": "Vienne",            "INN": "Innsbruck",
    "SZG": "Salzbourg",         "LUX": "Luxembourg",

    # ── Europe Scandinavie & Baltes
    "CPH": "Copenhague",        "ARN": "Stockholm",         "GOT": "Göteborg",
    "OSL": "Oslo",              "BGO": "Bergen",            "TRD": "Trondheim",
    "HEL": "Helsinki",          "KEF": "Reykjavik",         "VNO": "Vilnius",
    "RIX": "Riga",              "TLL": "Tallinn",

    # ── Europe Centrale & Orientale
    "WAW": "Varsovie",          "KRK": "Cracovie",          "GDN": "Gdańsk",
    "WRO": "Wrocław",           "PRG": "Prague",            "BUD": "Budapest",
    "OTP": "Bucarest",          "SOF": "Sofia",             "BEG": "Belgrade",
    "ZAG": "Zagreb",            "SPU": "Split",             "DBV": "Dubrovnik",
    "BTS": "Bratislava",        "LJU": "Ljubljana",         "SJJ": "Sarajevo",
    "TGD": "Podgorica",         "TIA": "Tirana",            "SKP": "Skopje",
    "KIV": "Chișinău",          "MSQ": "Minsk",             "KBP": "Kyiv",
    "LWO": "Lviv",

    # ── Europe Méditerranée
    "IST": "Istanbul",          "ESB": "Ankara",            "AYT": "Antalya",
    "ADB": "Izmir",             "BJV": "Bodrum",            "ATH": "Athènes",
    "SKG": "Thessalonique",     "HER": "Héraklion",         "RHO": "Rhodes",
    "CFU": "Corfou",            "JMK": "Mykonos",           "JTR": "Santorin",
    "MLA": "Malte",             "LCA": "Larnaca",           "PFO": "Paphos",

    # ── Europe Russie & Caucase
    "SVO": "Moscou",            "DME": "Moscou-Domodedovo", "LED": "Saint-Pétersbourg",
    "OVB": "Novossibirsk",      "SVX": "Iekaterinbourg",    "TBS": "Tbilissi",
    "EVN": "Erevan",            "GYD": "Bakou",

    # ── Moyen-Orient
    "DXB": "Dubaï",             "DOH": "Doha",              "AUH": "Abu Dhabi",
    "SHJ": "Sharjah",           "RUH": "Riyadh",            "JED": "Jeddah",
    "MED": "Médine",            "DMM": "Dammam",            "MCT": "Muscat",
    "SLL": "Salalah",           "BAH": "Bahreïn",           "KWI": "Koweït",
    "BEY": "Beyrouth",          "AMM": "Amman",             "AQJ": "Aqaba",
    "TLV": "Tel Aviv",          "BGW": "Bagdad",            "EBL": "Erbil",
    "BSR": "Bassora",           "DAM": "Damas",             "SAH": "Sanaa",
    "ADE": "Aden",              "IKA": "Téhéran",           "MHD": "Mashhad",
    "IFN": "Isfahan",           "SYZ": "Shiraz",

    # ── Asie Centrale
    "ALA": "Almaty",            "NQZ": "Astana",            "TAS": "Tachkent",
    "FRU": "Bichkek",           "DYU": "Douchanbé",         "ASB": "Achgabat",

    # ── Asie du Sud
    "DEL": "Delhi",             "BOM": "Mumbai",            "BLR": "Bangalore",
    "HYD": "Hyderabad",         "MAA": "Chennai",           "CCU": "Kolkata",
    "COK": "Kochi",             "AMD": "Ahmedabad",         "GOI": "Goa",
    "JAI": "Jaipur",            "LKO": "Lucknow",           "ATQ": "Amritsar",
    "TRV": "Thiruvananthapuram", "PNQ": "Pune",             "KHI": "Karachi",
    "LHE": "Lahore",            "ISB": "Islamabad",         "DAC": "Dhaka",
    "CMB": "Colombo",           "KTM": "Katmandou",         "MLE": "Malé",
    "PBH": "Paro",

    # ── Asie du Sud-Est
    "BKK": "Bangkok",           "CNX": "Chiang Mai",        "HKT": "Phuket",
    "KBV": "Krabi",             "HAN": "Hanoï",             "SGN": "Hô-Chi-Minh-Ville",
    "DAD": "Da Nang",           "PNH": "Phnom Penh",        "REP": "Siem Reap",
    "VTE": "Vientiane",         "RGN": "Yangon",            "KUL": "Kuala Lumpur",
    "PEN": "Penang",            "BKI": "Kota Kinabalu",     "KCH": "Kuching",
    "SIN": "Singapour",         "CGK": "Jakarta",           "DPS": "Bali",
    "SUB": "Surabaya",          "KNO": "Medan",             "MNL": "Manille",
    "CEB": "Cebu",              "DVO": "Davao",

    # ── Asie de l'Est
    "PEK": "Pékin",             "PVG": "Shanghai",          "SHA": "Shanghai-Hongqiao",
    "CAN": "Guangzhou",         "SZX": "Shenzhen",          "CTU": "Chengdu",
    "CKG": "Chongqing",         "HGH": "Hangzhou",          "KMG": "Kunming",
    "XIY": "Xi'an",             "TAO": "Qingdao",           "XMN": "Xiamen",
    "WUH": "Wuhan",             "NKG": "Nanjing",           "CGO": "Zhengzhou",
    "TSN": "Tianjin",           "HRB": "Harbin",            "DLC": "Dalian",
    "URC": "Urumqi",            "HKG": "Hong Kong",         "MFM": "Macao",
    "TPE": "Taipei",            "KHH": "Kaohsiung",         "NRT": "Tokyo",
    "HND": "Tokyo-Haneda",      "KIX": "Osaka",             "ITM": "Osaka-Itami",
    "NGO": "Nagoya",            "FUK": "Fukuoka",           "CTS": "Sapporo",
    "OKA": "Okinawa",           "HIJ": "Hiroshima",         "ICN": "Séoul",
    "GMP": "Séoul-Gimpo",       "PUS": "Busan",             "CJU": "Jeju",
    "ULN": "Oulan-Bator",

    # ── Amériques États-Unis
    "JFK": "New York",          "LGA": "New York-LaGuardia", "EWR": "Newark",
    "LAX": "Los Angeles",       "ORD": "Chicago",           "MDW": "Chicago-Midway",
    "DFW": "Dallas",            "IAH": "Houston",           "MIA": "Miami",
    "ATL": "Atlanta",           "SFO": "San Francisco",     "SEA": "Seattle",
    "IAD": "Washington",        "DCA": "Washington-Reagan", "BOS": "Boston",
    "DEN": "Denver",            "PHX": "Phoenix",           "LAS": "Las Vegas",
    "MCO": "Orlando",           "MSP": "Minneapolis",       "DTW": "Détroit",
    "PHL": "Philadelphie",      "CLT": "Charlotte",         "SLC": "Salt Lake City",
    "PDX": "Portland",          "TPA": "Tampa",             "BWI": "Baltimore",
    "SAN": "San Diego",         "HNL": "Honolulu",          "ANC": "Anchorage",
    "MSY": "La Nouvelle-Orléans", "MCI": "Kansas City",     "BNA": "Nashville",
    "AUS": "Austin",            "RDU": "Raleigh",           "PIT": "Pittsburgh",

    # ── Amériques Canada
    "YUL": "Montréal",          "YYZ": "Toronto",           "YVR": "Vancouver",
    "YYC": "Calgary",           "YEG": "Edmonton",          "YOW": "Ottawa",
    "YWG": "Winnipeg",          "YQB": "Québec",            "YHZ": "Halifax",

    # ── Mexique & Amérique Centrale
    "MEX": "Mexico City",       "CUN": "Cancún",            "GDL": "Guadalajara",
    "MTY": "Monterrey",         "TIJ": "Tijuana",           "PVR": "Puerto Vallarta",
    "SJD": "Los Cabos",         "GUA": "Guatemala",         "TGU": "Tegucigalpa",
    "SAL": "San Salvador",      "MGA": "Managua",           "SJO": "San José",
    "PTY": "Panama City",

    # ── Caraïbes
    "HAV": "La Havane",         "NAS": "Nassau",            "PUJ": "Punta Cana",
    "SDQ": "Saint-Domingue",    "KIN": "Kingston",          "MBJ": "Montego Bay",
    "SJU": "San Juan",          "PAP": "Port-au-Prince",    "BGI": "Bridgetown",
    "POS": "Port of Spain",     "PTP": "Pointe-à-Pitre",    "FDF": "Fort-de-France",
    "CAY": "Cayenne",

    # ── Amériques du Sud
    "GRU": "São Paulo",         "CGH": "São Paulo-Congonhas", "GIG": "Rio de Janeiro",
    "BSB": "Brasília",          "CNF": "Belo Horizonte",    "SSA": "Salvador",
    "REC": "Recife",            "FOR": "Fortaleza",         "MAO": "Manaus",
    "POA": "Porto Alegre",      "CWB": "Curitiba",          "BEL": "Belém",
    "NAT": "Natal",             "EZE": "Buenos Aires",      "AEP": "Buenos Aires-Aeroparque",
    "COR": "Córdoba",           "MDZ": "Mendoza",           "BRC": "Bariloche",
    "USH": "Ushuaia",           "SCL": "Santiago",          "LIM": "Lima",
    "CUZ": "Cusco",             "BOG": "Bogotá",            "MDE": "Medellín",
    "CLO": "Cali",              "CTG": "Cartagène",         "CCS": "Caracas",
    "UIO": "Quito",             "GYE": "Guayaquil",         "LPB": "La Paz",
    "VVI": "Santa Cruz",        "ASU": "Asunción",          "MVD": "Montevideo",
    "PBM": "Paramaribo",        "GEO": "Georgetown",

    # ── Océanie
    "SYD": "Sydney",            "MEL": "Melbourne",         "BNE": "Brisbane",
    "PER": "Perth",             "ADL": "Adélaïde",          "OOL": "Gold Coast",
    "CNS": "Cairns",            "DRW": "Darwin",            "HBA": "Hobart",
    "AKL": "Auckland",          "WLG": "Wellington",        "CHC": "Christchurch",
    "ZQN": "Queenstown",        "NAN": "Nadi",              "POM": "Port Moresby",
    "NOU": "Nouméa",            "PPT": "Papeete",           "GUM": "Guam",
}


AIRLINES = [
    ("Air France", "AF"), ("Ethiopian Airlines", "ET"),
    ("Royal Air Maroc", "AT"), ("Brussels Airlines", "SN"),
    ("Turkish Airlines", "TK"), ("Kenya Airways", "KQ"),
    ("ASKY Airlines", "KP"), ("Air Cote d'Ivoire", "HF"),
]
