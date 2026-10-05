import bcrypt
import hashlib
from user_agents import parse
from datetime import datetime, timezone
import asyncio
from firebase import db
from google.cloud import firestore
from cache import invalidate_cached_url


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def hash_ip(ip: str) -> str:
    """Anonymizes client IP for GDPR-safe analytics storage."""
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()[:16]


def parse_user_agent(ua_string: str) -> dict:
    user_agent = parse(ua_string or "")
    return {
        "browser": user_agent.browser.family if user_agent.browser.family else "Unknown",
        "device": user_agent.device.family if user_agent.device.family != "Other" else user_agent.os.family,
        "os": user_agent.os.family if user_agent.os.family else "Unknown",
    }


async def cleanup_expired_urls():
    """Background task to periodically delete expired URLs and invalidate cache."""
    while True:
        try:
            urls_ref = db.collection("urls")
            now_iso = datetime.utcnow().isoformat()
            
            expired_docs = urls_ref.where(filter=firestore.FieldFilter("expires_at", "<=", now_iso)).stream()
            
            batch = db.batch()
            count = 0
            for doc in expired_docs:
                code = doc.id
                batch.delete(doc.reference)
                invalidate_cached_url(code)
                count += 1
                if count % 400 == 0:
                    batch.commit()
                    batch = db.batch()
            
            if count > 0:
                batch.commit()
                print(f"[Cleanup] Cleaned up {count} expired URLs.")
        except Exception as e:
            print(f"[Cleanup] Error in cleanup task: {e}")
            
        await asyncio.sleep(60 * 60)
