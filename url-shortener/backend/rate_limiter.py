import os
import time
import math
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, Callable
from collections import defaultdict

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None
_last_redis_check = 0.0
_redis_healthy = False
_redis_lock = threading.Lock()

BOT_USER_AGENTS = {
    "bot", "crawler", "spider", "slackbot", "twitterbot", "facebookexternalhit",
    "whatsapp", "telegrambot", "discordbot", "linkedinbot", "embedly", "quora link preview",
    "pinterest", "bingbot", "googlebot", "yandex", "baiduspider", "duckduckbot"
}


def get_redis_client():
    global _redis_client, _redis_healthy, _last_redis_check
    now = time.time()
    with _redis_lock:
        if now - _last_redis_check > 5.0 or _redis_client is None:
            _last_redis_check = now
            try:
                import redis
                if _redis_client is None:
                    _redis_client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
                _redis_client.ping()
                _redis_healthy = True
            except Exception:
                _redis_healthy = False
        return _redis_client if _redis_healthy else None


def is_rate_limiter_redis_available() -> bool:
    return get_redis_client() is not None


def is_bot_or_crawler(user_agent: str) -> bool:
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(bot in ua_lower for bot in BOT_USER_AGENTS)


class InMemorySlidingWindowLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, list] = defaultdict(list)
        self._last_cleanup = time.time()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            if now - self._last_cleanup > 60:
                self._cleanup(now)
                self._last_cleanup = now

            timestamps = self._store[key]
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
    r = get_redis_client()
    if r:
        try:
            now = time.time()
            window_start = now - window_seconds
            redis_key = f"ratelimit:{key}"

            pipe = r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds + 5)
            _, current_count, _, _ = pipe.execute()

            if current_count < max_requests:
                remaining = max(0, max_requests - current_count - 1)
                return True, remaining, window_seconds
            else:
                r.zremrangebyscore(redis_key, now, now)
                return False, 0, window_seconds
        except Exception:
            pass

    return _in_memory_limiter.is_allowed(key, max_requests, window_seconds)


class RateLimitRule:
    def __init__(self, max_requests: int, window_seconds: int, scope: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope


TIER_QUOTAS = {
    "anonymous": {
        "shorten": RateLimitRule(20, 60, "shorten_anon"),
        "redirect": RateLimitRule(300, 60, "redirect_anon"),
        "verify": RateLimitRule(10, 60, "verify_anon"),
        "qr": RateLimitRule(30, 60, "qr_anon"),
        "keys": RateLimitRule(5, 60, "keys_anon"),
        "general": RateLimitRule(120, 60, "general_anon"),
    },
    "authenticated": {
        "shorten": RateLimitRule(120, 60, "shorten_auth"),
        "redirect": RateLimitRule(1000, 60, "redirect_auth"),
        "verify": RateLimitRule(30, 60, "verify_auth"),
        "qr": RateLimitRule(120, 60, "qr_auth"),
        "keys": RateLimitRule(10, 60, "keys_auth"),
        "general": RateLimitRule(600, 60, "general_auth"),
    },
    "api_basic": {
        "shorten": RateLimitRule(60, 60, "api_basic"),
        "bulk": RateLimitRule(10, 60, "api_basic_bulk"),
        "general": RateLimitRule(1000, 3600, "api_basic_hourly"),
    },
    "api_pro": {
        "shorten": RateLimitRule(300, 60, "api_pro"),
        "bulk": RateLimitRule(60, 60, "api_pro_bulk"),
        "general": RateLimitRule(10000, 3600, "api_pro_hourly"),
    },
    "api_enterprise": {
        "shorten": RateLimitRule(1200, 60, "api_enterprise"),
        "bulk": RateLimitRule(300, 60, "api_enterprise_bulk"),
        "general": RateLimitRule(100000, 3600, "api_enterprise_hourly"),
    },
}


def rate_limiter(action: str = "general"):
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


_rate_stats = {
    "total_checks": 0,
    "total_blocked": 0,
    "blocks_by_scope": {
        "shorten": 0,
        "redirect": 0,
        "verify": 0,
        "qr": 0,
        "general": 0,
        "keys": 0,
        "bulk": 0,
    },
    "recent_blocked_events": []
}
_rate_stats_lock = threading.Lock()


def _record_check(allowed: bool, scope: str, tier: str, client_id: str):
    with _rate_stats_lock:
        _rate_stats["total_checks"] += 1
        if not allowed:
            _rate_stats["total_blocked"] += 1
            _rate_stats["blocks_by_scope"][scope] = _rate_stats["blocks_by_scope"].get(scope, 0) + 1
            
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scope": scope,
                "tier": tier,
                "client": client_id[:16] + "..." if len(client_id) > 16 else client_id,
            }
            _rate_stats["recent_blocked_events"].insert(0, event)
            if len(_rate_stats["recent_blocked_events"]) > 20:
                _rate_stats["recent_blocked_events"].pop()


def get_rate_limiter_stats() -> Dict[str, Any]:
    with _rate_stats_lock:
        checks = _rate_stats["total_checks"]
        blocked = _rate_stats["total_blocked"]
        block_rate = round((blocked / checks * 100), 2) if checks > 0 else 0.0
        redis_active = is_rate_limiter_redis_available()
        return {
            "backend": "Redis-ZSET" if redis_active else "InMemory-Sliding-Window",
            "is_redis_active": redis_active,
            "total_checks": checks,
            "total_blocked": blocked,
            "block_rate_pct": block_rate,
            "blocks_by_scope": dict(_rate_stats["blocks_by_scope"]),
            "recent_blocked_events": list(_rate_stats["recent_blocked_events"]),
        }
