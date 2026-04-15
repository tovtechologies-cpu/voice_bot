"""Multilingual translation and confidence pipeline — Phase C."""
import logging
import uuid
import json
from typing import Dict, Tuple
from config import EMERGENT_LLM_KEY

logger = logging.getLogger("TranslationService")

# Languages that need translation to French before parsing
AFRICAN_LANGUAGES = {"wo", "fon", "yo", "ha", "sw"}
# Languages handled directly by Claude
DIRECT_LANGUAGES = {"fr", "en"}
# All supported languages
SUPPORTED_LANGUAGES = DIRECT_LANGUAGES | AFRICAN_LANGUAGES

LANGUAGE_NAMES = {
    "fr": "Francais",
    "en": "English",
    "wo": "Wolof",
    "fon": "Fon",
    "yo": "Yoruba",
    "ha": "Hausa",
    "sw": "Swahili",
}


async def translate_to_french(text: str, source_lang: str) -> Tuple[str, float]:
    """Translate African language text to French via Claude. Returns (translated_text, confidence)."""
    if source_lang in DIRECT_LANGUAGES:
        return text, 1.0

    lang_name = LANGUAGE_NAMES.get(source_lang, source_lang)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        if not EMERGENT_LLM_KEY:
            logger.warning("No LLM key — returning original text")
            return text, 0.3

        system_prompt = f"""You are a translation expert specializing in African languages.
Translate the following {lang_name} text to French.
Return ONLY a JSON object:
{{
  "translated": "the French translation",
  "confidence": 0.0 to 1.0 (how confident you are in the translation accuracy),
  "detected_intent": "greeting|booking|cancellation|modification|refund|question|unknown"
}}
If you cannot translate, set confidence to 0 and translated to the original text.
Return ONLY valid JSON, nothing else."""

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"translate-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        response = await chat.send_message(UserMessage(text=text))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text)
        translated = result.get("translated", text)
        confidence = float(result.get("confidence", 0.5))

        logger.info(f"[TRANSLATE] {lang_name} -> FR | confidence={confidence:.2f} | '{text[:50]}' -> '{translated[:50]}'")
        return translated, confidence

    except Exception as e:
        logger.error(f"Translation error ({lang_name}): {e}")
        return text, 0.3


def detect_language_extended(text: str) -> str:
    """Extended language detection supporting 7 languages."""
    text_lower = text.lower().strip()

    # Wolof markers
    wolof_words = ["nanga", "def", "jere", "jef", "baal", "ma", "nekk", "dem", "naa", "lii",
                   "yow", "man", "jang", "ndax", "waaw", "deedeet", "ana", "nii", "dinaa",
                   "xam", "benn", "juroom", "nett", "nyaar"]
    # Fon markers
    fon_words = ["mi", "nyi", "kudo", "ka", "do", "wE", "gbE", "nado", "a ni", "daxo",
                 "alo", "azOn", "kpOn", "towe", "enyi", "e", "nukunnu", "hounnon", "avion"]
    # Yoruba markers
    yoruba_words = ["bawo", "emi", "iwo", "oun", "awa", "se", "ko", "ni", "ati", "fun",
                    "mo", "fe", "lo", "wa", "gba", "beeni", "rara", "jowo", "ekaaro",
                    "ekasan", "ekaale", "pele"]
    # Hausa markers
    hausa_words = ["ina", "yaya", "kuna", "wane", "suna", "zai", "kai", "ke", "shi", "ta",
                   "mun", "da", "zuwa", "na", "gida", "rana", "sannu", "nagode", "tashi",
                   "zo", "tafi", "jirgi"]
    # Swahili markers
    swahili_words = ["habari", "jambo", "karibu", "asante", "tafadhali", "ndio", "hapana",
                     "nataka", "kwenda", "kuruka", "ndege", "safari", "leo", "kesho",
                     "nina", "sawa", "nzuri", "bwana", "mama"]
    # French markers
    french_words = ["je", "veux", "aller", "pour", "le", "la", "un", "une", "merci",
                    "bonjour", "oui", "non", "vol", "billet", "avion", "partir", "reservation"]
    # English markers
    english_words = ["i", "want", "to", "go", "the", "a", "please", "hello", "yes", "no",
                     "flight", "ticket", "book", "travel", "departure"]

    def score(words):
        return sum(1 for w in words if f" {w} " in f" {text_lower} " or text_lower == w or text_lower.startswith(w + " "))

    scores = {
        "wo": score(wolof_words),
        "fon": score(fon_words),
        "yo": score(yoruba_words),
        "ha": score(hausa_words),
        "sw": score(swahili_words),
        "fr": score(french_words),
        "en": score(english_words),
    }

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        # No markers detected — default to French
        return "fr"
    return best
