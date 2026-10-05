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
