"""Real-menu enrichment for demo sites.

Prefer structured public menus (Google-listed website, Yelp, Toast, Square,
DoorDash / Uber Eats). Fall back to OCR of a public menu photo when that is
the only confident source. If nothing usable is found, return None so the
generator keeps its labeled samples — never invent dishes and call them real.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import os
import re
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from config import DEMO_DIR, GOOGLE_PLACES_API_KEY

GOOGLE_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Same overlap rule as scanner.scanner.name_matches — kept local so this
# module does not import db (libsql) just to score a place name.
_STOP = {"the", "and", "a", "of", "restaurant", "cafe", "coffee", "bar",
         "grill", "kitchen", "llc", "inc", "co"}


def _norm_tokens(s: str) -> set:
    flat = (s or "").lower().replace("'", "").replace("\u2019", "")
    return {w for w in re.findall(r"[a-z0-9]+", flat) if w not in _STOP}


def name_matches(queried: str, returned: str, threshold: float = 0.6) -> bool:
    a, b = _norm_tokens(queried), _norm_tokens(returned)
    if not a or not b:
        return False
    return len(a & b) / len(min(a, b, key=len)) >= threshold

# Optional. Fusion is nicer than HTML when present; HTML /menu/{alias} still works.
YELP_API_KEY = os.getenv("YELP_API_KEY", "").strip()

TIMEOUT_DEFAULT = 12
CACHE_TTL_S = 7 * 24 * 3600
MIN_ITEMS = 3
MAX_ITEMS = 8
MAX_PRICE = 120.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
SSL_CTX = ssl.create_default_context()

SOURCE_LABELS = {
    "google": "from Google",
    "website": "from their website",
    "yelp": "from Yelp",
    "toast": "from Toast",
    "square": "from Square",
    "doordash": "from DoorDash",
    "ubereats": "from Uber Eats",
    "listing": "from a public menu listing",
    "photo": "from a menu photo",
    "social": "from a public menu photo",
}

# First-party / ordering hosts beat scrapers. Aggregators are last-resort listings.
_HOST_SOURCE = (
    (("toasttab.com", "toast.com"), "toast"),
    (("square.site", "squareup.com", "square.online"), "square"),
    (("doordash.com",), "doordash"),
    (("ubereats.com", "postmates.com"), "ubereats"),
    (("yelp.com",), "yelp"),
    (("facebook.com", "instagram.com"), "social"),
    (("google.com", "googleusercontent.com"), "google"),
    (("roostcafeandbistro.com", "allmenus.com", "zmenu.com", "menupix.com",
      "restaurantji.com", "restaurantguru.com", "wherevi.com", "kwickmenu.com",
      "res-pick.com", "sirved.com", "checkle.com", "menustatic.com"),
     "listing"),
)

_SKIP_HOSTS = (
    "duckduckgo.com", "bing.com", "google.com/search", "youtube.com",
    "wikipedia.org", "reddit.com",
)

_SECTION_WORDS = {
    "menu", "breakfast", "lunch", "dinner", "appetizers", "desserts",
    "drinks", "sides", "kids", "beverages", "specials", "entrees",
    "sandwiches", "omelettes", "hours", "about",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}

_NOISE_NAME = re.compile(
    r"^(add |extra |choice of|served with|for children|information|address|"
    r"phone|opening|hours|menu|see more|read more)",
    re.I,
)

_PRICE_RE = re.compile(r"\$(\d{1,3}(?:\.\d{2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class MenuItem:
    name: str
    description: str = ""
    price: float | None = None

    def as_tuple(self) -> tuple:
        return (self.name, self.description, self.price)


@dataclass
class MenuResult:
    items: list[MenuItem]
    source: str
    source_url: str = ""
    source_label: str = ""
    confidence: str = "high"

    def __post_init__(self):
        if not self.source_label:
            self.source_label = SOURCE_LABELS.get(self.source, f"from {self.source}")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_label": self.source_label,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "items": [asdict(i) for i in self.items],
        }


# --------------------------------------------------------------------------- cache
_mem: dict[str, tuple[float, dict | None]] = {}


def _cache_key(name: str, address: str, website: str = "") -> str:
    blob = f"{(name or '').lower()}|{(address or '').lower()}|{(website or '').lower()}"
    return hashlib.sha1(blob.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return Path(DEMO_DIR) / "menu-cache" / f"{key}.json"


def _cache_get(key: str) -> dict | None:
    now = time.time()
    hit = _mem.get(key)
    if hit and now - hit[0] < CACHE_TTL_S:
        return hit[1]
    path = _cache_path(key)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    saved = float(data.get("cached_at") or 0)
    if now - saved > CACHE_TTL_S:
        return None
    payload = data.get("result")
    _mem[key] = (saved, payload)
    return payload


def _cache_put(key: str, result: MenuResult | None) -> None:
    payload = result.to_dict() if result else None
    now = time.time()
    _mem[key] = (now, payload)
    path = _cache_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cached_at": now, "result": payload}, indent=2))
    except OSError:
        pass


def enrich_enabled() -> bool:
    return os.getenv("MENU_ENRICH", "1").lower() not in {"0", "false", "no"}


# --------------------------------------------------------------------------- HTTP
class Deadline:
    def __init__(self, seconds: float):
        self.end = time.monotonic() + max(0.2, seconds)

    def remaining(self) -> float:
        return max(0.0, self.end - time.monotonic())

    def expired(self) -> bool:
        return self.remaining() <= 0


def fetch_url(url: str, timeout: float = TIMEOUT_DEFAULT, binary: bool = False):
    """Return (final_url, body) or (None, None). Body is str unless binary=True."""
    if not url:
        return None, None
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
    })
    try:
        with urllib.request.urlopen(req, timeout=max(2, timeout), context=SSL_CTX) as r:
            data = r.read()
            final = r.geturl()
            if binary:
                return final, data
            return final, data.decode("utf-8", "replace")
    except Exception:
        return None, None


def _hostname(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower()


def source_for_url(url: str) -> str:
    host = _hostname(url)
    path = urllib.parse.urlparse(url).path.lower()
    for needles, source in _HOST_SOURCE:
        for n in needles:
            if host == n or host.endswith("." + n):
                if source == "listing" and "menu" in path and "restaurantji" in host:
                    return "photo" if path.endswith((".jpg", ".jpeg", ".png", ".webp")) else "listing"
                return source
    return "website"


def _skip_url(url: str) -> bool:
    low = (url or "").lower()
    return any(s in low for s in _SKIP_HOSTS)


# --------------------------------------------------------------------------- parse
def _clean_text(value) -> str:
    text = html_module.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip(" \t\n\r-:·•|")


def _parse_price(value, require_dollar: bool = False) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        return n if 0 < n <= MAX_PRICE else None
    s = str(value)
    if require_dollar or "$" in s:
        m = _PRICE_RE.search(s)
    else:
        # JSON-LD offers.price is a bare number. Do not scan prose for
        # "7:00 AM" / "7AM–4:30PM" and call that a dish price.
        m = re.fullmatch(r"\s*(\d{1,3}(?:\.\d{2})?)\s*", s)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    return n if 0 < n <= MAX_PRICE else None


def _good_name(name: str) -> bool:
    n = _clean_text(name)
    if len(n) < 3 or len(n) > 70:
        return False
    if n.lower() in _SECTION_WORDS:
        return False
    if _NOISE_NAME.search(n):
        return False
    letters = sum(ch.isalpha() for ch in n)
    return letters >= 3 and letters / max(len(n), 1) >= 0.35


def _dedupe(items: Iterable[MenuItem]) -> list[MenuItem]:
    seen = set()
    out = []
    for it in items:
        key = re.sub(r"[^a-z0-9]+", "", it.name.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _confident(items: list[MenuItem]) -> bool:
    usable = [i for i in items if _good_name(i.name)]
    priced = [i for i in usable if i.price]
    return len(usable) >= MIN_ITEMS and (len(priced) >= 2 or len(usable) >= 5)


def walk_jsonld_items(node, acc=None) -> list[MenuItem]:
    if acc is None:
        acc = []
    if isinstance(node, list):
        for x in node:
            walk_jsonld_items(x, acc)
        return acc
    if not isinstance(node, dict):
        return acc
    types = node.get("@type") or node.get("type") or ""
    if isinstance(types, list):
        types = " ".join(str(t) for t in types)
    types = str(types)
    if re.search(r"MenuItem", types, re.I):
        name = _clean_text(node.get("name") or node.get("title") or "")
        desc = _clean_text(node.get("description") or "")
        price = None
        offers = node.get("offers")
        if isinstance(offers, dict):
            price = _parse_price(offers.get("price") or offers.get("lowPrice"))
        elif isinstance(offers, list) and offers:
            price = _parse_price(offers[0].get("price") if isinstance(offers[0], dict) else offers[0])
        if price is None:
            price = _parse_price(node.get("price") or node.get("priceRange"))
        if _good_name(name):
            acc.append(MenuItem(name, desc, price))
    for v in node.values():
        if isinstance(v, (dict, list)):
            walk_jsonld_items(v, acc)
    return acc


def parse_jsonld_menu(text: str) -> list[MenuItem]:
    items: list[MenuItem] = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text or "", re.S | re.I,
    ):
        raw = m.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        walk_jsonld_items(data, items)
    return _dedupe(items)


def parse_html_menu(text: str) -> list[MenuItem]:
    """Conservative name + $price extraction from common menu markup."""
    items: list[MenuItem] = []
    named = re.findall(
        r'class="[^"]*cus-menu-text-name[^"]*"[^>]*>(.*?)</span>(.*?)</td>\s*<td[^>]*>\s*(\$[\d.]+)',
        text or "", re.S | re.I,
    )
    for name, desc, price in named:
        n = _clean_text(name)
        if _good_name(n):
            items.append(MenuItem(n, _clean_text(desc), _parse_price(price, require_dollar=True)))
    if _confident(items):
        return _dedupe(items)

    row_re = re.compile(
        r"<tr[^>]*>\s*<t[dh][^>]*>(.*?)</t[dh]>\s*(?:<t[dh][^>]*>(.*?)</t[dh]>\s*)?<t[dh][^>]*>(.*?)</t[dh]>",
        re.S | re.I,
    )
    for m in row_re.finditer(text or ""):
        cells = [_clean_text(c) for c in m.groups() if c is not None]
        if not cells:
            continue
        price = None
        name = cells[0]
        desc = ""
        for cell in reversed(cells):
            p = _parse_price(cell, require_dollar=True)
            if p:
                price = p
                break
        if len(cells) >= 3:
            desc = cells[1]
        if _good_name(name) and price:
            items.append(MenuItem(name, desc, price))
    if _confident(items):
        return _dedupe(items)

    # Yelp HTML cards: heading + nearby $amount
    for m in re.finditer(
        r'<h4[^>]*>(.*?)</h4>.*?<li class="menu-item-price-amount">\s*(\$[\d.]+)',
        text or "", re.S | re.I,
    ):
        n = _clean_text(m.group(1))
        if _good_name(n):
            items.append(MenuItem(n, "", _parse_price(m.group(2), require_dollar=True)))
    return _dedupe(items)


def parse_embedded_json_menu(text: str) -> list[MenuItem]:
    """Toast / Square / DoorDash pages often stash items in a JSON blob."""
    items: list[MenuItem] = []
    for m in re.finditer(r'<script[^>]*>(.*?)</script>', text or "", re.S | re.I):
        blob = m.group(1)
        if not re.search(r'"(?:price|unitPrice|amount)"\s*:', blob):
            continue
        if len(blob) > 2_000_000:
            continue
        for obj in re.finditer(
            r'\{[^{}]{0,400}"(?:name|title|itemName)"\s*:\s*"([^"]{3,80})"[^{}]{0,400}'
            r'"(?:price|unitPrice|amount)"\s*:\s*"?(\d+(?:\.\d{1,2})?)"?',
            blob,
        ):
            n = _clean_text(obj.group(1))
            if _good_name(n):
                items.append(MenuItem(n, "", _parse_price(obj.group(2))))
        if not items:
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            walk_jsonld_items(data, items)
    return _dedupe(items)


def parse_ocr_text(text: str) -> list[MenuItem]:
    """Turn OCR / photo text into items only when a name and price sit together."""
    items: list[MenuItem] = []
    if not text:
        return items
    lines = [_clean_text(ln) for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    pending = ""
    for ln in lines:
        price = _parse_price(ln, require_dollar=True)
        name_part = _PRICE_RE.sub("", ln).strip(" .-$")
        if price and _good_name(name_part):
            items.append(MenuItem(name_part, "", price))
            pending = ""
            continue
        if price and _good_name(pending):
            items.append(MenuItem(pending, name_part if name_part != pending else "", price))
            pending = ""
            continue
        if _good_name(ln) and not price:
            pending = ln
    return _dedupe(items)


def parse_any(text: str) -> list[MenuItem]:
    for parser in (parse_jsonld_menu, parse_html_menu, parse_embedded_json_menu):
        items = parser(text)
        if _confident(items):
            return items
    return []


# --------------------------------------------------------------------------- OCR
def ocr_image_bytes(data: bytes) -> str:
    if not data:
        return ""
    tesseract = _which("tesseract")
    if not tesseract:
        return ""
    suffix = ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        suffix = ".png"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            path = f.name
        result = subprocess.run(
            [tesseract, path, "stdout", "--psm", "6"],
            capture_output=True, text=True, timeout=20,
        )
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _which(cmd: str) -> str | None:
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        cand = Path(folder) / cmd
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


# --------------------------------------------------------------------------- discovery
def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-")


def guessed_menu_urls(name: str, address: str = "", city: str = "") -> list[str]:
    """Cheap first-party guesses — no search API required."""
    city_bit = _slug(city or "houston")
    name_slug = _slug(name)
    zip_m = re.search(r"\b(\d{5})\b", address or "")
    zip_code = zip_m.group(1) if zip_m else ""
    urls = [
        f"https://www.yelp.com/menu/{name_slug}-{city_bit}",
        f"https://www.yelp.com/menu/{name_slug}-{city_bit}-2",
        f"https://www.yelp.com/menu/{name_slug}",
        f"https://www.restaurantji.com/tx/{city_bit}/{name_slug}-/",
    ]
    if zip_code:
        urls.append(f"https://www.roostcafeandbistro.com/{name_slug}-{zip_code}/")
    return urls


def ddg_menu_urls(name: str, city: str, deadline: Deadline | None = None) -> list[str]:
    q = f'{name} {city} menu'
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q})
    timeout = deadline.remaining() if deadline else TIMEOUT_DEFAULT
    _, text = fetch_url(url, timeout=min(timeout, 8))
    if not text:
        return []
    out = []
    for raw in re.findall(r'uddg=([^&"]+)', text):
        link = urllib.parse.unquote(raw)
        if not link.startswith("http") or _skip_url(link):
            continue
        if link not in out:
            out.append(link)
    return out[:12]


def google_place_for_menu(name: str, address: str, deadline: Deadline | None = None) -> dict:
    """Website + photo names from Places. Empty if no key / no match."""
    if not GOOGLE_PLACES_API_KEY:
        return {}
    timeout = deadline.remaining() if deadline else 12
    if timeout < 2:
        return {}
    body = json.dumps({"textQuery": f"{name}, {address}", "maxResultCount": 1}).encode()
    req = urllib.request.Request(GOOGLE_SEARCH_URL, body, {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": (
            "places.websiteUri,places.displayName,places.photos,places.googleMapsUri"
        ),
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            data = json.load(r)
    except Exception:
        return {}
    places = data.get("places") or []
    if not places:
        return {}
    p = places[0]
    returned = ((p.get("displayName") or {}).get("text")) or ""
    if returned and not name_matches(name, returned):
        return {}
    photos = []
    for ph in (p.get("photos") or [])[:6]:
        nm = ph.get("name")
        if nm:
            photos.append(nm)
    return {"website": p.get("websiteUri") or "", "photos": photos,
            "maps": p.get("googleMapsUri") or ""}


def google_photo_bytes(photo_name: str, deadline: Deadline | None = None) -> bytes:
    if not GOOGLE_PLACES_API_KEY or not photo_name:
        return b""
    timeout = deadline.remaining() if deadline else 10
    url = (
        f"https://places.googleapis.com/v1/{photo_name}/media"
        f"?maxHeightPx=1400&key={urllib.parse.quote(GOOGLE_PLACES_API_KEY)}"
    )
    _, data = fetch_url(url, timeout=timeout, binary=True)
    return data or b""


def yelp_fusion_urls(name: str, address: str, city: str) -> list[str]:
    if not YELP_API_KEY:
        return []
    loc = address or city or "Houston, TX"
    q = urllib.parse.urlencode({"term": name, "location": loc, "limit": 3})
    req = urllib.request.Request(
        f"https://api.yelp.com/v3/businesses/search?{q}",
        headers={"Authorization": f"Bearer {YELP_API_KEY}", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as r:
            data = json.load(r)
    except Exception:
        return []
    urls = []
    for biz in data.get("businesses") or []:
        biz_name = biz.get("name") or ""
        if biz_name and not name_matches(name, biz_name):
            continue
        alias = biz.get("alias") or ""
        if alias:
            urls.append(f"https://www.yelp.com/menu/{alias}")
        if biz.get("url"):
            urls.append(biz["url"])
    return urls


def _rank_urls(urls: Iterable[str]) -> list[str]:
    rank = {
        "toast": 0, "square": 1, "website": 2, "yelp": 3,
        "doordash": 4, "ubereats": 5, "google": 6, "listing": 7,
        "social": 8, "photo": 9,
    }
    seen = set()
    out = []
    for u in urls:
        if not u or u in seen or _skip_url(u):
            continue
        seen.add(u)
        out.append(u)
    return sorted(out, key=lambda u: rank.get(source_for_url(u), 9))


def extract_page_links(base_url: str, text: str) -> list[str]:
    links = []
    for href in re.findall(r'href=["\'](https?://[^"\']+|/[a-zA-Z0-9][^"\']*)', text or ""):
        url = urllib.parse.urljoin(base_url, html_module.unescape(href.split("#")[0]))
        host = _hostname(url)
        path = urllib.parse.urlparse(url).path.lower()
        src = source_for_url(url)
        if src in {"toast", "square", "doordash", "ubereats", "yelp"}:
            links.append(url)
        elif "menu" in path and src in {"website", "listing"}:
            links.append(url)
        elif host and "menu" in path:
            links.append(url)
    return links


def menu_photos_from_html(text: str) -> list[str]:
    urls = []
    for u in re.findall(r'https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*', text or "", re.I):
        if "menu" in u.lower():
            urls.append(u.split("?")[0] if "localdatacdn.com" in u else u)
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text or "", re.S | re.I,
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        blob = json.dumps(data)
        for u in re.findall(r'https://[^"\\]+\.(?:jpg|jpeg|png|webp)[^"\\]*', blob, re.I):
            if "menu" in u.lower() and u not in urls:
                urls.append(u)
    return urls[:6]


def _page_title(text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", text or "", re.S | re.I)
    return _clean_text(m.group(1)) if m else ""


def strict_name_matches(queried: str, returned: str, threshold: float = 0.7) -> bool:
    """Jaccard match. The scanner's overlap-on-shorter rule would accept
    'Cream Parlor' for 'Hank's Ice Cream Parlor' — that is a different shop."""
    noise = {"menu", "houston", "tx", "texas", "prices", "order", "online",
             "gift", "gifts"}
    a, b = _norm_tokens(queried) - noise, _norm_tokens(returned) - noise
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= threshold


def url_names_business(name: str, url: str) -> bool:
    """True only when the path/host is this business's slug, not a substring
    of a longer parlor/grill name."""
    slug = _slug(name)
    if not slug or not url:
        return False
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if host == slug or host.startswith(slug + "."):
        return True
    for seg in path.strip("/").split("/"):
        if seg == slug or seg.startswith(slug + "-"):
            return True
    return False


def _accept_page(name: str, url: str, text: str) -> bool:
    """Reject a menu that belongs to a different restaurant."""
    if not text:
        return False
    if url_names_business(name, url):
        return True
    title = _page_title(text)
    return bool(title and strict_name_matches(name, title))


def _result_from_items(items: list[MenuItem], url: str, source: str | None = None,
                       confidence: str = "high") -> MenuResult | None:
    items = [i for i in _dedupe(items) if _good_name(i.name)]
    if not _confident(items):
        return None
    # Prefer priced highlights; keep order so section variety survives.
    priced = [i for i in items if i.price]
    rest = [i for i in items if not i.price]
    picked = (priced or items)[:MAX_ITEMS]
    if len(picked) < MIN_ITEMS:
        picked = items[:MAX_ITEMS]
    src = source or source_for_url(url)
    if src == "photo":
        confidence = "medium"
    return MenuResult(items=picked, source=src, source_url=url, confidence=confidence)


def _try_url(url: str, name: str, deadline: Deadline) -> MenuResult | None:
    if deadline.expired() or not url:
        return None
    final, text = fetch_url(url, timeout=min(deadline.remaining(), TIMEOUT_DEFAULT))
    if not text or not _accept_page(name, final or url, text):
        return None
    items = parse_any(text)
    got = _result_from_items(items, final or url)
    if got:
        return got
    # Follow menu-ish links on the same site once.
    for link in extract_page_links(final or url, text)[:4]:
        if deadline.expired():
            break
        if source_for_url(link) == source_for_url(url) or "menu" in link.lower():
            f2, t2 = fetch_url(link, timeout=min(deadline.remaining(), 8))
            if t2 and _accept_page(name, f2 or link, t2):
                got = _result_from_items(parse_any(t2), f2 or link)
                if got:
                    return got
    return None


def _try_photos(urls: list[str], deadline: Deadline, source: str = "photo") -> MenuResult | None:
    for url in urls[:4]:
        if deadline.expired():
            return None
        final, data = fetch_url(url, timeout=min(deadline.remaining(), 10), binary=True)
        if not data or len(data) < 4000:
            continue
        text = ocr_image_bytes(data)
        items = parse_ocr_text(text)
        got = _result_from_items(items, final or url, source=source, confidence="medium")
        if got:
            return got
    return None


def result_from_dict(data: dict | None) -> MenuResult | None:
    if not data or not data.get("items"):
        return None
    items = [MenuItem(
        name=str(i.get("name") or ""),
        description=str(i.get("description") or ""),
        price=_parse_price(i.get("price")),
    ) for i in data["items"]]
    return _result_from_items(
        items, data.get("source_url") or "", source=data.get("source") or "listing",
        confidence=data.get("confidence") or "high",
    )


def enrich_menu(name: str, address: str = "", website: str = "", city: str = "",
                deadline_s: float = 18.0, use_cache: bool = True) -> MenuResult | None:
    """Return sourced menu items, or None to keep labeled samples."""
    if not enrich_enabled() or not (name or "").strip():
        return None
    key = _cache_key(name, address, website)
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return result_from_dict(cached) if cached else None

    deadline = Deadline(deadline_s)
    city = city or "houston"
    place = google_place_for_menu(name, address or city, deadline)
    website = website or (place.get("website") if place else "") or ""

    urls = []
    if website:
        urls.append(website)
    urls.extend(yelp_fusion_urls(name, address, city))
    urls.extend(guessed_menu_urls(name, address, city))
    if not deadline.expired():
        urls.extend(ddg_menu_urls(name, city, deadline))
    urls = _rank_urls(urls)

    found: MenuResult | None = None
    photo_pages = []
    for url in urls[:10]:
        if deadline.expired():
            break
        got = _try_url(url, name, deadline)
        if got:
            found = got
            break
        # Keep listing pages around — they often host a menu photo.
        src = source_for_url(url)
        if src in {"listing", "social", "website"}:
            photo_pages.append(url)

    if not found:
        photo_urls = []
        for page in photo_pages[:4]:
            if deadline.expired():
                break
            _, text = fetch_url(page, timeout=min(deadline.remaining(), 8))
            if text:
                photo_urls.extend(menu_photos_from_html(text))
        for ph in place.get("photos") or []:
            # Places photo names are not http URLs; fetch bytes directly below.
            pass
        found = _try_photos(_rank_urls(photo_urls), deadline, source="photo")
        if not found and place.get("photos"):
            for pn in place["photos"][:3]:
                if deadline.expired():
                    break
                data = google_photo_bytes(pn, deadline)
                items = parse_ocr_text(ocr_image_bytes(data))
                found = _result_from_items(
                    items, place.get("maps") or "", source="google", confidence="medium")
                if found:
                    break

    if use_cache:
        _cache_put(key, found)
    return found


# --------------------------------------------------------------------------- prototypes / CLI
PROTOTYPES = (
    {
        "name": "Thien An Sandwiches",
        "address": "2611 San Jacinto St, Houston, TX 77004",
        "phone": "(713) 522-7007",
        "category": "restaurant",
        "city": "houston",
        "token": "EBMKiuowROVS",
        "rating": 4.5,
    },
    {
        "name": "Cream Parlor",
        "address": "Houston, TX",
        "phone": "",
        "category": "cafe",
        "city": "houston",
        "token": "QDfZzeoBRE9n",
        "rating": 4.8,
    },
    {
        "name": "Yale Street Grill",
        "address": "2100 Yale St, Houston, TX 77008",
        "phone": "(713) 861-3113",
        "category": "restaurant",
        "city": "houston",
        "token": "wa2LGwK--aBb",
        "rating": 4.3,
    },
)


def enrich_prototypes(deadline_s: float = 22.0) -> list[dict]:
    rows = []
    for spec in PROTOTYPES:
        result = enrich_menu(
            spec["name"], spec["address"], city=spec["city"], deadline_s=deadline_s)
        rows.append({
            "name": spec["name"],
            "token": spec["token"],
            "address": spec["address"],
            "enriched": bool(result),
            "source": result.source if result else None,
            "source_label": result.source_label if result else None,
            "source_url": result.source_url if result else None,
            "fallback": None if result else "labeled-sample",
            "items": [asdict(i) for i in result.items] if result else [],
        })
    return rows


def _print_report(rows: list[dict]) -> None:
    for row in rows:
        print(f"\n== {row['name']}  token={row['token']}")
        if row["enriched"]:
            print(f"   sourced {row['source_label']}  ({row['source_url']})")
            for it in row["items"]:
                price = f"${it['price']:.2f}" if it.get("price") else "Ask"
                desc = f" — {it['description']}" if it.get("description") else ""
                print(f"   • {it['name']}  {price}{desc}")
        else:
            print("   no confident public menu — keeping labeled samples (not claimed as real)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover real menus for demo sites.")
    parser.add_argument("--prototypes", action="store_true",
                        help="Enrich Thien An / Cream Parlor / Yale Street Grill and write a report.")
    parser.add_argument("--name", default="", help="Business name")
    parser.add_argument("--address", default="", help="Address")
    parser.add_argument("--city", default="houston")
    parser.add_argument("--write-html", action="store_true",
                        help="Also generate prototype demo HTML under demos/prototypes/")
    args = parser.parse_args()

    if args.prototypes or args.write_html:
        rows = enrich_prototypes()
        _print_report(rows)
        out = Path(DEMO_DIR) / "prototypes"
        out.mkdir(parents=True, exist_ok=True)
        (out / "enrich-report.json").write_text(json.dumps(rows, indent=2))
        print(f"\nwrote {out / 'enrich-report.json'}")
        if args.write_html:
            from generator import generate_site
            for spec, row in zip(PROTOTYPES, rows):
                html, _ = generate_site(
                    spec["name"], spec["address"], spec["phone"], spec["category"],
                    spec["rating"], spec["city"], use_ai=False, enrich_menu=True,
                    menu=row if row["enriched"] else None,
                )
                path = out / f"{_slug(spec['name'])}.html"
                path.write_text(html)
                print(f"wrote {path}")
    elif args.name:
        result = enrich_menu(args.name, args.address, city=args.city)
        if result:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print("null")
            raise SystemExit(2)
    else:
        parser.print_help()
