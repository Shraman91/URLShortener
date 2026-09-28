import string
import random
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import base64
from io import BytesIO

from fastapi import FastAPI, HTTPException, Request, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.cloud import firestore as gcf
from firebase_admin import auth
import qrcode
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from firebase import db
from models import (
    URLCreate, URLResponse, URLDetailedResponse, ClickStats,
    URLListResponse, VerifyPasswordRequest, BulkShortenRequest,
    BulkShortenResponse, APIKeyResponse
)
from utils import (
    get_password_hash, verify_password, parse_user_agent, cleanup_expired_urls
)

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_expired_urls())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://your-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "http://localhost:8000"
ALPHABET = string.ascii_letters + string.digits
BLOCKLIST = ["malicious.com", "phishing.net"]

security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials:
        try:
            token = credentials.credentials
            decoded_token = auth.verify_id_token(token)
            return decoded_token['uid']
        except Exception as e:
            pass
    return None


async def get_current_user_required(credentials: HTTPAuthorizationCredentials = Depends(security)):
    uid = await get_current_user(credentials)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    return uid


async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")
    keys_ref = db.collection("api_keys")
    docs = keys_ref.stream()
    for doc in docs:
        key_data = doc.to_dict()
        if verify_password(x_api_key, key_data.get("key_hash", "")):
            doc.reference.update({"usage_count": gcf.Increment(1)})
            return key_data
    raise HTTPException(status_code=401, detail="Invalid API Key")

def generate_code(length: int = 6) -> str:
    return "".join(random.choices(ALPHABET, k=length))


def _check_blocklist(url: str):
    for blocked in BLOCKLIST:
        if blocked in url:
            raise HTTPException(400, "URL is blocked")

@app.post("/api/shorten", response_model=URLResponse)
@limiter.limit("60/minute")
async def shorten_url(request: Request, payload: URLCreate, current_user: str = Depends(get_current_user)):
    request.state.user_uid = current_user
    _check_blocklist(str(payload.long_url))
    
    urls_ref = db.collection("urls")

    if payload.custom_alias:
        code = payload.custom_alias
        if urls_ref.document(code).get().exists:
            raise HTTPException(400, "Alias already taken")
    else:
        for _ in range(5):
            code = generate_code()
            if not urls_ref.document(code).get().exists:
                break
        else:
            raise HTTPException(500, "Could not generate unique code")

    doc_data = {
        "long_url": str(payload.long_url),
        "created_at": datetime.utcnow().isoformat(),
        "clicks": 0,
        "owner_uid": current_user,
    }
    
    if payload.password:
        doc_data["password_hash"] = get_password_hash(payload.password)
        doc_data["is_password_protected"] = True
    else:
        doc_data["is_password_protected"] = False
        
    if payload.expires_at:
        doc_data["expires_at"] = payload.expires_at.isoformat()
    if payload.max_clicks is not None:
        doc_data["max_clicks"] = payload.max_clicks

    urls_ref.document(code).set(doc_data)

    return URLResponse(
        short_code=code,
        short_url=f"{BASE_URL}/{code}",
        long_url=str(payload.long_url),
    )


def record_click(doc_ref, request: Request):
    referrer = request.headers.get("referer", "Direct")
    user_agent = request.headers.get("user-agent", "")
    parsed_ua = parse_user_agent(user_agent)
    
    click_ref = doc_ref.collection("clicks").document()
    click_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "referrer": referrer,
        "browser": parsed_ua["browser"],
        "device": parsed_ua["device"],
        "os": parsed_ua["os"]
    }
    
    batch = db.batch()
    batch.update(doc_ref, {"clicks": gcf.Increment(1)})
    batch.set(click_ref, click_data)
    batch.commit()


@app.get("/{code}")
async def redirect_url(code: str, request: Request):
    doc_ref = db.collection("urls").document(code)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(404, "Short URL not found")

    data = doc.to_dict()
    
    if "expires_at" in data and data["expires_at"]:
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            return RedirectResponse(url=f"http://localhost:3000/expired?code={code}&reason=time")
            
    if "max_clicks" in data and data["max_clicks"] is not None:
        if data.get("clicks", 0) >= data["max_clicks"]:
            return RedirectResponse(url=f"http://localhost:3000/expired?code={code}&reason=clicks")
            
    if data.get("is_password_protected"):
        return RedirectResponse(url=f"http://localhost:3000/{code}/password")

    record_click(doc_ref, request)

    return RedirectResponse(url=data["long_url"])


@app.post("/api/verify/{code}")
async def verify_url_password(code: str, request: Request, payload: VerifyPasswordRequest):
    doc_ref = db.collection("urls").document(code)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(404, "Short URL not found")
        
    data = doc.to_dict()

    if "expires_at" in data and data["expires_at"]:
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status.HTTP_410_GONE, "Link expired")
            
    if "max_clicks" in data and data["max_clicks"] is not None:
        if data.get("clicks", 0) >= data["max_clicks"]:
            raise HTTPException(status.HTTP_410_GONE, "Link expired")

    if not data.get("is_password_protected"):
        record_click(doc_ref, request)
        return {"url": data["long_url"]}
        
    if verify_password(payload.password, data.get("password_hash", "")):
        record_click(doc_ref, request)
        return {"url": data["long_url"]}
    
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")


@app.get("/api/stats/{code}/detailed", response_model=ClickStats)
async def get_stats_detailed(code: str):
    doc = db.collection("urls").document(code).get()
    if not doc.exists:
        raise HTTPException(404, "Not found")
        
    clicks_ref = db.collection("urls").document(code).collection("clicks")
    clicks = clicks_ref.stream()
    
    total_clicks = 0
    clicks_per_day = {}
    top_referrers = {}
    top_browsers = {}
    top_devices = {}
    
    for click_doc in clicks:
        click = click_doc.to_dict()
        total_clicks += 1
        
        day = click["timestamp"][:10]
        clicks_per_day[day] = clicks_per_day.get(day, 0) + 1

        ref = click.get("referrer", "Direct")
        top_referrers[ref] = top_referrers.get(ref, 0) + 1
        
        browser = click.get("browser", "Unknown")
        top_browsers[browser] = top_browsers.get(browser, 0) + 1
        
        device = click.get("device", "Unknown")
        top_devices[device] = top_devices.get(device, 0) + 1
        
    return ClickStats(
        total_clicks=total_clicks,
        clicks_per_day=clicks_per_day,
        top_referrers=top_referrers,
        top_browsers=top_browsers,
        top_devices=top_devices
    )

@app.get("/api/my-urls", response_model=URLListResponse)
async def get_my_urls(current_user: str = Depends(get_current_user_required)):
    urls_ref = db.collection("urls").where(filter=gcf.FieldFilter("owner_uid", "==", current_user))
    docs = urls_ref.stream()
    urls = []
    for doc in docs:
        data = doc.to_dict()
        urls.append(URLDetailedResponse(
            short_code=doc.id,
            long_url=data["long_url"],
            created_at=data["created_at"],
            clicks=data["clicks"],
            expires_at=data.get("expires_at"),
            max_clicks=data.get("max_clicks"),
            is_password_protected=data.get("is_password_protected", False),
            owner_uid=data.get("owner_uid")
        ))
    return URLListResponse(urls=urls)

@app.delete("/api/urls/{code}")
async def delete_url(code: str, current_user: str = Depends(get_current_user_required)):
    doc_ref = db.collection("urls").document(code)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(404, "Not found")
        
    if doc.to_dict().get("owner_uid") != current_user:
        raise HTTPException(403, "Not authorized to delete this URL")
        
    doc_ref.delete()
    return {"message": "Deleted successfully"}

@app.get("/api/qr/{code}")
async def get_qr_code(code: str):
    url = f"{BASE_URL}/{code}"
    img = qrcode.make(url)
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return Response(content=buf.getvalue(), media_type="image/png")

@app.post("/api/bulk-shorten", response_model=BulkShortenResponse)
async def bulk_shorten(payload: BulkShortenRequest, api_key_data: dict = Depends(verify_api_key)):
    urls_ref = db.collection("urls")
    results = []
    batch = db.batch()
    
    for long_url in payload.long_urls:
        _check_blocklist(str(long_url))
        
        for _ in range(5):
            code = generate_code()
            if not urls_ref.document(code).get().exists:
                break
        else:
            continue 
            
        doc_ref = urls_ref.document(code)
        doc_data = {
            "long_url": str(long_url),
            "created_at": datetime.utcnow().isoformat(),
            "clicks": 0,
            "owner_uid": api_key_data.get("owner_uid"),
            "is_password_protected": False,
        }
        batch.set(doc_ref, doc_data)
        results.append(URLResponse(
            short_code=code,
            short_url=f"{BASE_URL}/{code}",
            long_url=str(long_url)
        ))
        
    batch.commit()
    return BulkShortenResponse(shortened_urls=results)

@app.get("/api/usage", response_model=APIKeyResponse)
async def get_api_usage(api_key_data: dict = Depends(verify_api_key)):
    return APIKeyResponse(
        key_hash=api_key_data.get("key_hash", ""),
        owner_uid=api_key_data.get("owner_uid", ""),
        usage_count=api_key_data.get("usage_count", 0),
        rate_limit_tier=api_key_data.get("rate_limit_tier", "basic")
    )
