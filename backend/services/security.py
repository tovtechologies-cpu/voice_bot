"""AES-256-GCM encryption for PII + rate limiting + velocity checks."""
import os
import base64
import hashlib
import logging
import time
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from database import db
from config import ENCRYPTION_KEY

logger = logging.getLogger("SecurityService")

# Derive a proper 256-bit key from the config string
def _derive_key(key_str: str) -> bytes:
    return hashlib.sha256(key_str.encode()).digest()

_aes_key = _derive_key(ENCRYPTION_KEY) if ENCRYPTION_KEY else None


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field using AES-256-GCM. Returns base64(nonce+ciphertext+tag)."""
    if not _aes_key or not plaintext:
        return plaintext
    nonce = os.urandom(12)
    aesgcm = AESGCM(_aes_key)
    ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return base64.b64encode(nonce + ct).decode('utf-8')


def decrypt_field(encrypted: str) -> str:
    """Decrypt an AES-256-GCM encrypted field."""
    if not _aes_key or not encrypted:
        return encrypted
    try:
        raw = base64.b64decode(encrypted)
        nonce = raw[:12]
        ct = raw[12:]
        aesgcm = AESGCM(_aes_key)
        return aesgcm.decrypt(nonce, ct, None).decode('utf-8')
    except Exception:
        # If decryption fails, return as-is (field might not be encrypted)
        return encrypted


def encrypt_passenger_pii(data: dict) -> dict:
    """Encrypt sensitive passenger fields before storing in MongoDB."""
    sensitive_fields = ["passportNumber", "dateOfBirth", "expiryDate"]
    encrypted = data.copy()
    for field in sensitive_fields:
        if encrypted.get(field):
            encrypted[field] = encrypt_field(str(encrypted[field]))
            encrypted[f"_{field}_encrypted"] = True
    return encrypted


def decrypt_passenger_pii(data: dict) -> dict:
    """Decrypt sensitive passenger fields when reading from MongoDB."""
    if not data:
        return data
    sensitive_fields = ["passportNumber", "dateOfBirth", "expiryDate"]
    decrypted = data.copy()
    for field in sensitive_fields:
        if decrypted.get(f"_{field}_encrypted") and decrypted.get(field):
            decrypted[field] = decrypt_field(decrypted[field])
            del decrypted[f"_{field}_encrypted"]
    return decrypted


# Rate limiting via MongoDB
RATE_LIMITS = {
    "message": {"max_requests": 30, "window_seconds": 60},
    "payment": {"max_requests": 5, "window_seconds": 300},
    "enrollment": {"max_requests": 10, "window_seconds": 600},
}


async def check_rate_limit(phone: str, action: str = "message") -> bool:
    """Check if phone is within rate limits. Returns True if allowed, False if blocked."""
    limits = RATE_LIMITS.get(action, RATE_LIMITS["message"])
    now = datetime.now(timezone.utc)
    window_start = now.timestamp() - limits["window_seconds"]

    count = await db.rate_limits.count_documents({
        "phone": phone,
        "action": action,
        "timestamp": {"$gte": window_start}
    })

    if count >= limits["max_requests"]:
        logger.warning(f"Rate limit exceeded: {phone} ({action}): {count}/{limits['max_requests']}")
        return False

    await db.rate_limits.insert_one({
        "phone": phone,
        "action": action,
        "timestamp": now.timestamp()
    })
    return True


async def check_payment_velocity(phone: str) -> bool:
    """Check for suspicious payment patterns. Returns True if OK, False if suspicious."""
    now = time.time()
    one_hour_ago = now - 3600

    # Max 3 payment attempts per hour
    recent_payments = await db.rate_limits.count_documents({
        "phone": phone,
        "action": "payment",
        "timestamp": {"$gte": one_hour_ago}
    })

    if recent_payments >= 3:
        logger.warning(f"Payment velocity alert: {phone} - {recent_payments} attempts in 1h")
        await db.security_alerts.insert_one({
            "phone": phone,
            "type": "payment_velocity",
            "count": recent_payments,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return False
    return True


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection."""
    if not text:
        return ""
    # Remove potential NoSQL injection characters
    sanitized = text.replace("$", "").replace("{", "").replace("}", "")
    # Limit length
    return sanitized[:2000]


async def cleanup_rate_limits():
    """Cleanup old rate limit entries (run periodically)."""
    cutoff = time.time() - 3600  # 1 hour
    result = await db.rate_limits.delete_many({"timestamp": {"$lt": cutoff}})
    if result.deleted_count > 0:
        logger.info(f"Cleaned up {result.deleted_count} old rate limit entries")
