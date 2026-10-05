import os
import time
import math
import asyncio
import threading
from typing import Optional, Tuple, Dict, Any, Callable
from collections import defaultdict

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Optional Redis connection with graceful fallback
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None
_redis_available = False

try:
    import redis
    _r = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    _r.ping()
    _redis_client = _r
    _redis_available = True
    print("[RateLimiter] Connected to Redis successfully.")
except Exception as e:
    _redis_client = None
    _redis_available = False
    print(f"[RateLimiter] Redis not reachable ({e}). Falling back to high-performance in-memory sliding window.")


class InMemorySlidingWindowLimiter:
    """
    Thread-safe in-memory Sliding Window Log / Counter.
    Maintains timestamps of requests within a sliding window.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # map key -> list of (timestamp)
        self._store: Dict[str, list] = defaultdict(list)
        self._last_cleanup = time.time()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        """
        Returns: (allowed: bool, remaining: int, reset_after_seconds: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Periodic GC every 60 seconds to prevent unbounded memory growth
            if now - self._last_cleanup > 60:
                self._cleanup(now)
                self._last_cleanup = now

            timestamps = self._store[key]
            # Remove timestamps outside current sliding window
            self._store[key] = [t for t in timestamps if t > window_start]
            valid_timestamps = self._store[key]

            current_count = len(valid_timestamps)
            if current_count < max_requests:
                valid_timestamps.append(now)
                remaining = max_requests - current_count - 1
                reset_after = window_seconds
                if valid_timestamps:
                    reset_after = max(1, int(window_seconds - (now - valid_timestamps[0])))
                return True, remaining, reset_after
            else:
                oldest_in_window = valid_timestamps[0]
                reset_after = max(1, int(window_seconds - (now - oldest_in_window)))
                return False, 0, reset_after

    def _cleanup(self, now: float):
        # Remove empty keys older than 1 hour
        keys_to_delete = []
        for k, v in self._store.items():
            fresh = [t for t in v if now - t < 3600]
            if not fresh:
                keys_to_delete.append(k)
            else:
                self._store[k] = fresh
        for k in keys_to_delete:
            del self._store[k]


_in_memory_limiter = InMemorySlidingWindowLimiter()


def get_client_ip(request: Request) -> str:
    """Extracts client IP respecting standard reverse-proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int
) -> Tuple[bool, int, int]:
    """
    Evaluates rate limit using Redis Sliding Window (ZSET) if available,
    otherwise uses thread-safe InMemorySlidingWindowLimiter.
    """
    global _redis_available, _redis_client
    if _redis_available and _redis_client:
        try:
            now = time.time()
            window_start = now - window_seconds
            redis_key = f"ratelimit:{key}"

            pipe = _redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds + 5)
            _, current_count, _, _ = pipe.execute()

            if current_count < max_requests:
                remaining = max(0, max_requests - current_count - 1)
                return True, remaining, window_seconds
            else:
                # Exceeded: remove the one just added
                _redis_client.zremrangebyscore(redis_key, now, now)
                return False, 0, window_seconds
        except Exception:
            _redis_available = False  # Switch to in-memory fallback smoothly

    return _in_memory_limiter.is_allowed(key, max_requests, window_seconds)


class RateLimitRule:
    """Configuration for specific endpoint rate limits."""
    def __init__(self, max_requests: int, window_seconds: int, scope: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope


# Predefined Tier Quotas
TIER_QUOTAS = {
    "anonymous": {
        "shorten": RateLimitRule(20, 60, "shorten_anon"),         # 20 per min
        "redirect": RateLimitRule(300, 60, "redirect_anon"),      # 300 per min
        "verify": RateLimitRule(10, 60, "verify_anon"),           # 10 per min (brute force protection)
        "qr": RateLimitRule(30, 60, "qr_anon"),                  # 30 per min
        "general": RateLimitRule(120, 60, "general_anon"),
    },
    "authenticated": {
        "shorten": RateLimitRule(120, 60, "shorten_auth"),        # 120 per min
        "redirect": RateLimitRule(1000, 60, "redirect_auth"),
        "verify": RateLimitRule(30, 60, "verify_auth"),
        "qr": RateLimitRule(120, 60, "qr_auth"),
        "general": RateLimitRule(600, 60, "general_auth"),
    },
    "api_basic": {
        "shorten": RateLimitRule(60, 60, "api_basic"),           # 60 req/min
        "bulk": RateLimitRule(10, 60, "api_basic_bulk"),
        "general": RateLimitRule(1000, 3600, "api_basic_hourly"), # 1000 req/hour
    },
    "api_pro": {
        "shorten": RateLimitRule(300, 60, "api_pro"),            # 300 req/min
        "bulk": RateLimitRule(60, 60, "api_pro_bulk"),
        "general": RateLimitRule(10000, 3600, "api_pro_hourly"), # 10,000 req/hour
    },
    "api_enterprise": {
        "shorten": RateLimitRule(1200, 60, "api_enterprise"),     # 1,200 req/min
        "bulk": RateLimitRule(300, 60, "api_enterprise_bulk"),
        "general": RateLimitRule(100000, 3600, "api_enterprise_hourly"),
    },
}


def rate_limiter(action: str = "general"):
    """
    FastAPI dependency for tiered, multi-identity rate limiting.
    Attaches rate limit info and enforces quotas.
    """
    async def dependency(request: Request):
        ip = get_client_ip(request)
        user_uid = getattr(request.state, "user_uid", None)
        api_key_data = getattr(request.state, "api_key_data", None)

        if api_key_data:
            tier = api_key_data.get("rate_limit_tier", "basic").lower()
            tier_key = f"api_{tier}" if f"api_{tier}" in TIER_QUOTAS else "api_basic"
            identifier = f"apikey:{api_key_data.get('key_id', ip)}"
            rule = TIER_QUOTAS[tier_key].get(action, TIER_QUOTAS[tier_key]["general"])
        elif user_uid:
            tier_key = "authenticated"
            identifier = f"user:{user_uid}"
            rule = TIER_QUOTAS[tier_key].get(action, TIER_QUOTAS[tier_key]["general"])
        else:
            tier_key = "anonymous"
            identifier = f"ip:{ip}"
            rule = TIER_QUOTAS[tier_key].get(action, TIER_QUOTAS[tier_key]["general"])

        limit_key = f"{rule.scope}:{identifier}"
        allowed, remaining, reset_seconds = check_rate_limit(
            limit_key,
            rule.max_requests,
            rule.window_seconds
        )

        _record_check(allowed=allowed, scope=action, tier=tier_key, client_id=identifier)

        # Store headers in request.state for response injection
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(rule.max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(time.time() + reset_seconds)),
        }

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Quota exceeded for action '{action}'. Try again in {reset_seconds} seconds.",
                    "limit": rule.max_requests,
                    "retry_after_seconds": reset_seconds,
                    "tier": tier_key
                },
                headers={
                    "Retry-After": str(reset_seconds),
                    **request.state.rate_limit_headers
                }
            )

    return dependency


# ==========================================
# Observability & Rate Limit Telemetry
# ==========================================
_rate_stats = {
    "total_checks": 0,
    "total_blocked": 0,
    "blocks_by_scope": {
        "shorten": 0,
        "redirect": 0,
        "verify": 0,
        "qr": 0,
        "general": 0,
    },
    "recent_blocked_events": []  # max 20 events
}
_rate_stats_lock = threading.Lock()


def _record_check(allowed: bool, scope: str, tier: str, client_id: str):
    with _rate_stats_lock:
        _rate_stats["total_checks"] += 1
        if not allowed:
            _rate_stats["total_blocked"] += 1
            _rate_stats["blocks_by_scope"][scope] = _rate_stats["blocks_by_scope"].get(scope, 0) + 1
            
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "scope": scope,
                "tier": tier,
                "client": client_id[:16] + "..." if len(client_id) > 16 else client_id,
            }
            _rate_stats["recent_blocked_events"].insert(0, event)
            if len(_rate_stats["recent_blocked_events"]) > 20:
                _rate_stats["recent_blocked_events"].pop()


def get_rate_limiter_stats() -> Dict[str, Any]:
    """Returns rate limit trigger observability metrics."""
    with _rate_stats_lock:
        checks = _rate_stats["total_checks"]
        blocked = _rate_stats["total_blocked"]
        block_rate = round((blocked / checks * 100), 2) if checks > 0 else 0.0
        return {
            "backend": "Redis-ZSET" if _redis_available else "InMemory-Sliding-Window",
            "total_checks": checks,
            "total_blocked": blocked,
            "block_rate_pct": block_rate,
            "blocks_by_scope": dict(_rate_stats["blocks_by_scope"]),
            "recent_blocked_events": list(_rate_stats["recent_blocked_events"]),
        }

