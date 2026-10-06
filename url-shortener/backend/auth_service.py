import hashlib
import hmac
import secrets
import time
import asyncio
from typing import Optional, Dict, Any, Tuple
from fastapi import Header, HTTPException, status
from google.cloud import firestore as gcf

from firebase import db
from utils import verify_password

_API_KEY_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
CACHE_TTL_SECONDS = 300


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key_pair(prefix: str = "sk_live") -> Tuple[str, str, str]:
    key_id = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    full_api_key = f"{prefix}_{key_id}.{secret}"
    secret_hash = hash_secret(secret)
    return full_api_key, key_id, secret_hash


def invalidate_api_key_cache(key_id: str):
    _API_KEY_CACHE.pop(key_id, None)


async def verify_api_key(x_api_key: str = Header(None)) -> Dict[str, Any]:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'X-API-Key' header",
        )

    if "." in x_api_key and "_" in x_api_key:
        try:
            id_part, secret_part = x_api_key.split(".", 1)
            key_id = id_part.split("_")[-1]
        except Exception:
            raise HTTPException(status_code=401, detail="Malformed API key format")

        now = time.time()
        if key_id in _API_KEY_CACHE:
            cached_data, exp = _API_KEY_CACHE[key_id]
            if now < exp:
                provided_hash = hash_secret(secret_part)
                if hmac.compare_digest(provided_hash, cached_data.get("secret_hash", "")):
                    return cached_data

        doc_ref = db.collection("api_keys").document(key_id)
        doc = await asyncio.to_thread(doc_ref.get)

        if not doc.exists:
            raise HTTPException(status_code=401, detail="Invalid API key ID")

        key_data = doc.to_dict()
        if not key_data.get("is_active", True):
            raise HTTPException(status_code=403, detail="API key is disabled or revoked")

        stored_hash = key_data.get("secret_hash", "")
        provided_hash = hash_secret(secret_part)
        if not hmac.compare_digest(provided_hash, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid API key secret")

        await asyncio.to_thread(doc_ref.update, {
            "usage_count": gcf.Increment(1),
            "last_used_at": gcf.SERVER_TIMESTAMP
        })

        _API_KEY_CACHE[key_id] = (key_data, now + CACHE_TTL_SECONDS)
        return key_data

    def _verify_legacy():
        keys_ref = db.collection("api_keys")
        for doc in keys_ref.stream():
            data = doc.to_dict()
            if "key_hash" in data and verify_password(x_api_key, data["key_hash"]):
                doc.reference.update({"usage_count": gcf.Increment(1)})
                return data
        return None

    legacy_data = await asyncio.to_thread(_verify_legacy)
    if legacy_data:
        return legacy_data

    raise HTTPException(status_code=401, detail="Invalid API key")
