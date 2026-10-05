import os
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, HTTPException, Request, Depends, Header, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.cloud import firestore as gcf
from firebase_admin import auth
import qrcode

from firebase import db
from models import (
    URLCreate, URLResponse, URLDetailedResponse, ClickStats,
    URLListResponse, VerifyPasswordRequest, BulkShortenRequest,
    BulkShortenResponse, APIKeyResponse, APIKeyCreateRequest,
    APIKeyCreatedResponse, SystemHealthResponse
)
from utils import (
    get_password_hash, verify_password, parse_user_agent, cleanup_expired_urls, hash_ip
)
from rate_limiter import (
    rate_limiter, get_client_ip, _redis_available as rate_limiter_redis_available
)
from cache import (
    get_cached_url, set_cached_url, invalidate_cached_url,
    is_known_nonexistent, set_nonexistent, _redis_available as cache_redis_available
)
from keygen import generate_short_code, is_valid_alias
from analytics_queue import analytics_queue
from auth_service import verify_api_key, generate_api_key_pair, hash_secret

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BLOCKLIST = ["malicious.com", "phishing.net", "virus-download.org"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start async analytics queue worker & background cleanup
    analytics_queue.start()
    cleanup_task = asyncio.create_task(cleanup_expired_urls())
    yield
    # Shutdown: Flush pending analytics batches and cancel cleanup
    cleanup_task.cancel()
    await analytics_queue.stop()


app = FastAPI(
    title="High-Scale URL Shortener API",
    description="Production-grade URL shortening engine with multi-tier rate limiting, caching, and async analytics",
    version="2.0.0",
    lifespan=lifespan
)

# Global CORS Configuration
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
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After"],
)


@app.middleware("http")
async def rate_limit_header_middleware(request: Request, call_next):
    """Injects standard rate limit headers into all HTTP responses."""
    response = await call_next(request)
    headers_to_inject = getattr(request.state, "rate_limit_headers", None)
    if headers_to_inject:
        for k, v in headers_to_inject.items():
            response.headers[k] = v
    return response


security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Optional authentication: extracts user UID if valid Firebase token is present."""
    if credentials:
        try:
            token = credentials.credentials
            decoded_token = auth.verify_id_token(token)
            return decoded_token.get('uid')
        except Exception:
            pass
    return None


async def get_current_user_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Strict authentication dependency."""
    uid = await get_current_user(credentials)
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token required")
    return uid


def _check_blocklist(url: str):
    url_lower = url.lower()
    for blocked in BLOCKLIST:
        if blocked in url_lower:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Destination URL is blocked for security reasons")


# ==========================================
# 1. CORE URL SHORTENING (WRITE PATH)
# ==========================================
@app.post("/api/shorten", response_model=URLResponse)
async def shorten_url(
    request: Request,
    payload: URLCreate,
    current_user: str = Depends(get_current_user),
    _=Depends(rate_limiter("shorten"))
):
    request.state.user_uid = current_user
    _check_blocklist(str(payload.long_url))

    urls_ref = db.collection("urls")

    if payload.custom_alias:
        if not is_valid_alias(payload.custom_alias):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom alias must be 3-30 alphanumeric characters, underscores, or hyphens."
            )
        code = payload.custom_alias
        # Check cache / DB for alias collision
        if get_cached_url(code) or urls_ref.document(code).get().exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Custom alias is already in use")
    else:
        # High-performance collision-free distributed Snowflake key generation
        code = generate_short_code()

    doc_data = {
        "long_url": str(payload.long_url),
        "created_at": datetime.utcnow().isoformat(),
        "clicks": 0,
        "owner_uid": current_user,
        "is_password_protected": bool(payload.password),
    }

    if payload.password:
        doc_data["password_hash"] = get_password_hash(payload.password)
    if payload.expires_at:
        doc_data["expires_at"] = payload.expires_at.isoformat()
    if payload.max_clicks is not None:
        doc_data["max_clicks"] = payload.max_clicks

    # Write to Firestore and populate cache immediately
    urls_ref.document(code).set(doc_data)
    set_cached_url(code, doc_data)

    return URLResponse(
        short_code=code,
        short_url=f"{BASE_URL}/{code}",
        long_url=str(payload.long_url),
    )


# ==========================================
# 2. HIGH-THROUGHPUT REDIRECT (READ PATH)
# ==========================================
@app.get("/{code}")
async def redirect_url(
    code: str,
    request: Request,
    _=Depends(rate_limiter("redirect"))
):
    # 1. Fast Negative Cache check (avoids DB hammering on spam/404s)
    if is_known_nonexistent(code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")

    # 2. L1/L2 Cache lookup (<2ms response)
    data = get_cached_url(code)
    if not data:
        doc = db.collection("urls").document(code).get()
        if not doc.exists:
            set_nonexistent(code)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")
        data = doc.to_dict()
        set_cached_url(code, data)

    # 3. Check expiration
    if data.get("expires_at"):
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            return RedirectResponse(url=f"{FRONTEND_URL}/expired?code={code}&reason=time", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # 4. Check max click limits
    if data.get("max_clicks") is not None:
        if data.get("clicks", 0) >= data["max_clicks"]:
            return RedirectResponse(url=f"{FRONTEND_URL}/expired?code={code}&reason=clicks", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # 5. Password protection check
    if data.get("is_password_protected"):
        return RedirectResponse(url=f"{FRONTEND_URL}/{code}/password", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # 6. Asynchronously queue analytics event (non-blocking, zero wait for Firestore)
    client_ip = get_client_ip(request)
    ua_info = parse_user_agent(request.headers.get("user-agent", ""))
    analytics_queue.enqueue({
        "code": code,
        "timestamp": datetime.utcnow().isoformat(),
        "referrer": request.headers.get("referer", "Direct"),
        "browser": ua_info["browser"],
        "device": ua_info["device"],
        "os": ua_info["os"],
        "ip_hash": hash_ip(client_ip)
    })

    # 7. Return immediate HTTP 307 temporary redirect
    return RedirectResponse(url=data["long_url"], status_code=status.HTTP_307_TEMPORARY_REDIRECT)


# ==========================================
# 3. PASSWORD VERIFICATION (BRUTE FORCE PROTECTED)
# ==========================================
@app.post("/api/verify/{code}")
async def verify_url_password(
    code: str,
    request: Request,
    payload: VerifyPasswordRequest,
    _=Depends(rate_limiter("verify"))
):
    data = get_cached_url(code)
    if not data:
        doc = db.collection("urls").document(code).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Short URL not found")
        data = doc.to_dict()
        set_cached_url(code, data)

    if data.get("expires_at"):
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status.HTTP_410_GONE, detail="Link expired")

    if data.get("max_clicks") is not None and data.get("clicks", 0) >= data["max_clicks"]:
        raise HTTPException(status.HTTP_410_GONE, detail="Link reached maximum click limit")

    if not data.get("is_password_protected") or verify_password(payload.password, data.get("password_hash", "")):
        client_ip = get_client_ip(request)
        ua_info = parse_user_agent(request.headers.get("user-agent", ""))
        analytics_queue.enqueue({
            "code": code,
            "timestamp": datetime.utcnow().isoformat(),
            "referrer": request.headers.get("referer", "Direct"),
            "browser": ua_info["browser"],
            "device": ua_info["device"],
            "os": ua_info["os"],
            "ip_hash": hash_ip(client_ip)
        })
        return {"url": data["long_url"]}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")


# ==========================================
# 4. QR CODE GENERATION
# ==========================================
@app.get("/api/qr/{code}")
async def get_qr_code(
    code: str,
    _=Depends(rate_limiter("qr"))
):
    url = f"{BASE_URL}/{code}"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")


# ==========================================
# 5. ANALYTICS & STATS
# ==========================================
@app.get("/api/stats/{code}/detailed", response_model=ClickStats)
async def get_stats_detailed(
    code: str,
    _=Depends(rate_limiter("general"))
):
    doc = db.collection("urls").document(code).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Short URL not found")

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


# ==========================================
# 6. PUBLIC COMMUNITY & USER URL MANAGEMENT
# ==========================================
@app.get("/api/public-links", response_model=URLListResponse)
async def get_public_links(
    limit: int = 50,
    _=Depends(rate_limiter("general"))
):
    """
    Public community feed endpoint: Returns recent shortened links.
    Accessible to all users (both guests and authenticated users).
    Password-protected links are marked accordingly and will prompt for password upon opening.
    """
    try:
        urls_ref = db.collection("urls").order_by("created_at", direction=gcf.Query.DESCENDING).limit(min(limit, 100))
        docs = list(urls_ref.stream())
    except Exception:
        # Fallback if created_at order index is missing
        docs = list(db.collection("urls").limit(min(limit, 100)).stream())

    urls = []
    for doc in docs:
        data = doc.to_dict()
        urls.append(URLDetailedResponse(
            short_code=doc.id,
            long_url=data.get("long_url", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            clicks=data.get("clicks", 0),
            expires_at=data.get("expires_at"),
            max_clicks=data.get("max_clicks"),
            is_password_protected=data.get("is_password_protected", False),
            owner_uid=data.get("owner_uid")
        ))
    return URLListResponse(urls=urls)


@app.get("/api/my-urls", response_model=URLListResponse)
async def get_my_urls(
    current_user: str = Depends(get_current_user_required),
    _=Depends(rate_limiter("general"))
):
    urls_ref = db.collection("urls").where(filter=gcf.FieldFilter("owner_uid", "==", current_user))
    docs = urls_ref.stream()
    urls = []
    for doc in docs:
        data = doc.to_dict()
        urls.append(URLDetailedResponse(
            short_code=doc.id,
            long_url=data["long_url"],
            created_at=data["created_at"],
            clicks=data.get("clicks", 0),
            expires_at=data.get("expires_at"),
            max_clicks=data.get("max_clicks"),
            is_password_protected=data.get("is_password_protected", False),
            owner_uid=data.get("owner_uid")
        ))
    return URLListResponse(urls=urls)


@app.delete("/api/urls/{code}")
async def delete_url(
    code: str,
    current_user: str = Depends(get_current_user_required)
):
    doc_ref = db.collection("urls").document(code)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Short URL not found")

    if doc.to_dict().get("owner_uid") != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to delete this URL")

    doc_ref.delete()
    invalidate_cached_url(code)
    return {"message": "Deleted successfully"}


# ==========================================
# 7. DEVELOPER API KEYS & BULK OPERATIONS
# ==========================================
@app.post("/api/keys/generate", response_model=APIKeyCreatedResponse)
async def create_api_key(
    payload: APIKeyCreateRequest,
    current_user: str = Depends(get_current_user_required)
):
    """Generates a new secure API Key with O(1) verification support."""
    tier = payload.tier.lower() if payload.tier in ["basic", "pro", "enterprise"] else "basic"
    full_api_key, key_id, secret_hash = generate_api_key_pair()

    created_at = datetime.utcnow().isoformat()
    doc_data = {
        "key_id": key_id,
        "secret_hash": secret_hash,
        "owner_uid": current_user,
        "rate_limit_tier": tier,
        "name": payload.name,
        "usage_count": 0,
        "created_at": created_at,
        "is_active": True,
    }

    db.collection("api_keys").document(key_id).set(doc_data)

    return APIKeyCreatedResponse(
        api_key=full_api_key,
        key_id=key_id,
        name=payload.name,
        rate_limit_tier=tier,
        created_at=created_at
    )


@app.post("/api/bulk-shorten", response_model=BulkShortenResponse)
async def bulk_shorten(
    request: Request,
    payload: BulkShortenRequest,
    api_key_data: dict = Depends(verify_api_key),
    _=Depends(rate_limiter("bulk"))
):
    request.state.api_key_data = api_key_data
    urls_ref = db.collection("urls")
    results = []
    batch = db.batch()

    for long_url in payload.long_urls:
        _check_blocklist(str(long_url))
        code = generate_short_code()

        doc_ref = urls_ref.document(code)
        doc_data = {
            "long_url": str(long_url),
            "created_at": datetime.utcnow().isoformat(),
            "clicks": 0,
            "owner_uid": api_key_data.get("owner_uid"),
            "is_password_protected": False,
        }
        batch.set(doc_ref, doc_data)
        set_cached_url(code, doc_data)
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
        key_id=api_key_data.get("key_id"),
        key_hash=api_key_data.get("secret_hash") or api_key_data.get("key_hash", ""),
        owner_uid=api_key_data.get("owner_uid", ""),
        usage_count=api_key_data.get("usage_count", 0),
        rate_limit_tier=api_key_data.get("rate_limit_tier", "basic"),
        name=api_key_data.get("name", "API Key")
    )


# ==========================================
# 8. SYSTEM HEALTH & MONITORING
# ==========================================
@app.get("/api/health", response_model=SystemHealthResponse)
async def system_health():
    """Observability endpoint reporting cache and rate limiter backends."""
    return SystemHealthResponse(
        status="healthy",
        cache_backend="Redis" if cache_redis_available else "InMemory-LRU",
        rate_limiter_backend="Redis-Sliding-Window" if rate_limiter_redis_available else "InMemory-Sliding-Window",
        analytics_queue_size=analytics_queue._queue.qsize(),
        timestamp=datetime.utcnow().isoformat()
    )
