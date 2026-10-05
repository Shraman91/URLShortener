import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, Any, Tuple
from fastapi import Header, HTTPException, status
from google.cloud import firestore as gcf

from firebase import db
from utils import get_password_hash, verify_password

# In-memory fast cache for authenticated API keys: key_id -> (key_data, expires_at_epoch)
_API_KEY_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes cache


def hash_secret(secret: str) -> str:
    """Computes SHA-256 digest of secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key_pair(prefix: str = "sk_live") -> Tuple[str, str, str]:
    """
    Generates a high-entropy API key.
    Format: sk_live_<key_id>.<secret>
    Returns: (full_api_key, key_id, secret_hash)
    """
    key_id = secrets.token_hex(6)  # 12-character hex ID
    secret = secrets.token_urlsafe(32)  # 43-character URL-safe string
    full_api_key = f"{prefix}_{key_id}.{secret}"
    secret_hash = hash_secret(secret)
    return full_api_key, key_id, secret_hash


async def verify_api_key(x_api_key: str = Header(None)) -> Dict[str, Any]:
    """
    Fast O(1) API key verification with in-memory caching and constant-time hashing.
    Supports new composite format: `sk_live_<key_id>.<secret>`
    Also supports backward compatibility with legacy keys.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'X-API-Key' header",
        )

    # 1. Check if key is composite `sk_..._<key_id>.<secret>`
    if "." in x_api_key and "_" in x_api_key:
        try:
            id_part, secret_part = x_api_key.split(".", 1)
            key_id = id_part.split("_")[-1]  # Extract key_id
        except Exception:
            raise HTTPException(status_code=401, detail="Malformed API key format")

        # Check in-memory fast cache
        now = time.time()
        if key_id in _API_KEY_CACHE:
            cached_data, exp = _API_KEY_CACHE[key_id]
            if now < exp:
                provided_hash = hash_secret(secret_part)
                if hmac.compare_digest(provided_hash, cached_data.get("secret_hash", "")):
                    return cached_data

        # O(1) Firestore Document Lookup
        doc_ref = db.collection("api_keys").document(key_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=401, detail="Invalid API key ID")

        key_data = doc.to_dict()
        if not key_data.get("is_active", True):
            raise HTTPException(status_code=403, detail="API key is disabled or revoked")

        # Constant-time comparison of SHA-256 hash
        stored_hash = key_data.get("secret_hash", "")
        provided_hash = hash_secret(secret_part)
        if not hmac.compare_digest(provided_hash, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid API key secret")

        # Async atomic usage increment
        doc_ref.update({"usage_count": gcf.Increment(1), "last_used_at": gcf.SERVER_TIMESTAMP})

        # Cache valid credentials in memory
        _API_KEY_CACHE[key_id] = (key_data, now + CACHE_TTL_SECONDS)
        return key_data

    # 2. Legacy fallback for old bcrypt keys (deprecated)
    keys_ref = db.collection("api_keys")
    for doc in keys_ref.stream():
        data = doc.to_dict()
        if "key_hash" in data and verify_password(x_api_key, data["key_hash"]):
            doc.reference.update({"usage_count": gcf.Increment(1)})
            return data

    raise HTTPException(status_code=401, detail="Invalid API key")
