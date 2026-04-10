"""Claude AI intent parsing service."""
import os
import re
import json
import uuid
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from config import EMERGENT_LLM_KEY, AIRPORT_CODES

logger = logging.getLogger("AIService")


async def parse_travel_intent(text: str, language: str = "fr") -> Dict[str, Any]:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        if not EMERGENT_LLM_KEY:
            return fallback_parse_intent(text, language)

        system_prompt = f"""Tu es un assistant de reservation de vols. Extrais les informations de voyage.
Retourne UNIQUEMENT un JSON valide:
{{
  "origin": "code IATA ou ville (defaut: COO si non mentionne)",
  "destination": "code IATA ou ville ou null",
  "departure_date": "YYYY-MM-DD ou null",
  "return_date": "YYYY-MM-DD ou null",
  "passengers": nombre (defaut: 1)
}}
Codes IATA: DSS (Dakar), COO (Cotonou), LOS (Lagos), ACC (Accra), ABJ (Abidjan), CDG (Paris), LHR (Londres)
Aujourd'hui: {datetime.now().strftime("%Y-%m-%d")}
UNIQUEMENT le JSON."""

        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"intent-{uuid.uuid4()}", system_message=system_prompt).with_model("anthropic", "claude-sonnet-4-5-20250929")
        response = await chat.send_message(UserMessage(text=text))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"AI parsing error: {e}")
        return fallback_parse_intent(text, language)


def fallback_parse_intent(text: str, language: str) -> Dict:
    text_lower = text.lower()
    destination = None
    origin = "COO"
    for city, code in AIRPORT_CODES.items():
        if city in text_lower:
            if destination is None:
                destination = code
            else:
                origin = code
    departure_date = None
    today = datetime.now()
    if "demain" in text_lower or "tomorrow" in text_lower:
        departure_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "vendredi" in text_lower or "friday" in text_lower:
        days_ahead = (4 - today.weekday()) % 7 or 7
        departure_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    passengers = 1
    pax_match = re.search(r'(\d+)\s*(passager|personne|adulte|people|passenger|adult)', text_lower)
    if pax_match:
        passengers = int(pax_match.group(1))
    return {"origin": origin, "destination": destination, "departure_date": departure_date, "passengers": passengers}


def detect_language(text: str) -> str:
    french_words = ["je", "veux", "aller", "pour", "le", "la", "un", "une", "merci", "bonjour", "oui", "non", "vol", "billet"]
    text_lower = text.lower()
    french_count = sum(1 for word in french_words if f" {word} " in f" {text_lower} " or text_lower.startswith(word) or text_lower.endswith(word))
    return "fr" if french_count >= 1 else "en"


def parse_yes_no(text: str) -> str:
    """Parse natural language yes/no responses. Returns 'yes', 'no', or 'unknown'."""
    text_lower = text.strip().lower()
    yes_words = ["1", "oui", "yes", "ok", "okay", "d'accord", "daccord", "confirmer", "confirm", "bien sur", "exactement", "tout a fait", "parfait", "c'est bon", "volontiers", "absolument", "ouais", "yep", "yup", "ya", "wi"]
    no_words = ["2", "non", "no", "nope", "pas", "annuler", "cancel", "refuser", "jamais", "nan", "nah"]
    for word in yes_words:
        if text_lower == word or text_lower.startswith(word + " ") or text_lower.startswith(word + ","):
            return "yes"
    for word in no_words:
        if text_lower == word or text_lower.startswith(word + " ") or text_lower.startswith(word + ","):
            return "no"
    return "unknown"
