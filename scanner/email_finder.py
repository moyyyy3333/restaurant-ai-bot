"""
Best-effort email discovery for leads the scanner found with no email.

Sources tried in order:
1. Scrape the business website/social page (stdlib only).
2. Hunter.io domain search (free tier: 25 searches/month).
3. Apollo.io enrichment (free tier: 100 credits).

Places APIs (LocationIQ, Google) never return a business's email — privacy
policy on their end, not a gap here.
"""

import re
import urllib.error
import urllib.parse
import urllib.request

from config import APOLLO_API_KEY, HUNTER_API_KEY

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Platform/tooling addresses that show up in page source but aren't the
# business's real contact — picking one of these would just bounce or annoy.
JUNK_DOMAINS = (
    "sentry.io", "wixpress.com", "example.com", "godaddy.com", "schema.org",
    "w3.org", "google-analytics.com", "googleapis.com", "gstatic.com",
    "facebook.com", "instagram.com", "cloudflare.com", "yelp.com",
)
JUNK_LOCAL_PARTS = ("noreply", "no-reply", "donotreply", "postmaster", "webmaster")


def _looks_junk(email: str) -> bool:
    local, _, domain = email.lower().partition("@")
    if any(local.startswith(p) for p in JUNK_LOCAL_PARTS):
        return True
    if any(domain == d or domain.endswith("." + d) for d in JUNK_DOMAINS):
        return True
    if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
        return True  # regex sometimes catches "icon@2x.png"-style asset names
    return False


def scrape_email(url: str, timeout: int = 12) -> str:
    """Fetch url and return the first plausible contact email found, or ""."""
    if not url:
        return ""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LocalBizBot/1.0; +contact-lookup)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read(500_000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return ""

    for match in EMAIL_RE.findall(html):
        if not _looks_junk(match):
            return match
    return ""


def find_email(business_name: str, website: str, website_status: str) -> str:
    """Entry point used by the pipeline. Tries multiple sources in order:
    1. Scrape the business website/social page (stdlib only).
    2. Hunter.io domain search (free tier: 25 searches/month).
    3. Apollo.io enrichment (free tier: 100 credits).
    Returns the first email found, or "" if none.
    """
    # Source 1: scrape the website directly
    if website_status in ("social_only", "has_site") and website:
        email = scrape_email(website)
        if email:
            return email

    # Source 2: Hunter.io domain search
    domain = _extract_domain(website) or _extract_domain(business_name)
    if domain and HUNTER_API_KEY:
        email = _hunter_search(domain)
        if email:
            return email

    # Source 3: Apollo.io enrichment
    if domain and APOLLO_API_KEY:
        email = _apollo_search(domain)
        if email:
            return email

    return ""


def _extract_domain(text: str) -> str:
    """Extract a domain from a URL, email, or business name."""
    if not text:
        return ""
    # Already a domain
    if "." in text and " " not in text and "@" not in text:
        return text
    # Extract from URL
    if "://" in text:
        from urllib.parse import urlparse
        parsed = urlparse(text)
        if parsed.netloc:
            return parsed.netloc
    # Extract from email
    if "@" in text:
        return text.split("@")[-1]
    # Extract from business name (e.g. "Uchi Houston" → uchi.com)
    # Try common TLDs
    for tld in (".com", ".org", ".net", ".co"):
        candidate = text.lower().replace(" ", "") + tld
        if "." in candidate:
            return candidate
    return ""


def _hunter_search(domain: str) -> str:
    """Search Hunter.io for an email associated with a domain."""
    url = f"https://api.hunter.io/v2/domain-search?domain={urllib.parse.quote(domain)}&api_key={HUNTER_API_KEY}"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.loads(r.read())
            emails = data.get("data", {}).get("emails", [])
            if emails:
                return emails[0].get("value", "")
    except Exception:
        pass
    return ""


def _apollo_search(domain: str) -> str:
    """Search Apollo.io for an email associated with a domain."""
    url = f"https://api.apollo.io/v1/mixed_company/search?q={urllib.parse.quote(domain)}&api_key={APOLLO_API_KEY}"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.loads(r.read())
            contacts = data.get("contacts", [])
            if contacts:
                return contacts[0].get("email", "")
    except Exception:
        pass
    return ""
