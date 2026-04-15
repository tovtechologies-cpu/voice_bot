"""Helper utilities."""
import random
import string
import re
from datetime import datetime, timezone, timedelta
import math
from config import EUR_TO_XOF


def generate_booking_ref() -> str:
    chars = string.ascii_uppercase + string.digits
    return f"TRV-{''.join(random.choices(chars, k=6))}"


def mask_phone(phone: str) -> str:
    if len(phone) >= 4:
        return "****" + phone[-4:]
    return "****" + phone


def format_timestamp_gmt1(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    gmt1 = dt + timedelta(hours=1)
    return gmt1.strftime("%d/%m/%Y a %H:%M")


def eur_to_xof(eur: float) -> int:
    return int(math.ceil(eur * EUR_TO_XOF / 5) * 5)


def normalize_phone(phone: str) -> str:
    """Normalize phone number. Handles Benin new 10-digit format (ARCEP 2024)."""
    digits = re.sub(r'\D', '', phone)

    # Strip international dialing prefix 00
    if digits.startswith('00'):
        digits = digits[2:]

    # Benin complete new format: 22901XXXXXXXX (13 digits)
    if len(digits) == 13 and digits.startswith('22901'):
        return digits

    # Benin new without country code: 01XXXXXXXX (10 digits)
    if len(digits) == 10 and digits.startswith('01'):
        return '229' + digits

    # Benin old with country code: 229XXXXXXXX (11 digits)
    if len(digits) == 11 and digits.startswith('229'):
        return '22901' + digits[3:]

    # Benin old without country code: 8 digits
    if len(digits) == 8:
        return '22901' + digits

    # France complete: 33XXXXXXXXX (11 digits)
    if len(digits) == 11 and digits.startswith('33'):
        return digits

    # France local: 06/07 -> add 33
    if len(digits) == 10 and digits.startswith('0'):
        return '33' + digits[1:]

    # Other countries with country code
    if len(digits) >= 11:
        return digits

    return digits
