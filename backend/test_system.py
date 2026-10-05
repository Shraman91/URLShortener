import time
from keygen import generate_short_code, is_valid_alias
from rate_limiter import check_rate_limit, InMemorySlidingWindowLimiter
from auth_service import generate_api_key_pair, hash_secret
from cache import get_cached_url, set_cached_url, invalidate_cached_url, is_known_nonexistent, set_nonexistent


def test_keygen():
    codes = set()
    for _ in range(1000):
        code = generate_short_code()
        assert code not in codes, f"Collision detected: {code}"
        codes.add(code)
    assert is_valid_alias("my-custom-slug")
    assert not is_valid_alias("a")  # too short
    assert not is_valid_alias("invalid/slug!")
    print("[PASS] Keygen & Snowflake tests passed (1,000 unique codes generated with 0 collisions).")


def test_rate_limiter():
    limiter = InMemorySlidingWindowLimiter()
    key = "test_client_ip"
    
    # Allow 5 requests in a 2-second window
    for i in range(5):
        allowed, remaining, reset_after = limiter.is_allowed(key, max_requests=5, window_seconds=2)
        assert allowed is True, f"Request {i+1} should be allowed"
        assert remaining == 4 - i
    
    # 6th request should be blocked
    allowed, remaining, reset_after = limiter.is_allowed(key, max_requests=5, window_seconds=2)
    assert allowed is False, "6th request should be blocked"
    assert remaining == 0
    assert reset_after > 0
    
    # Wait for window to expire
    time.sleep(2.1)
    allowed, remaining, _ = limiter.is_allowed(key, max_requests=5, window_seconds=2)
    assert allowed is True, "Request after window expiration should be allowed"
    print("[PASS] Sliding Window Rate Limiter tests passed.")


def test_auth_service():
    full_key, key_id, secret_hash = generate_api_key_pair()
    assert full_key.startswith("sk_live_")
    assert "." in full_key
    id_part, secret = full_key.split(".", 1)
    assert id_part == f"sk_live_{key_id}"
    assert hash_secret(secret) == secret_hash
    print("[PASS] O(1) API Key hashing and pair generation tests passed.")


def test_cache_layer():
    code = "test_xyz"
    data = {"long_url": "https://example.com", "clicks": 42}
    set_cached_url(code, data)
    cached = get_cached_url(code)
    assert cached == data
    invalidate_cached_url(code)
    assert get_cached_url(code) is None

    set_nonexistent("invalid_404")
    assert is_known_nonexistent("invalid_404") is True
    print("[PASS] Caching and Negative-Caching tests passed.")


if __name__ == "__main__":
    test_keygen()
    test_rate_limiter()
    test_auth_service()
    test_cache_layer()
    print("\n>>> ALL SYSTEM DESIGN & BACKEND TESTS PASSED SUCCESSFULLY! <<<")
