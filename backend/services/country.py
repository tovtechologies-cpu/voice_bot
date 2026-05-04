"""Country -> phone dial code, currency, mobile-money operators map.
Single source of truth for the country-aware payment flow."""

# Dial code -> ISO country (longest prefix wins).
# Covers all African countries + key diaspora destinations.
PHONE_DIAL_TO_COUNTRY = {
    # ── West Africa
    "229": "BJ", "228": "TG", "225": "CI", "221": "SN", "223": "ML",
    "226": "BF", "227": "NE", "224": "GN", "245": "GW", "231": "LR",
    "232": "SL", "220": "GM", "222": "MR", "238": "CV",
    "233": "GH", "234": "NG",
    # ── Central Africa
    "237": "CM", "241": "GA", "242": "CG", "243": "CD", "236": "CF",
    "240": "GQ", "239": "ST", "235": "TD",
    # ── North Africa
    "212": "MA", "213": "DZ", "216": "TN", "218": "LY", "20": "EG", "249": "SD",
    # ── East Africa
    "251": "ET", "253": "DJ", "252": "SO", "211": "SS",
    "254": "KE", "255": "TZ", "256": "UG", "250": "RW", "257": "BI",
    # ── Southern Africa & islands
    "27": "ZA", "263": "ZW", "260": "ZM", "265": "MW", "267": "BW",
    "264": "NA", "244": "AO", "258": "MZ", "266": "LS", "268": "SZ",
    "261": "MG", "230": "MU", "262": "RE", "248": "SC", "269": "KM",
    # ── Europe / Diaspora
    "33": "FR", "32": "BE", "41": "CH", "44": "GB", "1": "US",
    "49": "DE", "34": "ES", "39": "IT", "351": "PT", "31": "NL",
    "30": "GR", "46": "SE", "47": "NO", "45": "DK", "358": "FI",
    "353": "IE", "352": "LU", "43": "AT",
    # ── Middle East
    "971": "AE", "974": "QA", "966": "SA", "965": "KW", "973": "BH",
    "968": "OM", "962": "JO", "961": "LB", "972": "IL",
    # ── Asia hubs (for diaspora travel)
    "86": "CN", "91": "IN", "81": "JP", "82": "KR", "65": "SG",
    "60": "MY", "66": "TH", "62": "ID", "63": "PH", "84": "VN",
}

# Country -> default currency
COUNTRY_CURRENCY = {
    # CFA Franc countries (West)
    "BJ": "XOF", "TG": "XOF", "SN": "XOF", "CI": "XOF", "ML": "XOF",
    "BF": "XOF", "NE": "XOF", "GW": "XOF",
    # CFA Franc Central (CEMAC)
    "CM": "XAF", "CF": "XAF", "TD": "XAF", "CG": "XAF", "GA": "XAF", "GQ": "XAF",
    # Other African
    "NG": "NGN", "GH": "GHS", "KE": "KES", "TZ": "TZS", "UG": "UGX",
    "RW": "RWF", "BI": "BIF", "ET": "ETB", "DJ": "DJF",
    "MA": "MAD", "DZ": "DZD", "TN": "TND", "LY": "LYD", "EG": "EGP",
    "ZA": "ZAR", "ZM": "ZMW", "ZW": "USD", "MW": "MWK",
    "MZ": "MZN", "AO": "AOA", "BW": "BWP", "NA": "NAD",
    "MG": "MGA", "MU": "MUR", "CV": "CVE", "SC": "SCR", "KM": "KMF",
    "GN": "GNF", "MR": "MRU", "GM": "GMD", "SL": "SLE", "LR": "LRD",
    "SO": "SOS", "SD": "SDG", "SS": "SSP", "RE": "EUR",
    # Europe
    "FR": "EUR", "BE": "EUR", "CH": "CHF", "GB": "GBP", "DE": "EUR",
    "ES": "EUR", "IT": "EUR", "PT": "EUR", "NL": "EUR", "IE": "EUR",
    "LU": "EUR", "AT": "EUR",
    # Default / diaspora
    "US": "USD", "AE": "AED", "QA": "QAR", "SA": "SAR",
}

# ── Mobile money operators per country ────────────────────────────────────
# Each entry: {"id": "<unique snake_case>", "name": "<display>", "country": "<ISO>", "currency": "<code>"}
# Used to dynamically register MOCK drivers and build the per-country menu.
COUNTRY_PAYMENT_METHODS = {

    # ───────── Bénin ─────────
    "BJ": [
        {"id": "celtiis_cash",   "name": "Celtiis Cash"},      # priority partner
        {"id": "mtn_momo_bj",    "name": "MTN MoMo"},
        {"id": "moov_money_bj",  "name": "Moov Money (Flooz)"},
    ],

    # ───────── Togo ─────────
    "TG": [
        {"id": "tmoney",         "name": "T-Money (Togocom)"},
        {"id": "flooz_tg",       "name": "Flooz (Moov Africa)"},
    ],

    # ───────── Sénégal ─────────
    "SN": [
        {"id": "wave_sn",        "name": "Wave"},
        {"id": "orange_money_sn","name": "Orange Money"},
        {"id": "free_money_sn",  "name": "Free Money"},
        {"id": "wizall_sn",      "name": "Wizall Money"},
    ],

    # ───────── Côte d'Ivoire ─────────
    "CI": [
        {"id": "wave_ci",        "name": "Wave"},
        {"id": "orange_money_ci","name": "Orange Money"},
        {"id": "mtn_momo_ci",    "name": "MTN MoMo"},
        {"id": "moov_money_ci",  "name": "Moov Money"},
    ],

    # ───────── Mali ─────────
    "ML": [
        {"id": "orange_money_ml","name": "Orange Money"},
        {"id": "moov_money_ml",  "name": "Moov Money"},
        {"id": "wave_ml",        "name": "Wave"},
    ],

    # ───────── Burkina Faso ─────────
    "BF": [
        {"id": "orange_money_bf","name": "Orange Money"},
        {"id": "moov_money_bf",  "name": "Moov Money"},
        {"id": "telecel_bf",     "name": "Telecel Money"},
    ],

    # ───────── Niger ─────────
    "NE": [
        {"id": "airtel_money_ne","name": "Airtel Money"},
        {"id": "orange_money_ne","name": "Orange Money"},
        {"id": "moov_money_ne",  "name": "Moov Money"},
    ],

    # ───────── Guinée ─────────
    "GN": [
        {"id": "orange_money_gn","name": "Orange Money"},
        {"id": "mtn_momo_gn",    "name": "MTN MoMo"},
    ],

    # ───────── Guinée-Bissau ─────────
    "GW": [
        {"id": "orange_money_gw","name": "Orange Money"},
    ],

    # ───────── Ghana ─────────
    "GH": [
        {"id": "mtn_momo_gh",    "name": "MTN MoMo"},
        {"id": "vodafone_cash",  "name": "Vodafone Cash"},
        {"id": "airteltigo_gh",  "name": "AirtelTigo Money"},
    ],

    # ───────── Nigeria ─────────
    "NG": [
        {"id": "opay_ng",        "name": "OPay"},
        {"id": "palmpay_ng",     "name": "PalmPay"},
        {"id": "kuda_ng",        "name": "Kuda Bank"},
        {"id": "paystack_ng",    "name": "Paystack (Card/USSD)"},
    ],

    # ───────── Sierra Leone ─────────
    "SL": [{"id": "orange_money_sl", "name": "Orange Money"}, {"id": "africell_money_sl", "name": "Afrimoney"}],

    # ───────── Liberia ─────────
    "LR": [{"id": "mtn_momo_lr", "name": "MTN MoMo"}, {"id": "orange_money_lr", "name": "Orange Money"}],

    # ───────── Gambie ─────────
    "GM": [{"id": "qmoney_gm", "name": "QMoney"}, {"id": "africell_money_gm", "name": "Afrimoney"}],

    # ───────── Mauritanie ─────────
    "MR": [{"id": "bankily_mr", "name": "Bankily"}, {"id": "masrvi_mr", "name": "Masrvi"}, {"id": "sedad_mr", "name": "Sedad"}],

    # ───────── Cabo Verde ─────────
    "CV": [{"id": "vinti4_cv", "name": "Vinti4"}],

    # ───────── Cameroun ─────────
    "CM": [
        {"id": "mtn_momo_cm",    "name": "MTN MoMo"},
        {"id": "orange_money_cm","name": "Orange Money"},
    ],

    # ───────── Gabon ─────────
    "GA": [{"id": "airtel_money_ga", "name": "Airtel Money"}, {"id": "moov_money_ga", "name": "Moov Money"}],

    # ───────── Congo ─────────
    "CG": [{"id": "mtn_momo_cg", "name": "MTN MoMo"}, {"id": "airtel_money_cg", "name": "Airtel Money"}],

    # ───────── RDC ─────────
    "CD": [
        {"id": "orange_money_cd","name": "Orange Money"},
        {"id": "mpesa_cd",       "name": "M-Pesa"},
        {"id": "airtel_money_cd","name": "Airtel Money"},
    ],

    # ───────── Centrafrique ─────────
    "CF": [{"id": "orange_money_cf", "name": "Orange Money"}, {"id": "telecel_cf", "name": "Telecel Money"}],

    # ───────── Tchad ─────────
    "TD": [{"id": "airtel_money_td", "name": "Airtel Money"}, {"id": "tigo_cash_td", "name": "Tigo Cash"}],

    # ───────── Guinée Équatoriale ─────────
    "GQ": [{"id": "muni_gq", "name": "Muni Money"}],

    # ───────── Sao Tomé ─────────
    "ST": [{"id": "stp_pay", "name": "STP Pay"}],

    # ───────── Maroc ─────────
    "MA": [
        {"id": "cmi_ma",         "name": "CMI (Carte bancaire)"},
        {"id": "inwi_money",     "name": "Inwi Money"},
        {"id": "orange_money_ma","name": "Orange Money"},
        {"id": "barid_pay",      "name": "Barid Pay"},
    ],

    # ───────── Algérie ─────────
    "DZ": [{"id": "edahabia", "name": "Edahabia (CIB)"}, {"id": "baridi_mob", "name": "BaridiMob"}],

    # ───────── Tunisie ─────────
    "TN": [{"id": "d17_tn", "name": "D17 (BIAT)"}, {"id": "flouci_tn", "name": "Flouci"}],

    # ───────── Égypte ─────────
    "EG": [
        {"id": "vodafone_cash_eg","name": "Vodafone Cash"},
        {"id": "instapay_eg",     "name": "InstaPay"},
        {"id": "orange_cash_eg",  "name": "Orange Cash"},
        {"id": "fawry_eg",        "name": "Fawry"},
    ],

    # ───────── Libye ─────────
    "LY": [{"id": "tadawul_ly", "name": "Tadawul"}],

    # ───────── Soudan ─────────
    "SD": [{"id": "bankak_sd", "name": "Bankak"}],

    # ───────── Soudan du Sud ─────────
    "SS": [{"id": "mgurush_ss", "name": "mGurush"}],

    # ───────── Éthiopie ─────────
    "ET": [{"id": "telebirr", "name": "Telebirr"}, {"id": "cbe_birr", "name": "CBE Birr"}],

    # ───────── Djibouti ─────────
    "DJ": [{"id": "d_money", "name": "D-Money"}, {"id": "waafi_dj", "name": "Waafi"}],

    # ───────── Somalie ─────────
    "SO": [{"id": "evc_plus", "name": "EVC Plus"}, {"id": "zaad_so", "name": "ZAAD"}, {"id": "sahal_so", "name": "Sahal"}],

    # ───────── Kenya ─────────
    "KE": [
        {"id": "mpesa_ke",       "name": "M-Pesa"},
        {"id": "airtel_money_ke","name": "Airtel Money"},
        {"id": "tkash_ke",       "name": "T-Kash"},
    ],

    # ───────── Tanzanie ─────────
    "TZ": [
        {"id": "mpesa_tz",       "name": "M-Pesa"},
        {"id": "tigo_pesa",      "name": "Mixx by Yas (Tigo Pesa)"},
        {"id": "airtel_money_tz","name": "Airtel Money"},
        {"id": "halopesa",       "name": "HaloPesa"},
    ],

    # ───────── Ouganda ─────────
    "UG": [
        {"id": "mtn_momo_ug",    "name": "MTN MoMo"},
        {"id": "airtel_money_ug","name": "Airtel Money"},
    ],

    # ───────── Rwanda ─────────
    "RW": [{"id": "mtn_momo_rw", "name": "MTN MoMo"}, {"id": "airtel_money_rw", "name": "Airtel Money"}],

    # ───────── Burundi ─────────
    "BI": [{"id": "lumicash_bi", "name": "Lumicash"}, {"id": "ecocash_bi", "name": "EcoCash"}],

    # ───────── Afrique du Sud ─────────
    "ZA": [
        {"id": "snapscan_za",    "name": "SnapScan"},
        {"id": "zapper_za",      "name": "Zapper"},
        {"id": "ozow_za",        "name": "Ozow"},
        {"id": "payshap_za",     "name": "PayShap"},
    ],

    # ───────── Zimbabwe ─────────
    "ZW": [{"id": "ecocash_zw", "name": "EcoCash"}, {"id": "onemoney_zw", "name": "OneMoney"}],

    # ───────── Zambie ─────────
    "ZM": [{"id": "mtn_momo_zm", "name": "MTN MoMo"}, {"id": "airtel_money_zm", "name": "Airtel Money"}, {"id": "zamtel_kwacha", "name": "Zamtel Kwacha"}],

    # ───────── Malawi ─────────
    "MW": [{"id": "tnm_mpamba", "name": "TNM Mpamba"}, {"id": "airtel_money_mw", "name": "Airtel Money"}],

    # ───────── Mozambique ─────────
    "MZ": [{"id": "mpesa_mz", "name": "M-Pesa"}, {"id": "emola_mz", "name": "e-Mola"}, {"id": "mkesh_mz", "name": "Mkesh"}],

    # ───────── Angola ─────────
    "AO": [{"id": "multicaixa_ao", "name": "Multicaixa Express"}, {"id": "kwik_ao", "name": "Kwik"}],

    # ───────── Botswana ─────────
    "BW": [{"id": "orange_money_bw", "name": "Orange Money"}, {"id": "mascom_myzaka", "name": "Mascom MyZaka"}],

    # ───────── Namibie ─────────
    "NA": [{"id": "mtc_money_na", "name": "MTC Money"}, {"id": "easy_wallet_na", "name": "Easy Wallet"}],

    # ───────── Lesotho ─────────
    "LS": [{"id": "mpesa_ls", "name": "M-Pesa"}, {"id": "ecocash_ls", "name": "EcoCash"}],

    # ───────── Eswatini ─────────
    "SZ": [{"id": "mtn_momo_sz", "name": "MTN MoMo"}, {"id": "eswatini_mobile", "name": "Eswatini Mobile"}],

    # ───────── Madagascar ─────────
    "MG": [{"id": "mvola_mg", "name": "MVola"}, {"id": "orange_money_mg", "name": "Orange Money"}, {"id": "airtel_money_mg", "name": "Airtel Money"}],

    # ───────── Maurice ─────────
    "MU": [{"id": "juice_mu", "name": "Juice by MCB"}, {"id": "blink_mu", "name": "Blink by Emtel"}],

    # ───────── La Réunion ─────────
    "RE": [{"id": "lyf_re", "name": "Lyf Pay"}],

    # ───────── Seychelles / Comores ─────────
    "SC": [{"id": "ecash_sc", "name": "eCash"}],
    "KM": [{"id": "holo_km", "name": "Holo (Comores Telecom)"}],
}


def country_from_phone(phone: str) -> str:
    """Detect ISO country from a phone number. Returns 'BJ' as a safe default."""
    if not phone:
        return "BJ"
    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    # Strip the "web" prefix used internally for webchat sessions ("+webXXXX")
    if clean.lower().startswith("web"):
        return "BJ"
    # Strip the "tg" prefix used internally for telegram chat ids ("+tgXXXX")
    if clean.lower().startswith("tg"):
        return "BJ"
    # Try longest dial codes first (3 digits, then 2, then 1)
    for length in (3, 2, 1):
        prefix = clean[:length]
        if prefix in PHONE_DIAL_TO_COUNTRY:
            return PHONE_DIAL_TO_COUNTRY[prefix]
    return "BJ"


def get_country_currency(country_code: str) -> str:
    """Return the local currency for a country (default XOF)."""
    return COUNTRY_CURRENCY.get((country_code or "").upper(), "XOF")


# Build reverse dial-code map once (country -> primary dial code, shortest first).
_COUNTRY_TO_DIAL: dict[str, str] = {}
for _dial, _cc in PHONE_DIAL_TO_COUNTRY.items():
    if _cc not in _COUNTRY_TO_DIAL or len(_dial) < len(_COUNTRY_TO_DIAL[_cc]):
        _COUNTRY_TO_DIAL[_cc] = _dial


def get_country_dial_code(country_code: str) -> str:
    """Return primary international dial code for a country (without '+'), or '' if unknown."""
    return _COUNTRY_TO_DIAL.get((country_code or "").upper(), "")


# Country flag emoji per ISO code — used in the "Pays detecté" header.
# Build dynamically: each ISO letter maps to its regional indicator symbol.
def country_flag(country_code: str) -> str:
    """Return flag emoji for ISO-2 country code, or empty string if invalid."""
    cc = (country_code or "").upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in cc)
