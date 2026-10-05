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


def get_cached_url(code: str) -> Optional[Dict[str, Any]]:
    """Retrieves URL metadata from Redis or Local LRU cache."""
    # 1. Check local LRU
    local_val = _local_lru.get(f"url:{code}")
    if local_val:
        return local_val

    # 2. Check Redis
    if _redis_available and _redis_cache:
        try:
            raw = _redis_cache.get(f"url:{code}")
            if raw:
                data = json.loads(raw)
                _local_lru.set(f"url:{code}", data, ttl_seconds=300)
                return data
        except Exception:
            pass

    return None


def set_cached_url(code: str, data: Dict[str, Any], ttl_seconds: int = 86400):
    """Sets URL metadata into cache."""
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
    return bool(_negative_lru.get(f"neg:{code}"))


def set_nonexistent(code: str, ttl_seconds: int = 30):
    """Caches a 404 for a short period."""
    _negative_lru.set(f"neg:{code}", True, ttl_seconds=ttl_seconds)
