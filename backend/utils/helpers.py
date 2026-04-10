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
