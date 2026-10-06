import time
from keygen import generate_short_code, is_valid_alias
from rate_limiter import check_rate_limit, InMemorySlidingWindowLimiter, is_bot_or_crawler
from auth_service import generate_api_key_pair, hash_secret
from cache import get_cached_url, set_cached_url, invalidate_cached_url, is_known_nonexistent, set_nonexistent
from ai_scanner import scan_url_safety, check_domain_blocklist


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

    # Bot crawler detection test
    assert is_bot_or_crawler("Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)") is True
    assert is_bot_or_crawler("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0") is False
    print("[PASS] Sliding Window Rate Limiter & Bot Detection tests passed.")


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


def test_ai_scanner_and_blocklist():
    # 1. Clean URL
    clean = scan_url_safety("https://github.com/fastapi/fastapi")
    assert clean["safety_score"] >= 85
    assert clean["safety_verdict"] == "SAFE"
    assert clean["category"] == "Developer & Tech"

    # 2. Malicious Phishing Spoof
    phish = scan_url_safety("http://paypal-security-update.crypto-airdrop.xyz/login/verify")
    assert phish["safety_score"] < 40
    assert phish["safety_verdict"] == "MALICIOUS"

    # 3. Blocklist
    blocked, reason = check_domain_blocklist("https://subdomain.malicious.com/payload")
    assert blocked is True
    assert "blocked" in reason.lower()

    allowed, _ = check_domain_blocklist("https://google.com")
    assert allowed is False
    print("[PASS] AI Threat Scanner & Domain Blocklist tests passed.")


if __name__ == "__main__":
    test_keygen()
    test_rate_limiter()
    test_auth_service()
    test_cache_layer()
    test_ai_scanner_and_blocklist()
    print("\n>>> ALL SYSTEM DESIGN & BACKEND TESTS PASSED SUCCESSFULLY! <<<")
