from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class URLCreate(BaseModel):
    long_url: HttpUrl
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_clicks: Optional[int] = None
    password: Optional[str] = None


class URLResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    safety_score: Optional[int] = 100
    safety_verdict: Optional[str] = "SAFE"
    ai_category: Optional[str] = "General Web"
    safety_flags: Optional[List[str]] = []


class ClickStats(BaseModel):
    total_clicks: int
    clicks_per_day: Dict[str, int]
    top_referrers: Dict[str, int]
    top_browsers: Dict[str, int]
    top_devices: Dict[str, int]


class URLDetailedResponse(BaseModel):
    short_code: str
    long_url: str
    created_at: str
    clicks: int
    expires_at: Optional[str] = None
    max_clicks: Optional[int] = None
    is_password_protected: bool
    owner_uid: Optional[str] = None
    safety_score: Optional[int] = 100
    safety_verdict: Optional[str] = "SAFE"
    ai_category: Optional[str] = "General Web"
    safety_flags: Optional[List[str]] = []


class AIScanResponse(BaseModel):
    url: str
    safety_score: int
    safety_verdict: str
    category: str
    flags: List[str]
    entropy: float


class URLListResponse(BaseModel):
    urls: List[URLDetailedResponse]



class VerifyPasswordRequest(BaseModel):
    password: str


class BulkShortenRequest(BaseModel):
    long_urls: List[HttpUrl]


class BulkShortenResponse(BaseModel):
    shortened_urls: List[URLResponse]


class APIKeyCreateRequest(BaseModel):
    name: Optional[str] = "Default API Key"
    tier: Optional[str] = "basic"  # basic, pro, enterprise


class APIKeyCreatedResponse(BaseModel):
    api_key: str
    key_id: str
    name: str
    rate_limit_tier: str
    created_at: str
    message: str = "Store this API key securely. You will not be able to view the full key again."


class APIKeyResponse(BaseModel):
    key_id: Optional[str] = None
    key_hash: Optional[str] = None
    owner_uid: str
    usage_count: int
    rate_limit_tier: str
    name: Optional[str] = "API Key"


class SystemHealthResponse(BaseModel):
    status: str
    cache_backend: str
    rate_limiter_backend: str
    analytics_queue_size: int
    timestamp: str


class CacheMetrics(BaseModel):
    backend: str
    is_redis_active: bool
    hits: int
    misses: int
    negative_hits: int
    total_lookups: int
    hit_rate_pct: float
    items_in_l1: int
    negative_items: int


class QueueMetrics(BaseModel):
    queue_size: int
    total_enqueued: int
    total_flushed: int
    total_batches: int
    last_flush_time: Optional[str] = None
    is_worker_running: bool


class LatencyMetrics(BaseModel):
    total_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    requests_per_minute: int
    status_codes: Dict[str, int]


class RateLimitMetrics(BaseModel):
    backend: str
    total_checks: int
    total_blocked: int
    block_rate_pct: float
    blocks_by_scope: Dict[str, int]
    recent_blocked_events: List[Dict[str, Any]]


class ObservabilityResponse(BaseModel):
    status: str
    uptime_seconds: float
    timestamp: str
    cache: CacheMetrics
    queue: QueueMetrics
    latency: LatencyMetrics
    rate_limiter: RateLimitMetrics

