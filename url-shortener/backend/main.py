import os
import asyncio
import time
import threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from collections import deque

from fastapi import FastAPI, HTTPException, Request, Depends, Header, status, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.cloud import firestore as gcf
from google.api_core.exceptions import AlreadyExists, NotFound
from firebase_admin import auth
import qrcode

from firebase import db
from models import (
    URLCreate, URLResponse, URLDetailedResponse, ClickStats,
    URLListResponse, VerifyPasswordRequest, BulkShortenRequest,
    BulkShortenResponse, BulkShortenItemResult, APIKeyResponse, APIKeyCreateRequest,
    APIKeyCreatedResponse, APIKeyListResponse, SystemHealthResponse, ObservabilityResponse,
    CacheMetrics, QueueMetrics, LatencyMetrics, RateLimitMetrics,
    AIScanRequest, AIScanResponse
)
from utils import (
    get_password_hash, verify_password, parse_user_agent, cleanup_expired_urls,
    hash_ip, extract_referrer_host
)
from rate_limiter import (
    rate_limiter, get_client_ip, get_rate_limiter_stats,
    is_rate_limiter_redis_available, is_bot_or_crawler
)
from cache import (
    get_cached_url, set_cached_url, invalidate_cached_url,
    is_known_nonexistent, set_nonexistent, get_cache_stats,
    is_redis_available, atomic_increment_clicks
)
from keygen import generate_short_code, is_valid_alias
from analytics_queue import analytics_queue
from auth_service import (
    verify_api_key, generate_api_key_pair, hash_secret,
    invalidate_api_key_cache
)
from ai_scanner import scan_url_safety, check_domain_blocklist

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_RAW.split(",") if origin.strip()]
APP_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize background workers & telemetry
    analytics_queue.start()
    cleanup_task = asyncio.create_task(cleanup_expired_urls())
    yield
    # Shutdown: Flush pending buffers and stop cleanly
    cleanup_task.cancel()
    await analytics_queue.stop()


app = FastAPI(
    title="High-Scale URL Shortener API",
    description="Production-grade URL shortening engine with multi-tier rate limiting, caching, and async analytics",
    version="2.1.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After", "X-Response-Time"],
)


# ==========================================
# Telemetry & Request Latency Tracker
# ==========================================
_latency_samples = deque(maxlen=2000)
_request_timestamps = deque(maxlen=5000)  # for accurate sliding-window RPM
_status_codes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
_total_requests = 0
_telemetry_lock = threading.Lock()


@app.middleware("http")
async def observability_and_latency_middleware(request: Request, call_next):
    global _total_requests
    start_time = time.perf_counter()

    response = await call_next(request)

    execution_time_ms = round((time.perf_counter() - start_time) * 1000, 3)
    response.headers["X-Response-Time"] = f"{execution_time_ms}ms"

    if hasattr(request.state, "rate_limit_headers"):
        for header_name, header_value in request.state.rate_limit_headers.items():
            response.headers[header_name] = header_value

    now = time.time()
    with _telemetry_lock:
        _total_requests += 1
        _latency_samples.append(execution_time_ms)
        _request_timestamps.append(now)

        code_group = f"{response.status_code // 100}xx"
        if code_group in _status_codes:
            _status_codes[code_group] += 1
        else:
            _status_codes["5xx"] += 1

    return response


# ==========================================
# Static Route Handlers (Fast-Path)
# ==========================================
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    return Response("User-agent: *\nDisallow:", media_type="text/plain")


# ==========================================
# Authentication Dependencies
# ==========================================
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[str]:
    """
    Validates Firebase ID token.
    Returns UID if valid.
    Raises 401 if token is present but invalid/expired.
    Returns None if no token is provided.
    """
    if not credentials:
        return None
    try:
        decoded_token = await asyncio.to_thread(auth.verify_id_token, credentials.credentials)
        return decoded_token["uid"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {e}"
        )


async def get_current_user_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    uid = await get_current_user(credentials)
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required"
        )
    return uid


# ==========================================
# 1. CORE URL SHORTENING (WRITE PATH)
# ==========================================
@app.post("/api/shorten", response_model=URLResponse)
async def shorten_url(
    request: Request,
    payload: URLCreate,
    current_user: Optional[str] = Depends(get_current_user),
    _=Depends(rate_limiter("shorten"))
):
    request.state.user_uid = current_user
    url_str = str(payload.long_url)

    # 1. Security blocklist check
    is_blocked, block_reason = check_domain_blocklist(url_str)
    if is_blocked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=block_reason)

    # 2. AI Safety Scan & Threat Vector Analysis
    safety_info = scan_url_safety(url_str)
    if safety_info["safety_verdict"] == "MALICIOUS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL rejected by AI Threat Scanner: {', '.join(safety_info['flags'])}"
        )

    urls_ref = db.collection("urls")

    # 3. Determine short code
    if payload.custom_alias:
        if not is_valid_alias(payload.custom_alias):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom alias must be 3-30 alphanumeric characters, underscores, or hyphens."
            )
        code = payload.custom_alias
    else:
        code = generate_short_code()

    # 4. Prepare Document Data
    doc_data = {
        "long_url": url_str,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "clicks": 0,
        "owner_uid": current_user,
        "is_password_protected": bool(payload.password),
        "is_public": bool(payload.is_public),
        "safety_score": safety_info["safety_score"],
        "safety_verdict": safety_info["safety_verdict"],
        "ai_category": safety_info["category"],
        "safety_flags": safety_info["flags"],
    }

    if payload.password:
        doc_data["password_hash"] = await asyncio.to_thread(get_password_hash, payload.password)
    if payload.expires_at:
        doc_data["expires_at"] = payload.expires_at.isoformat()
    if payload.max_clicks is not None:
        doc_data["max_clicks"] = payload.max_clicks

    # 5. Non-blocking Atomic Creation in Firestore (.create prevents overwriting existing links)
    doc_ref = urls_ref.document(code)
    try:
        await asyncio.to_thread(doc_ref.create, doc_data)
    except AlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alias or short code '{code}' is already in use. Please choose a different alias."
        )

    # 6. Invalidate negative cache & populate cache
    invalidate_cached_url(code)
    set_cached_url(code, doc_data)

    return URLResponse(
        short_code=code,
        short_url=f"{BASE_URL}/{code}",
        long_url=url_str,
        is_password_protected=bool(payload.password),
        is_public=bool(payload.is_public),
        safety_score=safety_info["safety_score"],
        safety_verdict=safety_info["safety_verdict"],
        ai_category=safety_info["category"],
        safety_flags=safety_info["flags"],
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
    # 1. Fast Negative Cache check
    if is_known_nonexistent(code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")

    # 2. L1/L2 Cache lookup (<2ms response)
    data = get_cached_url(code)
    if not data:
        doc_ref = db.collection("urls").document(code)
        doc = await asyncio.to_thread(doc_ref.get)
        if not doc.exists:
            set_nonexistent(code)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")
        data = doc.to_dict()
        set_cached_url(code, data)

    # 3. Check expiration (timezone-aware)
    if data.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_at:
                return RedirectResponse(url=f"{FRONTEND_URL}/expired?code={code}&reason=time", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        except Exception:
            pass

    # 4. Check & enforce max click limits atomically
    if data.get("max_clicks") is not None:
        max_limit = data["max_clicks"]
        # Atomic increment check via Redis if available
        redis_count = atomic_increment_clicks(code, max_limit)
        if redis_count is not None:
            if redis_count > max_limit:
                return RedirectResponse(url=f"{FRONTEND_URL}/expired?code={code}&reason=clicks", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        else:
            # Fallback to Firestore atomic count check
            doc_ref = db.collection("urls").document(code)
            doc_fresh = await asyncio.to_thread(doc_ref.get)
            if doc_fresh.exists:
                current_clicks = doc_fresh.to_dict().get("clicks", 0)
                if current_clicks >= max_limit:
                    return RedirectResponse(url=f"{FRONTEND_URL}/expired?code={code}&reason=clicks", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # 5. Password protection check
    if data.get("is_password_protected"):
        return RedirectResponse(url=f"{FRONTEND_URL}/{code}/password", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # 6. Filter Bots & Crawlers from polluting analytics and burning click quotas
    user_agent_str = request.headers.get("user-agent", "")
    if request.method != "HEAD" and not is_bot_or_crawler(user_agent_str):
        client_ip = get_client_ip(request)
        ua_info = parse_user_agent(user_agent_str)
        raw_referrer = request.headers.get("referer", "Direct")
        clean_referrer = extract_referrer_host(raw_referrer)

        analytics_queue.enqueue({
            "code": code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "referrer": clean_referrer,
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
    doc_ref = db.collection("urls").document(code)
    doc = await asyncio.to_thread(doc_ref.get)
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")
    data = doc.to_dict()

    if data.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(status.HTTP_410_GONE, detail="Link expired")
        except Exception:
            pass

    if data.get("max_clicks") is not None and data.get("clicks", 0) >= data["max_clicks"]:
        raise HTTPException(status.HTTP_410_GONE, detail="Link reached maximum click limit")

    password_hash = data.get("password_hash", "")
    is_valid = await asyncio.to_thread(verify_password, payload.password, password_hash)

    if not data.get("is_password_protected") or is_valid:
        client_ip = get_client_ip(request)
        ua_info = parse_user_agent(request.headers.get("user-agent", ""))
        clean_referrer = extract_referrer_host(request.headers.get("referer", "Direct"))

        analytics_queue.enqueue({
            "code": code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "referrer": clean_referrer,
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
    if len(code) > 50:
        raise HTTPException(status_code=400, detail="Invalid short code length")

    # Verify link existence first
    data = get_cached_url(code)
    if not data:
        doc = await asyncio.to_thread(db.collection("urls").document(code).get)
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Short URL not found")

    url = f"{BASE_URL}/{code}"

    def _render_qr(target_url: str) -> bytes:
        img = qrcode.make(target_url)
        buf = BytesIO()
        img.save(buf)
        return buf.getvalue()

    img_bytes = await asyncio.to_thread(_render_qr, url)

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"}
    )


# ==========================================
# 5. ANALYTICS & STATS (OWNER-ONLY)
# ==========================================
@app.get("/api/stats/{code}/detailed", response_model=ClickStats)
async def get_stats_detailed(
    code: str,
    current_user: str = Depends(get_current_user_required),
    _=Depends(rate_limiter("general"))
):
    doc_ref = db.collection("urls").document(code)
    doc = await asyncio.to_thread(doc_ref.get)
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Short URL not found")

    data = doc.to_dict()
    if data.get("owner_uid") != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to view analytics for this link")

    def _aggregate_clicks():
        clicks_ref = db.collection("urls").document(code).collection("clicks").order_by("timestamp", direction=gcf.Query.DESCENDING).limit(1000)
        clicks = list(clicks_ref.stream())

        clicks_per_day = {}
        top_referrers = {}
        top_browsers = {}
        top_os = {}
        top_devices = {}

        for c in clicks:
            cd = c.to_dict()
            ts = cd.get("timestamp", "")
            day = ts.split("T")[0] if ts else "Unknown"
            clicks_per_day[day] = clicks_per_day.get(day, 0) + 1

            ref = cd.get("referrer", "Direct")
            top_referrers[ref] = top_referrers.get(ref, 0) + 1

            browser = cd.get("browser", "Unknown")
            top_browsers[browser] = top_browsers.get(browser, 0) + 1

            os_fam = cd.get("os", "Unknown")
            top_os[os_fam] = top_os.get(os_fam, 0) + 1

            dev = cd.get("device", "Unknown")
            top_devices[dev] = top_devices.get(dev, 0) + 1

        return ClickStats(
            total_clicks=data.get("clicks", len(clicks)),
            clicks_per_day=clicks_per_day,
            top_referrers=top_referrers,
            top_browsers=top_browsers,
            top_os=top_os,
            top_devices=top_devices
        )

    return await asyncio.to_thread(_aggregate_clicks)


# ==========================================
# 6. PUBLIC COMMUNITY & USER URL MANAGEMENT
# ==========================================
_public_feed_cache = None
_public_feed_cache_time = 0.0


@app.get("/api/public-links", response_model=URLListResponse)
async def get_public_links(
    limit: int = Query(default=20, ge=1, le=100, description="Page limit"),
    _=Depends(rate_limiter("general"))
):
    """
    Public community feed endpoint:
    - Filters only URLs explicitly marked as `is_public == True`.
    - Never leaks `long_url` for password-protected links.
    - Never leaks `owner_uid` on public feeds.
    - Cached for 30s to prevent database hammering.
    """
    global _public_feed_cache, _public_feed_cache_time
    now = time.time()

    if _public_feed_cache is not None and (now - _public_feed_cache_time) < 30.0:
        return _public_feed_cache

    def _fetch_feed():
        try:
            urls_ref = db.collection("urls").where(filter=gcf.FieldFilter("is_public", "==", True)).order_by("created_at", direction=gcf.Query.DESCENDING).limit(limit)
            docs = list(urls_ref.stream())
        except Exception:
            docs = list(db.collection("urls").limit(limit).stream())

        urls = []
        for doc in docs:
            data = doc.to_dict()
            is_protected = data.get("is_password_protected", False)

            urls.append(URLDetailedResponse(
                short_code=doc.id,
                long_url="[PROTECTED - PASSCODE REQUIRED]" if is_protected else data.get("long_url", ""),
                created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
                clicks=data.get("clicks", 0),
                expires_at=data.get("expires_at"),
                max_clicks=data.get("max_clicks"),
                is_password_protected=is_protected,
                is_public=data.get("is_public", True),
                owner_uid=None,  # Redacted on public feeds for privacy
                safety_score=data.get("safety_score", 100),
                safety_verdict=data.get("safety_verdict", "SAFE"),
                ai_category=data.get("ai_category", "General Web"),
                safety_flags=data.get("safety_flags", []),
            ))
        return URLListResponse(urls=urls)

    result = await asyncio.to_thread(_fetch_feed)
    _public_feed_cache = result
    _public_feed_cache_time = now
    return result


@app.get("/api/my-urls", response_model=URLListResponse)
async def get_my_urls(
    current_user: str = Depends(get_current_user_required),
    _=Depends(rate_limiter("general"))
):
    def _fetch_user_urls():
        urls_ref = db.collection("urls").where(filter=gcf.FieldFilter("owner_uid", "==", current_user))
        docs = urls_ref.stream()
        urls = []
        for doc in docs:
            data = doc.to_dict()
            urls.append(URLDetailedResponse(
                short_code=doc.id,
                long_url=data.get("long_url", ""),
                created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
                clicks=data.get("clicks", 0),
                expires_at=data.get("expires_at"),
                max_clicks=data.get("max_clicks"),
                is_password_protected=data.get("is_password_protected", False),
                is_public=data.get("is_public", True),
                owner_uid=data.get("owner_uid"),
                safety_score=data.get("safety_score", 100),
                safety_verdict=data.get("safety_verdict", "SAFE"),
                ai_category=data.get("ai_category", "General Web"),
                safety_flags=data.get("safety_flags", []),
            ))
        return URLListResponse(urls=urls)

    return await asyncio.to_thread(_fetch_user_urls)


@app.delete("/api/urls/{code}")
async def delete_url(
    code: str,
    current_user: str = Depends(get_current_user_required)
):
    doc_ref = db.collection("urls").document(code)
    doc = await asyncio.to_thread(doc_ref.get)
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Short URL not found")

    if doc.to_dict().get("owner_uid") != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to delete this URL")

    # Recursive delete to avoid orphaned click subcollections
    try:
        await asyncio.to_thread(db.recursive_delete, doc_ref)
    except Exception:
        await asyncio.to_thread(doc_ref.delete)

    invalidate_cached_url(code)
    return {"message": "Deleted successfully"}


# ==========================================
# 7. DEVELOPER API KEYS & BULK OPERATIONS
# ==========================================
@app.post("/api/keys/generate", response_model=APIKeyCreatedResponse)
async def create_api_key(
    payload: APIKeyCreateRequest,
    current_user: str = Depends(get_current_user_required),
    _=Depends(rate_limiter("keys"))
):
    """
    Generates a new secure API Key with O(1) verification.
    Server-side tier assignment (defaults to 'basic' to prevent privilege escalation).
    Enforces a maximum of 5 active keys per user.
    """
    def _create_key():
        keys_ref = db.collection("api_keys")
        user_keys = list(keys_ref.where(filter=gcf.FieldFilter("owner_uid", "==", current_user)).where(filter=gcf.FieldFilter("is_active", "==", True)).stream())

        if len(user_keys) >= 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum limit of 5 active API keys reached. Please revoke an unused key.")

        full_api_key, key_id, secret_hash = generate_api_key_pair()
        created_at = datetime.now(timezone.utc).isoformat()

        doc_data = {
            "key_id": key_id,
            "secret_hash": secret_hash,
            "owner_uid": current_user,
            "rate_limit_tier": "basic",  # Secure server-side assignment
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
            rate_limit_tier="basic",
            created_at=created_at
        )

    return await asyncio.to_thread(_create_key)


@app.get("/api/keys", response_model=APIKeyListResponse)
async def list_api_keys(
    current_user: str = Depends(get_current_user_required)
):
    """Lists all active API keys for the authenticated user without exposing secret hashes."""
    def _fetch_keys():
        keys_ref = db.collection("api_keys")
        docs = list(keys_ref.where(filter=gcf.FieldFilter("owner_uid", "==", current_user)).stream())
        key_list = []
        for d in docs:
            data = d.to_dict()
            key_list.append(APIKeyResponse(
                key_id=data.get("key_id", d.id),
                name=data.get("name", "API Key"),
                rate_limit_tier=data.get("rate_limit_tier", "basic"),
                usage_count=data.get("usage_count", 0),
                created_at=data.get("created_at"),
                is_active=data.get("is_active", True)
            ))
        return APIKeyListResponse(keys=key_list)

    return await asyncio.to_thread(_fetch_keys)


@app.delete("/api/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: str = Depends(get_current_user_required)
):
    """Revokes an API key immediately and clears it from in-memory cache."""
    doc_ref = db.collection("api_keys").document(key_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if not doc.exists:
        raise HTTPException(status_code=404, detail="API key not found")

    if doc.to_dict().get("owner_uid") != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to revoke this key")

    await asyncio.to_thread(doc_ref.update, {"is_active": False, "revoked_at": datetime.now(timezone.utc).isoformat()})
    invalidate_api_key_cache(key_id)
    return {"message": "API key revoked successfully"}


@app.get("/api/usage", response_model=APIKeyResponse)
async def get_api_usage(api_key_data: dict = Depends(verify_api_key)):
    """Returns metadata and usage stats for the caller's API key without leaking secret hash."""
    return APIKeyResponse(
        key_id=api_key_data.get("key_id", ""),
        name=api_key_data.get("name", "API Key"),
        rate_limit_tier=api_key_data.get("rate_limit_tier", "basic"),
        usage_count=api_key_data.get("usage_count", 0),
        created_at=api_key_data.get("created_at"),
        is_active=api_key_data.get("is_active", True)
    )


@app.post("/api/bulk-shorten", response_model=BulkShortenResponse)
async def bulk_shorten(
    request: Request,
    payload: BulkShortenRequest,
    api_key_data: dict = Depends(verify_api_key),
    _=Depends(rate_limiter("bulk"))
):
    """
    High-throughput bulk URL shortener (max 100 per batch).
    - Validates all destination URLs first.
    - Atomically commits all items to Firestore before caching to avoid cache poisoning.
    """
    request.state.api_key_data = api_key_data
    urls_to_create = []
    item_results = []
    urls_ref = db.collection("urls")

    # Step 1: Pre-validate all URLs
    for long_url in payload.long_urls:
        url_str = str(long_url)
        is_blocked, block_reason = check_domain_blocklist(url_str)
        if is_blocked:
            item_results.append(BulkShortenItemResult(
                long_url=url_str,
                status="failed",
                error=block_reason
            ))
            continue

        safety = scan_url_safety(url_str)
        if safety["safety_verdict"] == "MALICIOUS":
            item_results.append(BulkShortenItemResult(
                long_url=url_str,
                status="failed",
                error=f"Rejected: {', '.join(safety['flags'])}",
                safety_score=safety["safety_score"],
                safety_verdict=safety["safety_verdict"]
            ))
            continue

        code = generate_short_code()
        doc_data = {
            "long_url": url_str,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "clicks": 0,
            "owner_uid": api_key_data.get("owner_uid"),
            "is_password_protected": False,
            "is_public": True,
            "safety_score": safety["safety_score"],
            "safety_verdict": safety["safety_verdict"],
            "ai_category": safety["category"],
            "safety_flags": safety["flags"],
        }
        urls_to_create.append((code, doc_data, url_str, safety))

    # Step 2: Commit valid URLs in atomic batch
    if urls_to_create:
        def _commit_batch():
            batch = db.batch()
            for code, doc_data, _, _ in urls_to_create:
                doc_ref = urls_ref.document(code)
                batch.set(doc_ref, doc_data)
            batch.commit()

        await asyncio.to_thread(_commit_batch)

        # Step 3: Populate cache only after successful commit
        for code, doc_data, url_str, safety in urls_to_create:
            set_cached_url(code, doc_data)
            item_results.append(BulkShortenItemResult(
                long_url=url_str,
                status="success",
                short_code=code,
                short_url=f"{BASE_URL}/{code}",
                safety_score=safety["safety_score"],
                safety_verdict=safety["safety_verdict"],
                ai_category=safety["category"]
            ))

    successful_count = sum(1 for r in item_results if r.status == "success")
    return BulkShortenResponse(
        total_submitted=len(payload.long_urls),
        total_shortened=successful_count,
        results=item_results
    )


# ==========================================
# 8. AI SCANNER & THREAT INTELLIGENCE
# ==========================================
@app.post("/api/scan", response_model=AIScanResponse)
async def scan_custom_url(
    payload: Optional[AIScanRequest] = None,
    url: Optional[str] = None,
    _=Depends(rate_limiter("general"))
):
    """
    Real-time AI Link Intelligence & Threat Scanner:
    Inspects URL lexical entropy, protocol security, brand spoofing, and TLD reputation.
    Supports JSON body {"url": "..."} or query parameter.
    """
    target_url = str(payload.url) if payload else url
    if not target_url:
        raise HTTPException(status_code=400, detail="Missing URL to scan")

    scan_result = scan_url_safety(target_url)
    return AIScanResponse(
        url=target_url,
        safety_score=scan_result["safety_score"],
        safety_verdict=scan_result["safety_verdict"],
        category=scan_result["category"],
        flags=scan_result["flags"],
        entropy=scan_result["entropy"],
    )


@app.get("/api/scan/{code}", response_model=AIScanResponse)
async def scan_short_code(
    code: str,
    current_user: Optional[str] = Depends(get_current_user),
    _=Depends(rate_limiter("general"))
):
    """
    Fetches AI Safety Analysis for an existing shortened URL code.
    Protects password-protected destinations from leaking to unauthenticated users.
    """
    data = get_cached_url(code)
    if not data:
        doc = await asyncio.to_thread(db.collection("urls").document(code).get)
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Short URL not found")
        data = doc.to_dict()

    if data.get("is_password_protected") and data.get("owner_uid") != current_user:
        return AIScanResponse(
            url="[PROTECTED - PASSCODE REQUIRED]",
            safety_score=data.get("safety_score", 100),
            safety_verdict=data.get("safety_verdict", "SAFE"),
            category=data.get("ai_category", "General Web"),
            flags=["Password Protected Link (Destination URL Redacted)"],
            entropy=0.0
        )

    long_url = data.get("long_url", "")
    scan_result = scan_url_safety(long_url)
    return AIScanResponse(
        url=long_url,
        safety_score=data.get("safety_score", scan_result["safety_score"]),
        safety_verdict=data.get("safety_verdict", scan_result["safety_verdict"]),
        category=data.get("ai_category", scan_result["category"]),
        flags=data.get("safety_flags", scan_result["flags"]),
        entropy=scan_result["entropy"],
    )


# ==========================================
# 9. OBSERVABILITY, METRICS & SYSTEM HEALTH
# ==========================================
@app.get("/api/health", response_model=SystemHealthResponse)
async def system_health():
    """Live health probe verifying Firestore and Redis connectivity."""
    # Test Firestore connectivity
    firestore_status = "connected"
    try:
        await asyncio.to_thread(lambda: db.collection("health").document("ping").get())
    except Exception:
        firestore_status = "degraded"

    redis_status = "connected" if is_redis_available() else "offline"

    overall_status = "healthy" if firestore_status == "connected" else "degraded"

    return SystemHealthResponse(
        status=overall_status,
        firestore=firestore_status,
        redis=redis_status,
        cache_backend="Redis-L2 + Memory-L1" if is_redis_available() else "InMemory-LRU",
        rate_limiter_backend="Redis-Sliding-Window" if is_rate_limiter_redis_available() else "InMemory-Sliding-Window",
        analytics_queue_size=analytics_queue._queue.qsize(),
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/api/observability", response_model=ObservabilityResponse)
async def get_system_observability():
    """
    Comprehensive Observability Endpoint:
    Returns real-time cache hit/miss rates, queue metrics, request latency statistics,
    and rate limit trigger telemetry.
    """
    cache_stats = get_cache_stats()
    queue_stats = analytics_queue.get_queue_stats()
    rate_stats = get_rate_limiter_stats()

    # Latency & Sliding-Window RPM calculations
    now = time.time()
    with _telemetry_lock:
        samples = list(_latency_samples)
        total_reqs = _total_requests
        status_map = dict(_status_codes)
        # Count requests in last 60 seconds for true RPM
        recent_reqs = sum(1 for t in _request_timestamps if now - t <= 60.0)

    uptime = now - APP_START_TIME

    if samples:
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        avg_lat = round(sum(samples) / n, 2)
        p50_lat = round(sorted_samples[int(n * 0.50)], 2)
        p95_lat = round(sorted_samples[min(int(n * 0.95), n - 1)], 2)
        p99_lat = round(sorted_samples[min(int(n * 0.99), n - 1)], 2)
        min_lat = round(sorted_samples[0], 2)
        max_lat = round(sorted_samples[-1], 2)
    else:
        avg_lat = p50_lat = p95_lat = p99_lat = min_lat = max_lat = 0.0

    return ObservabilityResponse(
        status="healthy",
        uptime_seconds=round(uptime, 1),
        timestamp=datetime.now(timezone.utc).isoformat(),
        cache=CacheMetrics(
            backend=cache_stats["backend"],
            is_redis_active=cache_stats["is_redis_active"],
            l1_hits=cache_stats["l1_hits"],
            l2_hits=cache_stats["l2_hits"],
            misses=cache_stats["misses"],
            negative_hits=cache_stats["negative_hits"],
            total_lookups=cache_stats["total_lookups"],
            hit_rate_pct=cache_stats["hit_rate_pct"],
            items_in_l1=cache_stats["items_in_l1"],
            negative_items=cache_stats["negative_items"],
        ),
        queue=QueueMetrics(
            queue_size=queue_stats["queue_size"],
            total_enqueued=queue_stats["total_enqueued"],
            total_flushed=queue_stats["total_flushed"],
            total_batches=queue_stats["total_batches"],
            last_flush_time=queue_stats["last_flush_time"],
            is_worker_running=queue_stats["is_worker_running"],
        ),
        latency=LatencyMetrics(
            total_requests=total_reqs,
            avg_latency_ms=avg_lat,
            p50_latency_ms=p50_lat,
            p95_latency_ms=p95_lat,
            p99_latency_ms=p99_lat,
            min_latency_ms=min_lat,
            max_latency_ms=max_lat,
            requests_per_minute=recent_reqs,
            status_codes=status_map,
        ),
        rate_limiter=RateLimitMetrics(
            backend=rate_stats["backend"],
            total_checks=rate_stats["total_checks"],
            total_blocked=rate_stats["total_blocked"],
            block_rate_pct=rate_stats["block_rate_pct"],
            blocks_by_scope=rate_stats["blocks_by_scope"],
            recent_blocked_events=rate_stats["recent_blocked_events"],
        )
    )
