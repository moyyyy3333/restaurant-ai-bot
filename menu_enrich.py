"""Pull real menu items for a demo when a public source is available.

Fail closed: if we cannot fetch and parse a public menu / order page (or a
public menu photo), return None. The generator then keeps the labeled sample.
Never invent dishes and present them as the restaurant's menu.

Discovery order:
  1. Google Places websiteUri (and any menu / food-order links we were given)
  2. Links on that page to known order hosts (Toast, Square, DoorDash, …)
     or an obvious /menu path
  3. Public IG/FB menu-photo OCR when a public image URL is already in hand
     (skip login walls and 401/403)

Called from generate_site when fetch_place/fetch_menu is on (demo rebuild).
"""

from __future__ import annotations

import html as htmlmod
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

# Hosts that publish a structured menu we can try to parse.
ORDER_HOSTS = (
    "toasttab.com", "toast.com",
    "square.site", "squareup.com", "square.online",
    "doordash.com", "ubereats.com", "grubhub.com", "postmates.com",
    "chownow.com", "thanx.com", "slicelife.com",
    "menufy.com", "clover.com", "owner.com",
    "singleplatform.com", "gotoeat.net",
)

SOCIAL_HOSTS = ("instagram.com", "facebook.com", "m.facebook.com", "fb.com")

_MENU_PATH_HINTS = ("/menu", "/menus", "/our-menu", "/food-menu", "/order",
                    "/ordering", "/online-order", "/online-ordering")
_MENU_LINK_WORDS = re.compile(
    r"\b(menu|order\s*online|order\s*now|food\s*order|view\s*menu|full\s*menu)\b",
    re.I,
)
_SKIP_TITLES = {
    "home", "about", "contact", "cart", "login", "sign in", "privacy",
    "terms", "delivery", "pickup", "hours", "location", "order now",
    "view menu", "full menu", "see menu", "order online", "menu",
    "appetizers", "entrees", "desserts", "drinks", "beverages",
    "must-try menu", "featured items",
}
_PRICE_RE = re.compile(r"(?:US\s*)?\$\s*(\d{1,3}(?:\.\d{1,2})?)")
_BARE_PRICE_RE = re.compile(r"^\s*(\d{1,3}\.\d{2})\s*$")
_ITEM_LINE_RE = re.compile(
    r"^\s*(.{3,60}?)\s+(?:US\s*)?\$\s*(\d{1,3}(?:\.\d{1,2})?)\s*$",
    re.I,
)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
_BLOCKED = {401, 403, 405, 406, 429, 503}

_CACHE: dict = {}
_MAX_ITEMS = 8
_MIN_ITEMS = 3
_MAX_BYTES = 400_000


def enrich_menu(name: str, address: str = "", website: str = "",
                extra_urls=(), timeout: float = 6.0) -> dict | None:
    """Return {items, source, source_url, source_label} or None.

    items are (title, desc, price_or_None). price is a number when the source
    printed one; we never fill a missing price.
    """
    key = (name or "").lower().strip(), (address or "").lower().strip(), (website or "").strip()
    if key in _CACHE:
        cached = _CACHE[key]
        return dict(cached) if cached else None

    deadline = time.monotonic() + max(1.0, float(timeout))
    try:
        result = _enrich_uncached(name, address, website, extra_urls, deadline)
    except Exception:
        result = None
    _CACHE[key] = dict(result) if result else None
    return dict(result) if result else None


def _enrich_uncached(name, address, website, extra_urls, deadline) -> dict | None:
    seeds = []
    for raw in (website, *(extra_urls or ())):
        url = _norm_url(raw)
        if url:
            seeds.append(url)
    if not seeds and name:
        website = _places_website(name, address, deadline)
        url = _norm_url(website)
        if url:
            seeds.append(url)
    if not seeds:
        return None

    pages = []
    seen = set()
    for url in seeds:
        if time.monotonic() >= deadline:
            break
        page = _fetch(url, deadline)
        if not page:
            continue
        if page["url"] in seen:
            continue
        seen.add(page["url"])
        pages.append(page)

    candidates = list(seeds)
    for page in pages:
        for href, text in page["links"]:
            if _looks_like_menu_or_order(href, text):
                candidates.append(href)

    # Prefer first-party / order hosts, then /menu paths, then the seed page.
    ranked = _rank_urls(candidates)
    for url in ranked:
        if time.monotonic() >= deadline:
            break
        page = _fetch(url, deadline)
        if not page or _is_auth_wall(page):
            continue
        items = parse_menu_html(page["html"], page["url"])
        if items:
            return _result(items, page["url"])

    # Last resort: a public menu photo URL already on a page we fetched.
    for page in pages:
        if time.monotonic() >= deadline:
            break
        if _is_auth_wall(page):
            continue
        for img in page["images"]:
            if not _looks_like_menu_image(img):
                continue
            items = _items_from_public_image(img["url"], deadline)
            if items:
                return _result(items, img["url"], kind="social_photo")
    return None


def parse_menu_html(html: str, url: str = "") -> list | None:
    """Parse items from a fetched menu/order page. None if not confident."""
    if not html or _is_auth_wall({"url": url, "html": html}):
        return None
    items = []
    items.extend(_json_ld_items(html))
    if len(items) < _MIN_ITEMS:
        items.extend(_known_markup_items(html))
    if len(items) < _MIN_ITEMS:
        items.extend(_next_data_items(html))
    if len(items) < _MIN_ITEMS:
        items.extend(_text_line_items(_visible_text(html)))
    return _clean_items(items)


def parse_menu_text(text: str) -> list | None:
    """Parse OCR / plain-text menu lines. None if not confident."""
    return _clean_items(_text_line_items(text or ""))


def _places_website(name: str, address: str, deadline: float) -> str:
    remaining = deadline - time.monotonic()
    if remaining < 0.4:
        return ""
    try:
        from scanner.scanner import google_enrich
        info = google_enrich(name, address or "", timeout=min(4, remaining),
                             check_liveness=False) or {}
        return info.get("website") or ""
    except Exception:
        return ""


def _result(items, url: str, kind: str | None = None) -> dict:
    kind = kind or _source_kind(url)
    labels = {
        "order_page": "From their order page",
        "menu_page": "From their menu",
        "social_photo": "From a public menu photo",
    }
    return {
        "items": items[:_MAX_ITEMS],
        "source": kind,
        "source_url": url,
        "source_label": labels.get(kind, "From their menu"),
    }


def _source_kind(url: str) -> str:
    host = _hostname(url)
    if _host_is(host, SOCIAL_HOSTS) or _looks_like_image_url(url):
        return "social_photo"
    if _host_is(host, ORDER_HOSTS) and not _host_is(host, ("singleplatform.com", "gotoeat.net")):
        return "order_page"
    path = (urllib.parse.urlparse(url).path or "").lower()
    if any(h in path for h in _MENU_PATH_HINTS) or _host_is(host, ("singleplatform.com", "gotoeat.net")):
        return "menu_page"
    if _host_is(host, ORDER_HOSTS):
        return "order_page"
    return "menu_page"


def _rank_urls(urls) -> list:
    scored = []
    seen = set()
    for i, raw in enumerate(urls):
        url = _norm_url(raw)
        if not url or url in seen:
            continue
        seen.add(url)
        host = _hostname(url)
        path = (urllib.parse.urlparse(url).path or "").lower()
        score = 0
        if _host_is(host, ("toasttab.com", "toast.com", "square.site",
                           "squareup.com", "square.online", "chownow.com",
                           "thanx.com")):
            score = 100
        elif _host_is(host, ORDER_HOSTS):
            score = 80
        elif any(h in path for h in _MENU_PATH_HINTS):
            score = 60
        elif _host_is(host, SOCIAL_HOSTS):
            score = 10
        else:
            score = 30
        if any(h in path for h in _MENU_PATH_HINTS):
            score += 15
        scored.append((-score, i, url))
    return [u for _, _, u in sorted(scored)]


def _looks_like_menu_or_order(href: str, text: str) -> bool:
    host = _hostname(href)
    path = (urllib.parse.urlparse(href).path or "").lower()
    if _host_is(host, ORDER_HOSTS):
        return True
    if any(h in path for h in _MENU_PATH_HINTS):
        return True
    if _MENU_LINK_WORDS.search(text or "") and href.startswith("http"):
        return True
    return False


def _looks_like_menu_image(img: dict) -> bool:
    blob = " ".join((img.get("url") or "", img.get("alt") or "")).lower()
    return "menu" in blob or "carte" in blob


def _looks_like_image_url(url: str) -> bool:
    path = (urllib.parse.urlparse(url).path or "").lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


# ------------------------------------------------------------------ fetch
def _fetch(url: str, deadline: float) -> dict | None:
    remaining = deadline - time.monotonic()
    if remaining < 0.25 or not url:
        return None
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,image/*,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=min(4.5, remaining)) as r:
            raw = r.read(_MAX_BYTES)
            final = r.geturl() or url
            ctype = (r.headers.get("Content-Type") or "").lower()
            if r.status in _BLOCKED:
                return None
            text = raw.decode("utf-8", "replace") if not ctype.startswith("image/") else ""
            parsed = _parse_page(text, final) if text else {"links": [], "images": []}
            return {"url": final, "html": text, "ctype": ctype, **parsed}
    except urllib.error.HTTPError as e:
        if e.code in _BLOCKED:
            return None
        return None
    except Exception:
        return None


def _is_auth_wall(page: dict) -> bool:
    url = (page.get("url") or "").lower()
    head = (page.get("html") or "")[:4000].lower()
    if "accounts/login" in url or "/login" in url and "instagram" in url:
        return True
    if "log in to instagram" in head or "login to facebook" in head:
        return True
    if "facebook.com/login" in url:
        return True
    return False


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.images = []
        self._in_a = False
        self._href = ""
        self._a_text = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        if tag == "a":
            self._in_a = True
            self._href = attrs.get("href") or ""
            self._a_text = []
        if tag == "img":
            src = attrs.get("src") or attrs.get("data-src") or ""
            alt = attrs.get("alt") or ""
            if src:
                self.images.append({"url": src, "alt": alt})

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        if tag == "a" and self._in_a:
            self.links.append((self._href, "".join(self._a_text)))
            self._in_a = False

    def handle_data(self, data):
        if self._in_a and not self._skip:
            self._a_text.append(data)


def _parse_page(html: str, base: str) -> dict:
    p = _PageParser()
    try:
        p.feed(html)
    except Exception:
        pass
    links = []
    for href, text in p.links:
        abs_url = _abs_url(base, href)
        if abs_url:
            links.append((abs_url, (text or "").strip()))
    images = []
    for img in p.images:
        abs_url = _abs_url(base, img["url"])
        if abs_url:
            images.append({"url": abs_url, "alt": img.get("alt") or ""})
    # og:image often carries a public photo when the page itself is thin.
    for m in re.finditer(
            r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.I):
        abs_url = _abs_url(base, htmlmod.unescape(m.group(1)))
        if abs_url:
            images.append({"url": abs_url, "alt": "og:image"})
    return {"links": links, "images": images}


# ------------------------------------------------------------------ parsers
def _json_ld_items(html: str) -> list:
    out = []
    for m in re.finditer(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.I | re.S):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        out.extend(_walk_ld(data))
    return out


def _walk_ld(node) -> list:
    out = []
    if isinstance(node, list):
        for child in node:
            out.extend(_walk_ld(child))
        return out
    if not isinstance(node, dict):
        return out
    types = node.get("@type") or node.get("type") or ""
    if isinstance(types, list):
        types = " ".join(str(t) for t in types)
    types = str(types)
    if "MenuItem" in types:
        item = _ld_item(node)
        if item:
            out.append(item)
    for key in ("hasMenuItem", "hasMenuSection", "hasMenu", "itemListElement",
                "menu", "menuAddOn", "acceptedOffer", "offers"):
        if key in node:
            out.extend(_walk_ld(node[key]))
    if "@graph" in node:
        out.extend(_walk_ld(node["@graph"]))
    return out


def _ld_item(node: dict):
    title = _plain(node.get("name") or node.get("title") or "")
    desc = _plain(node.get("description") or "")
    price = _price_from(node.get("offers") or node.get("price") or "")
    if not title:
        return None
    return (title, desc, price)


def _known_markup_items(html: str) -> list:
    """Known, boring class pairs used by SinglePlatform, gotoeat, etc."""
    pairs = (
        (r'<h4 class="item-title">(.*?)</h4>(?:.*?<span class="price">(.*?)</span>)?', re.S | re.I),
        (r'<div class="menu-item-desc">(.*?)</div>.*?class="menu-item-price">(.*?)</div>', re.S | re.I),
        (r'<div class="promotion-desc">(.*?)</div>.*?class="promotion-discount">(.*?)</(?:div|span)>', re.S | re.I),
        (r'<div class="product-title">(.*?)</div>.*?class="product-price">(.*?)</div>', re.S | re.I),
    )
    out = []
    for pat, flags in pairs:
        for m in re.finditer(pat, html, flags):
            title = _plain(m.group(1))
            price = _price_from(m.group(2) if m.lastindex >= 2 else "")
            if title:
                # Description sits in a following <p> on gotoeat.
                desc = ""
                tail = html[m.end():m.end() + 240]
                pm = re.search(r"<p>(.*?)</p>", tail, re.S | re.I)
                if pm:
                    desc = _plain(pm.group(1))
                out.append((title, desc, price))
    return out


def _next_data_items(html: str) -> list:
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                  html, re.I | re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out = []
    _walk_json_items(data, out)
    return out


def _walk_json_items(node, out: list, depth: int = 0):
    if depth > 12 or len(out) >= 40:
        return
    if isinstance(node, list):
        for child in node:
            _walk_json_items(child, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    title = node.get("name") or node.get("itemName") or node.get("title")
    price = (node.get("price") or node.get("amount")
             or (node.get("priceMoney") or {}).get("amount")
             or node.get("unitPrice"))
    desc = node.get("description") or node.get("desc") or ""
    if title and price not in (None, ""):
        parsed = _price_from(price)
        # Toast/Square sometimes store cents as an integer (750 → $7.50).
        if parsed is None and isinstance(price, (int, float)) and 100 <= price <= 20000:
            parsed = round(float(price) / 100.0, 2)
        title_s = _plain(str(title))
        if title_s and parsed is not None:
            out.append((title_s, _plain(str(desc)), parsed))
    for v in node.values():
        if isinstance(v, (dict, list)):
            _walk_json_items(v, out, depth + 1)


def _text_line_items(text: str) -> list:
    out = []
    for raw in (text or "").splitlines():
        line = _plain(raw)
        if not line:
            continue
        m = _ITEM_LINE_RE.match(line)
        if not m:
            continue
        title, price_s = m.group(1).strip(), m.group(2)
        if _skip_title(title):
            continue
        out.append((title, "", _price_from("$" + price_s)))
    return out


def _visible_text(html: str) -> str:
    stripped = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    stripped = re.sub(r"<style\b[^>]*>.*?</style>", " ", stripped, flags=re.I | re.S)
    stripped = re.sub(r"<br\s*/?>", "\n", stripped, flags=re.I)
    stripped = re.sub(r"</(?:p|div|li|h1|h2|h3|h4|tr)>", "\n", stripped, flags=re.I)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return htmlmod.unescape(stripped)


def _items_from_public_image(url: str, deadline: float) -> list | None:
    """Best-effort OCR. Skip if the image is blocked or we have no OCR."""
    remaining = deadline - time.monotonic()
    if remaining < 0.4:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "image/*,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=min(4.0, remaining)) as r:
            if r.status in _BLOCKED:
                return None
            ctype = (r.headers.get("Content-Type") or "").lower()
            data = r.read(2_000_000)
    except urllib.error.HTTPError as e:
        if e.code in _BLOCKED:
            return None
        return None
    except Exception:
        return None
    if "html" in ctype or data[:15].lstrip().startswith(b"<!DOCTYPE") or data[:6].lstrip().startswith(b"<html"):
        return None
    text = _ocr_bytes(data, ctype)
    if not text:
        return None
    return parse_menu_text(text)


def _ocr_bytes(data: bytes, ctype: str) -> str:
    """Optional OCR. Missing tesseract / PIL → empty (fail closed)."""
    if not data:
        return ""
    # Some "menu photos" are actually a one-page PDF.
    if data[:5] == b"%PDF-" or "pdf" in (ctype or ""):
        try:
            return data.decode("latin-1", "replace")
        except Exception:
            return ""
    try:
        from PIL import Image
        import io
        import pytesseract
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""


# ------------------------------------------------------------------ cleanup
def _clean_items(rows) -> list | None:
    seen = set()
    out = []
    for row in rows or []:
        if not row:
            continue
        title = _plain(row[0])
        desc = _plain(row[1] if len(row) > 1 else "")
        price = _price_from(row[2] if len(row) > 2 else None)
        if not title or _skip_title(title):
            continue
        if len(title) < 3 or len(title) > 60:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((title, desc, price))
        if len(out) >= 20:
            break
    if len(out) < _MIN_ITEMS:
        return None
    return out


def _skip_title(title: str) -> bool:
    return (title or "").strip().lower() in _SKIP_TITLES


def _plain(value) -> str:
    if value is None:
        return ""
    text = htmlmod.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _price_from(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return _price_from(value.get("price") or value.get("lowPrice")
                           or value.get("highPrice") or value.get("amount"))
    if isinstance(value, (int, float)):
        n = float(value)
        if 0.5 <= n <= 200:
            return n if n != int(n) else float(int(n))
        return None
    text = str(value)
    m = _PRICE_RE.search(text) or _BARE_PRICE_RE.search(text.strip())
    if not m:
        try:
            n = float(text)
        except ValueError:
            return None
        return n if 0.5 <= n <= 200 else None
    n = float(m.group(1))
    return n if 0.5 <= n <= 200 else None


def _norm_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw or raw.startswith("#") or raw.lower().startswith("javascript:"):
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed.geturl()


def _abs_url(base: str, href: str) -> str:
    href = (href or "").strip()
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return ""
    try:
        return _norm_url(urllib.parse.urljoin(base, href))
    except Exception:
        return ""


def _hostname(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _host_is(host: str, needles) -> bool:
    for needle in needles:
        n = needle.lower().lstrip(".")
        if host == n or host.endswith("." + n):
            return True
    return False
