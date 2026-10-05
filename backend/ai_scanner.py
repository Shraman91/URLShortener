import re
import math
from urllib.parse import urlparse
from typing import Dict, Any, List

# Known high-risk or suspicious TLDs often abused in phishing/malware
SUSPICIOUS_TLDS = {
    ".zip", ".mov", ".top", ".xyz", ".click", ".link", ".download",
    ".gq", ".cf", ".ml", ".ga", ".tk", ".work", ".stream", ".cam",
    ".bid", ".monster", ".racing", ".accountant"
}

# Sensitive target brands commonly spoofed in credential theft
POPULAR_BRANDS = [
    "paypal", "google", "apple", "microsoft", "netflix", "amazon",
    "facebook", "instagram", "chase", "wellsfargo", "binance",
    "coinbase", "metamask", "steam", "discord", "telegram"
]

# Sensitive suspicious keywords
SUSPICIOUS_KEYWORDS = [
    "login", "signin", "verify", "security-update", "account-alert",
    "free-gift", "crypto-airdrop", "claim-reward", "password-reset",
    "bank-statement", "invoice-download", "kyc-update", "wallet-connect"
]


def calculate_entropy(text: str) -> float:
    """Calculates Shannon entropy to detect algorithmic randomness/DGA domains."""
    if not text:
        return 0.0
    prob = [float(text.count(c)) / len(text) for c in set(text)]
    return -sum(p * math.log2(p) for p in prob)


def scan_url_safety(url_str: str) -> Dict[str, Any]:
    """
    AI Link Intelligence & Threat Scanner:
    Evaluates URL structure, domain reputation, lexical entropy, brand impersonation,
    and protocol safety to compute a unified Safety Score (0-100) and risk verdict.
    """
    try:
        parsed = urlparse(url_str)
    except Exception:
        return {
            "safety_score": 30,
            "safety_verdict": "MALICIOUS",
            "category": "Suspicious",
            "flags": ["Malformed URL structure"],
            "entropy": 0.0
        }

    score = 100
    flags: List[str] = []
    category = "General Web"

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    full_text = url_str.lower()

    # 1. Protocol Security Check
    if scheme == "http":
        score -= 15
        flags.append("Insecure plain HTTP (No SSL/TLS)")
    elif scheme == "https":
        flags.append("SSL/TLS Encrypted")

    # 2. IP Address in Hostname (High Risk)
    ip_pattern = r"^(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?$"
    if re.match(ip_pattern, netloc):
        score -= 40
        flags.append("Direct IP address used instead of domain name")

    # 3. Suspicious TLD Detection
    for tld in SUSPICIOUS_TLDS:
        if netloc.endswith(tld):
            score -= 20
            flags.append(f"High-risk top-level domain ({tld})")
            break

    # 4. Excessive Subdomains (Deep tunneling)
    subdomain_parts = netloc.split(".")
    if len(subdomain_parts) > 4:
        score -= 15
        flags.append(f"Excessive subdomain depth ({len(subdomain_parts)} levels)")

    # 5. Phishing Brand Impersonation & Typosquatting
    domain_without_tld = subdomain_parts[0] if len(subdomain_parts) > 1 else netloc
    for brand in POPULAR_BRANDS:
        if brand in full_text:
            # Check if it is the legitimate root domain
            if not (netloc == f"{brand}.com" or netloc.endswith(f".{brand}.com")):
                score -= 30
                flags.append(f"Potential {brand.title()} brand spoofing / impersonation detected")

    # 6. Sensitive / Phishing Keyword Infiltration
    found_keywords = [kw for kw in SUSPICIOUS_KEYWORDS if kw in path or kw in query]
    if found_keywords:
        score -= min(30, len(found_keywords) * 15)
        flags.append(f"High-risk credential keywords: {', '.join(found_keywords)}")

    # 7. Lexical Entropy Analysis (Random DGA strings)
    entropy = round(calculate_entropy(domain_without_tld), 2)
    if entropy > 4.2 and len(domain_without_tld) > 12:
        score -= 20
        flags.append(f"High lexical randomness (Entropy: {entropy})")

    # 8. Excessive URL length
    if len(url_str) > 250:
        score -= 10
        flags.append("Obfuscated or excessively long URL parameters")

    # 9. Category Classification
    if any(k in netloc for k in ["github", "gitlab", "stackoverflow", "dev.to", "npmjs", "python"]):
        category = "Developer & Tech"
    elif any(k in netloc for k in ["youtube", "spotify", "netflix", "twitch", "vimeo"]):
        category = "Media & Entertainment"
    elif any(k in netloc for k in ["amazon", "ebay", "shopify", "walmart", "stripe"]):
        category = "E-Commerce & Retail"
    elif any(k in netloc for k in ["twitter", "x.com", "linkedin", "reddit", "facebook"]):
        category = "Social Platform"
    elif any(k in netloc for k in ["wikipedia", "medium", "substack", "nytimes", "bbc"]):
        category = "News & Knowledge"

    # Normalize score
    final_score = max(5, min(100, score))

    if final_score >= 85:
        verdict = "SAFE"
    elif final_score >= 65:
        verdict = "MODERATE"
    elif final_score >= 40:
        verdict = "SUSPICIOUS"
    else:
        verdict = "MALICIOUS"

    if not flags:
        flags.append("Clean Domain Reputation")
        flags.append("No Threat Vectors Detected")

    return {
        "safety_score": final_score,
        "safety_verdict": verdict,
        "category": category,
        "flags": flags,
        "entropy": entropy
    }
