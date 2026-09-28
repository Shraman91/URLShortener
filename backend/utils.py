import bcrypt
from user_agents import parse
from datetime import datetime, timezone
import asyncio
from firebase import db
from google.cloud import firestore


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def parse_user_agent(ua_string: str) -> dict:
    user_agent = parse(ua_string)
    return {
        "browser": user_agent.browser.family,
        "device": user_agent.device.family if user_agent.device.family != "Other" else user_agent.os.family,
        "os": user_agent.os.family,
    }


async def cleanup_expired_urls():
    """Background task to periodically delete expired URLs."""
    while True:
        try:
            urls_ref = db.collection("urls")
            now_iso = datetime.utcnow().isoformat()
            
            expired_docs = urls_ref.where(filter=firestore.FieldFilter("expires_at", "<=", now_iso)).stream()
            
            batch = db.batch()
            count = 0
            for doc in expired_docs:
                batch.delete(doc.reference)
                count += 1
            
            if count > 0:
                batch.commit()
                print(f"Cleaned up {count} expired URLs.")
        except Exception as e:
            print(f"Error in cleanup task: {e}")
            
        await asyncio.sleep(60 * 60) 
