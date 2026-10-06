import os
import json
import time
import threading
from typing import Optional, Dict, Any
from collections import OrderedDict

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")

_redis_cache = None
_last_redis_check = 0.0
_redis_healthy = False
_redis_lock = threading.Lock()


def get_redis_client():
    global _redis_cache, _redis_healthy, _last_redis_check
    now = time.time()
    with _redis_lock:
        if now - _last_redis_check > 5.0 or _redis_cache is None:
            _last_redis_check = now
            try:
                import redis
                if _redis_cache is None:
                    _redis_cache = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
                _redis_cache.ping()
                _redis_healthy = True
            except Exception:
                _redis_healthy = False
        return _redis_cache if _redis_healthy else None


def is_redis_available() -> bool:
    return get_redis_client() is not None


class InMemoryLRUCache:
    def __init__(self, capacity: int = 50000):
        self.capacity = capacity
        self.cache: OrderedDict[str, tuple] = OrderedDict()
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

_cache_stats = {
    "l1_hits": 0,
    "l2_hits": 0,
    "misses": 0,
    "negative_hits": 0,
    "sets": 0,
}
_stats_lock = threading.Lock()


def get_cached_url(code: str) -> Optional[Dict[str, Any]]:
    local_val = _local_lru.get(f"url:{code}")
    if local_val:
        with _stats_lock:
            _cache_stats["l1_hits"] += 1
        return local_val

    r = get_redis_client()
    if r:
        try:
            raw = r.get(f"url:{code}")
            if raw:
                data = json.loads(raw)
                _local_lru.set(f"url:{code}", data, ttl_seconds=60)
                with _stats_lock:
                    _cache_stats["l2_hits"] += 1
                return data
        except Exception:
            pass

    with _stats_lock:
        _cache_stats["misses"] += 1
    return None


def set_cached_url(code: str, data: Dict[str, Any], ttl_seconds: int = 86400):
    clean_data = dict(data)
    clean_data.pop("password_hash", None)
    _negative_lru.delete(f"neg:{code}")

    with _stats_lock:
        _cache_stats["sets"] += 1

    _local_lru.set(f"url:{code}", clean_data, ttl_seconds=min(ttl_seconds, 60))

    r = get_redis_client()
    if r:
        try:
            r.delete(f"neg:{code}")
            r.setex(f"url:{code}", ttl_seconds, json.dumps(clean_data))
        except Exception:
            pass


def invalidate_cached_url(code: str):
    _local_lru.delete(f"url:{code}")
    _negative_lru.delete(f"neg:{code}")
    r = get_redis_client()
    if r:
        try:
            r.delete(f"url:{code}")
            r.delete(f"neg:{code}")
        except Exception:
            pass


def is_known_nonexistent(code: str) -> bool:
    if _negative_lru.get(f"neg:{code}"):
        with _stats_lock:
            _cache_stats["negative_hits"] += 1
        return True

    r = get_redis_client()
    if r:
        try:
            if r.exists(f"neg:{code}"):
                _negative_lru.set(f"neg:{code}", True, ttl_seconds=30)
                with _stats_lock:
                    _cache_stats["negative_hits"] += 1
                return True
        except Exception:
            pass
    return False


def set_nonexistent(code: str, ttl_seconds: int = 30):
    _negative_lru.set(f"neg:{code}", True, ttl_seconds=ttl_seconds)
    r = get_redis_client()
    if r:
        try:
            r.setex(f"neg:{code}", ttl_seconds, "1")
        except Exception:
            pass


def atomic_increment_clicks(code: str, max_clicks: int) -> Optional[int]:
    r = get_redis_client()
    if not r:
        return None
    try:
        redis_key = f"clicks:{code}"
        pipe = r.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, 86400 * 7)
        results = pipe.execute()
        return results[0]
    except Exception:
        return None


def get_cache_stats() -> Dict[str, Any]:
    with _stats_lock:
        l1 = _cache_stats["l1_hits"]
        l2 = _cache_stats["l2_hits"]
        hits = l1 + l2
        misses = _cache_stats["misses"]
        neg_hits = _cache_stats["negative_hits"]
        total = hits + misses + neg_hits
        hit_rate = round(((hits + neg_hits) / total * 100), 2) if total > 0 else 100.0

        with _local_lru.lock:
            l1_count = len(_local_lru.cache)
        with _negative_lru.lock:
            neg_count = len(_negative_lru.cache)

        redis_active = is_redis_available()
        return {
            "backend": "Redis-L2 + Memory-L1" if redis_active else "InMemory-LRU",
            "is_redis_active": redis_active,
            "l1_hits": l1,
            "l2_hits": l2,
            "hits": hits,
            "misses": misses,
            "negative_hits": neg_hits,
            "total_lookups": total,
            "hit_rate_pct": hit_rate,
            "items_in_l1": l1_count,
            "negative_items": neg_count,
        }
