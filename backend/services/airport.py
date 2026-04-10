"""Airport recognition with rapidfuzz fuzzy matching."""
import logging
from typing import Optional, Tuple
from rapidfuzz import fuzz, process
from config import AIRPORT_CODES, CODE_TO_CITY

logger = logging.getLogger("AirportService")

# Build search corpus for fuzzy matching
_CITY_LIST = list(AIRPORT_CODES.keys())
_CODE_LIST = list(CODE_TO_CITY.keys())


def resolve_airport(query: str) -> Optional[str]:
    """5-step destination resolution:
    1. Exact match in local DB
    2. IATA code direct match
    3. Fuzzy match (rapidfuzz, score >= 70)
    4. Partial/contains match
    5. Return None (caller should ask Claude or user)
    """
    if not query:
        return None
    query_clean = query.strip().lower()

    # Step 1: Exact match
    if query_clean in AIRPORT_CODES:
        return AIRPORT_CODES[query_clean]

    # Step 2: Direct IATA code
    upper = query_clean.upper()
    if upper in CODE_TO_CITY and len(upper) == 3:
        return upper

    # Step 3: Fuzzy match
    result = process.extractOne(query_clean, _CITY_LIST, scorer=fuzz.WRatio, score_cutoff=70)
    if result:
        matched_city, score, _ = result
        code = AIRPORT_CODES[matched_city]
        logger.info(f"Fuzzy match: '{query}' -> '{matched_city}' ({code}) [score={score:.0f}]")
        return code

    # Step 4: Contains match
    for city, code in AIRPORT_CODES.items():
        if query_clean in city or city in query_clean:
            return code

    # Step 5: No match
    logger.info(f"Airport not found: '{query}'")
    return None


def get_airport_code(city_name: str) -> Optional[str]:
    """Legacy wrapper for resolve_airport."""
    return resolve_airport(city_name)


def get_city_name(code: str) -> str:
    """Get city name from IATA code."""
    return CODE_TO_CITY.get(code.upper(), code) if code else code


def suggest_airports(query: str, limit: int = 5) -> list:
    """Return top fuzzy matches for a query, useful for 'did you mean?' suggestions."""
    if not query:
        return []
    query_clean = query.strip().lower()
    results = process.extract(query_clean, _CITY_LIST, scorer=fuzz.WRatio, limit=limit, score_cutoff=50)
    return [{"city": city, "code": AIRPORT_CODES[city], "score": score} for city, score, _ in results]
