"""Passport OCR service using pytesseract/Google Vision."""
import os
import logging
from typing import Dict, Any, Optional
import re
import httpx
from config import WHATSAPP_TOKEN, API_TIMEOUT

logger = logging.getLogger("PassportService")


def title_case_name(name: str) -> str:
    if name == name.upper() and len(name) > 1:
        return name.title()
    return name


async def download_whatsapp_image(image_id: str) -> Optional[bytes]:
    if not WHATSAPP_TOKEN or WHATSAPP_TOKEN == 'your_token_here':
        logger.warning("WhatsApp not configured - cannot download image")
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url_resp = await client.get(f"https://graph.facebook.com/v18.0/{image_id}", headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
            if url_resp.status_code != 200:
                return None
            media_url = url_resp.json().get("url")
            if not media_url:
                return None
            img_resp = await client.get(media_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
            if img_resp.status_code == 200:
                return img_resp.content
    except Exception as e:
        logger.error(f"WhatsApp image download error: {e}")
    return None


async def extract_passport_data(image_bytes: bytes) -> Dict[str, Any]:
    google_key = os.environ.get("GOOGLE_VISION_API_KEY")
    if google_key and google_key != "your_key_here":
        return await _extract_with_google_vision(image_bytes, google_key)
    return await _extract_with_tesseract(image_bytes)


async def _extract_with_google_vision(image_bytes: bytes, api_key: str) -> Dict[str, Any]:
    import base64
    try:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
                json={"requests": [{"image": {"content": encoded}, "features": [{"type": "TEXT_DETECTION"}]}]})
            if resp.status_code != 200:
                return await _extract_with_tesseract(image_bytes)
            data = resp.json()
            text = data.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("text", "")
            return _parse_mrz_from_text(text, confidence=0.9)
    except Exception as e:
        logger.error(f"Google Vision error: {e}")
        return await _extract_with_tesseract(image_bytes)


async def _extract_with_tesseract(image_bytes: bytes) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import pytesseract
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("L")
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(img, config="--psm 6")
        confidence_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in confidence_data.get("conf", []) if str(c).isdigit() and int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        return _parse_mrz_from_text(text, confidence=avg_confidence / 100.0)
    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return {"success": False, "error": str(e), "confidence": 0}


def _parse_mrz_from_text(text: str, confidence: float = 0) -> Dict[str, Any]:
    result = {"success": False, "confidence": confidence, "firstName": None, "lastName": None, "passportNumber": None, "nationality": None, "dateOfBirth": None, "expiryDate": None}
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    mrz_lines = []
    for line in lines:
        cleaned = line.replace(" ", "").replace("\u00ab", "<").replace("\u2039", "<")
        if len(cleaned) >= 30 and ("<" in cleaned or cleaned.startswith("P")):
            mrz_lines.append(cleaned)

    if len(mrz_lines) >= 2:
        line1 = mrz_lines[-2]
        line2 = mrz_lines[-1]
        if line1.startswith("P"):
            parts = line1[5:].split("<<", 1)
            if len(parts) >= 1:
                result["lastName"] = title_case_name(parts[0].replace("<", " ").strip())
            if len(parts) >= 2:
                result["firstName"] = title_case_name(parts[1].replace("<", " ").strip())
            if len(line1) >= 5:
                result["nationality"] = line1[2:5].replace("<", "")
        if len(line2) >= 28:
            pp = line2[:9].replace("<", "").strip()
            if pp and len(pp) >= 5:
                result["passportNumber"] = pp
            dob_raw = line2[13:19]
            if dob_raw.isdigit():
                yy, mm, dd = int(dob_raw[:2]), dob_raw[2:4], dob_raw[4:6]
                year = 1900 + yy if yy > 30 else 2000 + yy
                result["dateOfBirth"] = f"{year}-{mm}-{dd}"
            exp_raw = line2[21:27]
            if exp_raw.isdigit():
                yy, mm, dd = int(exp_raw[:2]), exp_raw[2:4], exp_raw[4:6]
                year = 2000 + yy
                result["expiryDate"] = f"{year}-{mm}-{dd}"

    has_name = bool(result["firstName"] or result["lastName"])
    result["success"] = has_name
    result["partial"] = has_name and not result["passportNumber"]
    return result
