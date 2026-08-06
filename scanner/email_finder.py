"""
Best-effort email discovery for leads the scanner found with no email.

Places APIs (LocationIQ, Google) never return a business's email — privacy
policy on their end, not a gap here. The only public source left is whatever
page classify_website() already found (a Facebook/Instagram/Linktree/Yelp
page), which sometimes lists a contact email in its plain HTML. This scrapes
that one page. If a business has no site *and* no social page (website_status
== "none"), there's nothing to scrape and find_email() correctly returns "".

Stdlib only. One GET per lead, a regex, and a junk filter — no scraping
framework needed for "read one page, find one string".
"""

import re
import urllib.error
import urllib.request

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
    """Entry point used by the pipeline. Only social_only/has_site leads carry
    a URL worth scraping — "none" means no page was ever found to check."""
    if website_status not in ("social_only", "has_site") or not website:
        return ""
    return scrape_email(website)
