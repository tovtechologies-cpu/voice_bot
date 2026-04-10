"""Natural language date parsing with dateparser."""
import logging
from datetime import datetime, timedelta
from typing import Optional
import dateparser

logger = logging.getLogger("DateService")

# Configure dateparser for French + English
DATEPARSER_SETTINGS = {
    'PREFER_DATES_FROM': 'future',
    'PREFER_DAY_OF_MONTH': 'first',
    'DATE_ORDER': 'DMY',
    'RETURN_AS_TIMEZONE_AWARE': False,
}


def parse_date(text: str, language: str = "fr") -> Optional[str]:
    """Parse a natural language date string into YYYY-MM-DD.

    Supports French and English:
    - 'demain', 'apres-demain', 'lundi prochain'
    - '15 janvier', 'le 20 mars'
    - 'next friday', 'tomorrow'
    - '2025-03-15' (ISO)
    """
    if not text:
        return None
    text_clean = text.strip().lower()

    # Check ISO format first (YYYY-MM-DD)
    import re
    iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text_clean)
    if iso_match:
        return text_clean

    # Quick matches for common French words
    today = datetime.now()
    quick = _quick_french_match(text_clean, today)
    if quick:
        return quick

    # Try dateparser with French locale first
    languages = ['fr', 'en'] if language == 'fr' else ['en', 'fr']
    parsed = dateparser.parse(text_clean, languages=languages, settings=DATEPARSER_SETTINGS)

    if parsed:
        # Ensure date is in the future
        if parsed.date() < today.date():
            parsed = parsed.replace(year=parsed.year + 1)
        result = parsed.strftime("%Y-%m-%d")
        logger.info(f"Date parsed: '{text}' -> {result}")
        return result

    logger.info(f"Date not parsed: '{text}'")
    return None


def _quick_french_match(text: str, today: datetime) -> Optional[str]:
    """Handle common French date expressions quickly."""
    # Ordered longest-first to avoid substring matches
    mapping = [
        ("apres-demain", 2),
        ("apres demain", 2),
        ("aujourd'hui", 0),
        ("aujourdhui", 0),
        ("tomorrow", 1),
        ("demain", 1),
        ("today", 0),
    ]

    for phrase, days in mapping:
        if phrase in text:
            return (today + timedelta(days=days)).strftime("%Y-%m-%d")

    # Day of week (French)
    day_names_fr = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
        "vendredi": 4, "samedi": 5, "dimanche": 6
    }
    day_names_en = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }

    all_days = {**day_names_fr, **day_names_en}
    for day_name, day_num in all_days.items():
        if day_name in text:
            current_day = today.weekday()
            days_ahead = (day_num - current_day) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next occurrence
            if "prochain" in text or "next" in text:
                if days_ahead <= 0:
                    days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    return None


def generate_date_options(language: str = "fr") -> list:
    """Generate date picker options for WhatsApp interactive list."""
    today = datetime.now()
    options = []

    labels_fr = ["Demain", "Apres-demain"]
    labels_en = ["Tomorrow", "Day after tomorrow"]
    labels = labels_fr if language == "fr" else labels_en

    for i, label in enumerate(labels):
        date = today + timedelta(days=i + 1)
        options.append({
            "id": date.strftime("%Y-%m-%d"),
            "title": label,
            "description": date.strftime("%A %d %B" if language == "fr" else "%A, %B %d")
        })

    # Add next 5 days
    for i in range(3, 8):
        date = today + timedelta(days=i)
        day_name = date.strftime("%A")
        options.append({
            "id": date.strftime("%Y-%m-%d"),
            "title": day_name,
            "description": date.strftime("%d/%m/%Y")
        })

    return options
