import os
import json
import time
import threading
from typing import Optional, Dict, Any
from collections import OrderedDict

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")

_redis_cache = None
_redis_available = False

try:
    import redis
    _r = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    _r.ping()
    _redis_cache = _r
    _redis_available = True
    print("[Cache] Connected to Redis cache successfully.")
except Exception:
    _redis_cache = None
    _redis_available = False
    print("[Cache] Using thread-safe LRU In-Memory Cache.")


class InMemoryLRUCache:
    """Thread-safe LRU Cache with TTL."""
    def __init__(self, capacity: int = 50000):
        self.capacity = capacity
        self.cache: OrderedDict[str, tuple] = OrderedDict()  # key -> (value, expire_at)
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key not in self.cache:
                return None
            val, exp = self.cache[key]
            if exp is not None and time.time() > exp:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return val

    def set(self, key: str, val: Any, ttl_seconds: Optional[int] = None):
        with self.lock:
            exp = time.time() + ttl_seconds if ttl_seconds else None
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (val, exp)
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def delete(self, key: str):
        with self.lock:
            self.cache.pop(key, None)


_local_lru = InMemoryLRUCache(capacity=50000)
_negative_lru = InMemoryLRUCache(capacity=10000)

# Observability telemetry counters
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "negative_hits": 0,
    "sets": 0,
}
_stats_lock = threading.Lock()


def get_cached_url(code: str) -> Optional[Dict[str, Any]]:
    """Retrieves URL metadata from Redis or Local LRU cache with metric recording."""
    global _cache_stats

    # Check for negative cached (known 404)
    if _negative_lru.get(f"neg:{code}"):
        with _stats_lock:
            _cache_stats["negative_hits"] += 1
            _cache_stats["hits"] += 1
        return None

    # 1. Check local LRU
    local_val = _local_lru.get(f"url:{code}")
    if local_val:
        with _stats_lock:
            _cache_stats["hits"] += 1
        return local_val

    # 2. Check Redis
    if _redis_available and _redis_cache:
        try:
            raw = _redis_cache.get(f"url:{code}")
            if raw:
                data = json.loads(raw)
                _local_lru.set(f"url:{code}", data, ttl_seconds=300)
                with _stats_lock:
                    _cache_stats["hits"] += 1
                return data
        except Exception:
            pass

    with _stats_lock:
        _cache_stats["misses"] += 1
    return None


def set_cached_url(code: str, data: Dict[str, Any], ttl_seconds: int = 86400):
    """Sets URL metadata into cache with metric recording."""
    global _cache_stats
    with _stats_lock:
        _cache_stats["sets"] += 1

    _local_lru.set(f"url:{code}", data, ttl_seconds=min(ttl_seconds, 3600))
    if _redis_available and _redis_cache:
        try:
            _redis_cache.setex(f"url:{code}", ttl_seconds, json.dumps(data))
        except Exception:
            pass


def invalidate_cached_url(code: str):
    """Purges URL from cache upon deletion or update."""
    _local_lru.delete(f"url:{code}")
    _negative_lru.delete(f"neg:{code}")
    if _redis_available and _redis_cache:
        try:
            _redis_cache.delete(f"url:{code}")
            _redis_cache.delete(f"neg:{code}")
        except Exception:
            pass


def is_known_nonexistent(code: str) -> bool:
    """Protects against cache penetration attacks (hammering non-existent links)."""
    val = bool(_negative_lru.get(f"neg:{code}"))
    if val:
        with _stats_lock:
            _cache_stats["negative_hits"] += 1
            _cache_stats["hits"] += 1
    return val


def set_nonexistent(code: str, ttl_seconds: int = 30):
    """Caches a 404 for a short period."""
    _negative_lru.set(f"neg:{code}", True, ttl_seconds=ttl_seconds)


def get_cache_stats() -> Dict[str, Any]:
    """Returns real-time cache observability metrics."""
    with _stats_lock:
        hits = _cache_stats["hits"]
        misses = _cache_stats["misses"]
        neg_hits = _cache_stats["negative_hits"]
        total = hits + misses
        hit_rate = round((hits / total * 100), 2) if total > 0 else 100.0

        with _local_lru.lock:
            l1_count = len(_local_lru.cache)
        with _negative_lru.lock:
            neg_count = len(_negative_lru.cache)

        return {
            "backend": "Redis-L2 + Memory-L1" if _redis_available else "InMemory-LRU",
            "is_redis_active": _redis_available,
            "hits": hits,
            "misses": misses,
            "negative_hits": neg_hits,
            "total_lookups": total,
            "hit_rate_pct": hit_rate,
            "items_in_l1": l1_count,
            "negative_items": neg_count,
        }

