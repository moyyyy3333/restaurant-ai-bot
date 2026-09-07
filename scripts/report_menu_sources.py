#!/usr/bin/env python3
"""Classify built demo menus as REAL vs SAMPLE vs unknown.

Reads demo tokens from Turso/local SQLite when credentials are present.
Otherwise uses the public known-token seed (GitHub Actions pipeline logs
and Growth PR demo URLs) and fetches live /demo/<token> HTML.

Does not send outreach. Does not invent menu items.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_BASE = "https://restaurant-ai-bot-two.vercel.app"
STATS_URLS = (
    "https://restaurant-ai-bot-two.vercel.app/stats",
    "https://restaurant-ai-bot-n844.onrender.com/stats",
)

# Non-sample sources written by generator.py / menu_enrich.py.
REAL_SOURCES = frozenset({
    "menu_page", "order_page", "social_photo", "yelp",
})
SAMPLE_SOURCES = frozenset({"sample"})

# Public tokens from Daily lead pipeline run logs + Growth PR bodies.
# Not a Turso dump — production /stats reports more demos than this seed.
KNOWN_TOKENS: list[dict] = [
    {"name": "L'Oca d'Oro", "token": "2mzDCfq8THG7"},
    {"name": "Colleen's Kitchen", "token": "nGLcnkGCjNKk"},
    {"name": "Bao'd Up", "token": "VvIhVSZHkCg9"},
    {"name": "Nando's", "token": "JkZc_BgGsS8S"},
    {"name": "Blue Lacy", "token": "u2jjsqsA7leB"},
    {"name": "Chuy's", "token": "hgzM_wbTIjKl"},
    {"name": "Marufuku Ramen", "token": "RPkEJDhkQM2h"},
    {"name": "Dish Society", "token": "iDTCVws6hR6R"},
    {"name": "Veracruz Fonda and Bar", "token": "S__Q_1RqQj0f"},
    {"name": "Kerbey Lane Café", "token": "awQfMiVIg5at"},
    {"name": "Conscious Cravings", "token": "uQTrDmllpefG"},
    {"name": "Eggman", "token": "1sYi46Z2z84D"},
    {"name": "Veracruz All Natural", "token": "T3-070410vPK"},
    {"name": "Xian Sushi and Noodle - Mueller", "token": "d-SDqIrxr49O"},
    {"name": "The Stone House", "token": "k7MG6MShdJPl"},
    {"name": "Texas Mesquite Grill", "token": "_4ur89DO-Ptd"},
    {"name": "E Star Chinese Buffet", "token": "3dmomuSTkstD"},
    {"name": "Yale Street Grill", "token": "wa2LGwK--aBb"},
    {"name": "Rustika Cafe & Bakery", "token": "sL7EkRvIUOdl"},
    {"name": "Bonjour Cafe", "token": "7qdviCOL8_nD"},
    {"name": "La Pupusa Loca", "token": "ebJU-rKQa3Hd"},
    {"name": "Tai Kee", "token": "rvR3yxAhb2wW"},
    {"name": "Korea House", "token": "F1vDQauRYi-3"},
    {"name": "Pho I-10", "token": "QriQmIUtMOiC"},
    {"name": "Cliff's Grill", "token": "Qk1NdQZI-j32"},
    {"name": "Go Fish", "token": "1CEYJhz53TeH"},
    {"name": "Texas Medical Center Commons", "token": "zLUSQZWrXGW2"},
    {"name": "Half Moon Empanadas", "token": "U5UbrUYNbnuP"},
    {"name": "Orno Miami", "token": "5B1qhYeXKYRq"},
    {"name": "Focaccia Bistro", "token": "DprFGmpmjPz8"},
    {"name": "Teapresso Bar", "token": "TAtKLRfrMwXz"},
    {"name": "Almost Famous", "token": "DofacFrFhz54"},
    {"name": "Antidote Coffee", "token": "yk04K6KX68CV"},
    {"name": "Simply Coffie", "token": "4EDfTorGlcKr"},
    {"name": "Rustica Hondureña", "token": "QzTEkSRkFTpI"},
    {"name": "Petit Rouge", "token": "wl8ksbgZcabh"},
    {"name": "ARCH Café", "token": "x7Y2bFAAgmfk"},
    {"name": "Cure Cafe", "token": "WYER5Kr_hL-K"},
    {"name": "Cafe Galleria", "token": "A8bYXTkKE1Ot"},
    {"name": "American and Cuban coffee", "token": "sJ-mP2KnDIBn"},
    {"name": "GVA BOX", "token": "ZoCmFLuIFi9Z"},
    {"name": "Juan Valdez Café", "token": "GY4GRz7utQ3i"},
    {"name": "Clos Bistro & Cafe", "token": "LwyD63hWc2Au"},
    {"name": "Mister Block Cafe", "token": "Gor72nWJNPKk"},
    {"name": "Bianchini Mercato", "token": "O--RAyQIbY5y"},
    {"name": "Miami Under Ground", "token": "aEGN6bcLJZMl"},
    {"name": "Wynwood Cafe", "token": "ZJaV1FTYOBdo"},
    {"name": "Think Tacos", "token": "ZoUXNca36__H"},
    {"name": "Thien An Sandwiches", "token": "EBMKiuowROVS"},
    {"name": "Sharetea", "token": "MTg_A-cZltwo"},
    {"name": "B&B Joint", "token": "6haIdu9tl9Pz"},
    {"name": "La Gazzetta", "token": "o_iG-fMMQeoY"},
    {"name": "La Moon", "token": "RTf2CbcCm4eA"},
    {"name": "Conscious Cravings", "token": "-ikz1E_rxPgp"},
    {"name": "The Stone House", "token": "lXn9dLkZq87B"},
    {"name": "Double Trouble", "token": "b9vB_nN-m5gt"},
    {"name": "Apothecary Cafe & Wine Bar", "token": "01Gs2yIATAWL"},
    {"name": "Koko Cafe", "token": "_NZTxd94xBOK"},
    {"name": "Black Hole Coffee House", "token": "5i9Qrv3PLlkD"},
    {"name": "GW Gyro & Wings", "token": "lrwlM-PqbgwT"},
    {"name": "Chopsticks Express", "token": "zXADMT_yLjvi"},
    {"name": "Teriyaki Kitchen", "token": "U8j7s0qOvMQU"},
    {"name": "Uncle Bean's Coffee", "token": "IgWKVOofG3MJ"},
    {"name": "Roland's Soul Food", "token": "NfWOw2F4zl2P"},
    {"name": "Sam's BBQ", "token": "f_5hF9MciXcR"},
    {"name": "Galloway's Sandwich Shop", "token": "byJ6FILpk4gW"},
    {"name": "The Original New Orleans Po-Boy and Gumbo Shop", "token": "ZNsitniK_uT3"},
    {"name": "Thai Thani", "token": "rMWq8aJ_9VnR"},
    {"name": "Elaine's Pork and Pie", "token": "3L8UGdBjVc5i"},
    {"name": "Katz's", "token": "Urn-76MPxlyS"},
    {"name": "Pavón Coffee Den", "token": "3DLzbKSCJjo4"},
    {"name": "CoCo Fresh Tea & Juice", "token": "X2j-uxuIRJs2"},
    {"name": "Harold's", "token": "6uHzUctF7gAz"},
    {"name": "Dish Society", "token": "rLb8FCOkUS6M"},
    {"name": "Zapvor by Thai Spice", "token": "1oUxyV9qBoYB"},
    {"name": "Jenni's Noodle House", "token": "-zIJ-V-XOPvJ"},
    {"name": "Vietnam Restaurant", "token": "sui5P3BEhGQA"},
    {"name": "1891 American Eatery and Bar", "token": "pZsrB8GI79A0"},
    {"name": "Via313 Pizzeria", "token": "XXswWW1VRlIB"},
    {"name": "Revolucion Coffee + Juice", "token": "1g3-F7WHHY8k"},
    {"name": "Wild", "token": "8MwFoJpVXhCo"},
    {"name": "Melange Creperie", "token": "M0KmfMqIbrEl"},
    {"name": "Simply Phở", "token": "NlRkan5Pusto"},
    {"name": "Tout Suite", "token": "aKkUSX43uFkN"},
    {"name": "Frenchies Dinner", "token": "bIO9ncQPL6S5"},
    {"name": "Cream Parlor", "token": "QDfZzeoBRE9n"},
]

_TAG_RE = re.compile(r"<[^>]+>")
_MENU_SRC_RE = re.compile(r'data-menu-source="([^"]*)"')
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_CAT_RE = re.compile(r'data-category="([^"]*)"')
_H3_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.I | re.S)
_MENU_SEC_RE = re.compile(r'<section[^>]*id="menu"[^>]*>(.*?)</section>', re.I | re.S)
_NOTE_RE = re.compile(
    r'<(?:p)[^>]*class="[^"]*(?:menu-source|sub)[^"]*"[^>]*>(.*?)</p>',
    re.I | re.S,
)


def _strip(text: str) -> str:
    text = html_lib.unescape(_TAG_RE.sub("", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def classify_source(raw: str | None) -> str:
    """Return REAL, SAMPLE, or UNKNOWN for a data-menu-source value."""
    src = (raw or "").strip().lower()
    if src in SAMPLE_SOURCES:
        return "SAMPLE"
    if not src:
        return "UNKNOWN"
    if src in REAL_SOURCES:
        return "REAL"
    # Any other explicit source (future enrich kinds) is treated as real.
    return "REAL"


def parse_demo_html(html: str, fallback_name: str = "") -> dict:
    """Pull name, city, category, menu source, and a short title sniff."""
    src_m = _MENU_SRC_RE.search(html or "")
    source = src_m.group(1).strip() if src_m else ""
    title = _strip(_TITLE_RE.search(html or "").group(1)) if _TITLE_RE.search(html or "") else ""
    name, city = fallback_name, ""
    if " · " in title:
        name, city = [p.strip() for p in title.split(" · ", 1)]
    elif title:
        name = title
    cat_m = _CAT_RE.search(html or "")
    category = (cat_m.group(1).strip() if cat_m else "") or ""
    section = _MENU_SEC_RE.search(html or "")
    block = section.group(1) if section else (html or "")
    sniff = ", ".join(_strip(m.group(1)) for m in list(_H3_RE.finditer(block))[:4] if _strip(m.group(1)))
    note = ""
    for m in _NOTE_RE.finditer(block):
        cand = _strip(m.group(1))
        if cand:
            note = cand
            break
    return {
        "name": name or fallback_name,
        "city": city,
        "category": category,
        "data_menu_source": source,
        "menu_class": classify_source(source),
        "sniff": sniff,
        "caption": note,
    }


def demo_url(base: str, token: str) -> str:
    return f"{base.rstrip('/')}/demo/{token}"


def _http_get(url: str, timeout: float) -> tuple[int, str]:
    req = Request(url, headers={"User-Agent": "menu-source-report/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, raw.decode("utf-8", "replace")
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        return exc.code, body
    except (URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def fetch_stats() -> dict:
    for url in STATS_URLS:
        code, body = _http_get(url, timeout=15)
        if code == 200:
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                continue
    return {}


def load_from_db() -> list[dict]:
    """Return demo rows from Turso/local SQLite, or [] if unused/unconfigured."""
    try:
        import db
    except Exception:
        return []
    if not (os.getenv("TURSO_DATABASE_URL") or os.getenv("LOCAL_DB_PATH")):
        # Default local file is empty in this environment; skip unless set.
        if not db.turso_configured():
            return []
    try:
        db.ensure_schema()
        with db.conn() as c:
            rows = c.execute(
                """
                SELECT demo_sites.token AS token,
                       demo_sites.html AS html,
                       leads.name AS name,
                       leads.city AS city,
                       leads.category AS category
                FROM demo_sites
                LEFT JOIN leads ON leads.demo_token = demo_sites.token
                WHERE demo_sites.token IS NOT NULL AND demo_sites.token != ''
                ORDER BY leads.name COLLATE NOCASE
                """
            ).fetchall()
    except Exception as exc:
        print(f"db read failed: {exc}", file=sys.stderr)
        return []
    out = []
    for r in rows:
        rec = {
            "name": r["name"] or "",
            "city": r["city"] or "",
            "category": r["category"] or "",
            "token": r["token"],
            "html": r["html"] or "",
            "origin": "db",
        }
        out.append(rec)
    return out


def merge_inventory(db_rows: list[dict], seed: list[dict]) -> list[dict]:
    by_token: dict[str, dict] = {}
    for row in seed:
        tok = (row.get("token") or "").strip()
        if not tok:
            continue
        by_token[tok] = {
            "name": row.get("name") or "",
            "city": row.get("city") or "",
            "category": row.get("category") or "",
            "token": tok,
            "html": "",
            "origin": "seed",
        }
    for row in db_rows:
        tok = row["token"]
        prev = by_token.get(tok, {})
        by_token[tok] = {
            "name": row.get("name") or prev.get("name") or "",
            "city": row.get("city") or prev.get("city") or "",
            "category": row.get("category") or prev.get("category") or "",
            "token": tok,
            "html": row.get("html") or "",
            "origin": "db",
        }
    return sorted(by_token.values(), key=lambda r: (r["name"] or "").lower())


def classify_row(row: dict, base: str, fetch_live: bool, timeout: float) -> dict:
    parsed = {
        "name": row.get("name") or "",
        "city": row.get("city") or "",
        "category": row.get("category") or "",
        "data_menu_source": "",
        "menu_class": "UNKNOWN",
        "sniff": "",
        "caption": "",
    }
    html = row.get("html") or ""
    status = "stored" if html else ""
    if html:
        parsed = parse_demo_html(html, fallback_name=parsed["name"])
        if row.get("city") and not parsed["city"]:
            parsed["city"] = row["city"]
        if row.get("category") and not parsed["category"]:
            parsed["category"] = row["category"]
    elif fetch_live:
        url = demo_url(base, row["token"])
        code, body = _http_get(url, timeout=timeout)
        status = str(code or "error")
        if code == 200 and body:
            parsed = parse_demo_html(body, fallback_name=parsed["name"])
        elif code == 404:
            parsed["menu_class"] = "UNKNOWN"
            parsed["caption"] = "demo missing (404)"
        else:
            parsed["menu_class"] = "UNKNOWN"
            parsed["caption"] = f"fetch failed ({status})"
    else:
        parsed["caption"] = "no stored HTML; live fetch skipped"
    url = demo_url(base, row["token"])
    return {
        "name": parsed["name"] or row.get("name") or "",
        "city": parsed["city"] or row.get("city") or "",
        "category": parsed["category"] or row.get("category") or "",
        "token": row["token"],
        "demo_url": url,
        "data_menu_source": parsed["data_menu_source"],
        "menu_class": parsed["menu_class"],
        "sniff": parsed["sniff"],
        "notes": _notes(parsed, status, row.get("origin") or ""),
    }


def _notes(parsed: dict, status: str, origin: str) -> str:
    bits = []
    if parsed.get("data_menu_source"):
        bits.append(f"data-menu-source={parsed['data_menu_source']}")
    if parsed.get("sniff"):
        bits.append(parsed["sniff"])
    if parsed.get("caption") and parsed["caption"] not in (parsed.get("sniff") or ""):
        bits.append(parsed["caption"])
    if status and status not in {"stored", "200"}:
        bits.append(f"http {status}")
    if origin == "seed":
        bits.append("known token (pipeline/PR)")
    elif origin == "db":
        bits.append("from Turso/local db")
    return " — ".join(bits)


def _md_cell(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", " ")


def render_markdown(rows: list[dict], stats: dict, method: str, generated_at: str) -> str:
    real = sum(1 for r in rows if r["menu_class"] == "REAL")
    sample = sum(1 for r in rows if r["menu_class"] == "SAMPLE")
    unknown = sum(1 for r in rows if r["menu_class"] == "UNKNOWN")
    funnel_demos = (stats.get("funnel") or {}).get("demos")
    sites = stats.get("sites")
    lines = [
        "# Demo menu sources",
        "",
        f"Snapshot generated **{generated_at}**.",
        "",
        "## Method",
        "",
        method,
        "",
        "Classification:",
        "",
        "- **REAL** — `data-menu-source` is `menu_page`, `order_page`, `social_photo`, `yelp`, or another non-sample source.",
        "- **SAMPLE** — `data-menu-source=sample` (labeled sample prices).",
        "- **UNKNOWN** — missing attribute, 404, or fetch/parse failure. Menus are not invented.",
        "",
        "## Production census",
        "",
        f"- Public `/stats` sites (demo_sites rows): **{sites if sites is not None else 'n/a'}**",
        f"- Public `/stats` funnel.demos (leads with a token): **{funnel_demos if funnel_demos is not None else 'n/a'}**",
        f"- Rows classified in this snapshot: **{len(rows)}**",
        "",
        "## Totals (this snapshot)",
        "",
        f"- **{real} real**",
        f"- **{sample} sample**",
        f"- **{unknown} unknown/missing**",
        "",
        "## Demos",
        "",
        "| name | city | category | demo_url | menu_source | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            "| {name} | {city} | {category} | {url} | {src} | {notes} |".format(
                name=_md_cell(r["name"]),
                city=_md_cell(r["city"]),
                category=_md_cell(r["category"]),
                url=r["demo_url"],
                src=_md_cell(r["menu_class"]),
                notes=_md_cell(r["notes"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("DEMO_BASE_URL") or DEFAULT_BASE)
    parser.add_argument("--out", default=str(ROOT / "docs" / "menu_sources.md"))
    parser.add_argument(
        "--fetch-live",
        action="store_true",
        help="GET each /demo/<token> when stored HTML is missing",
    )
    parser.add_argument("--no-fetch-live", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)

    db_rows = load_from_db()
    inventory = merge_inventory(db_rows, KNOWN_TOKENS)
    fetch_live = bool(args.fetch_live) or (not db_rows and not args.no_fetch_live)
    stats = fetch_stats()

    classified: list[dict] = []
    if fetch_live:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = {
                pool.submit(classify_row, row, args.base_url, True, args.timeout): row
                for row in inventory
            }
            for fut in as_completed(futs):
                classified.append(fut.result())
    else:
        for row in inventory:
            classified.append(classify_row(row, args.base_url, False, args.timeout))
    classified.sort(key=lambda r: (r["name"] or "").lower())

    method = (
        "Turso/local `demo_sites` + `leads` (stored HTML parsed; no live GET)."
        if db_rows and not fetch_live else
        "Turso/local rows plus live GET for pages without stored HTML."
        if db_rows else
        "No Turso/local secrets in this environment. Tokens come from public "
        "GitHub Actions Daily lead pipeline logs and Growth PR demo URLs, "
        "then each live `https://restaurant-ai-bot-two.vercel.app/demo/<token>` "
        "was fetched and parsed for `data-menu-source`."
    )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    markdown = render_markdown(classified, stats, method, stamp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(classified, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    real = sum(1 for r in classified if r["menu_class"] == "REAL")
    sample = sum(1 for r in classified if r["menu_class"] == "SAMPLE")
    unknown = sum(1 for r in classified if r["menu_class"] == "UNKNOWN")
    print(f"wrote {out_path}")
    print(f"classified {len(classified)}: {real} real, {sample} sample, {unknown} unknown")
    if stats:
        print(f"production /stats: sites={stats.get('sites')} funnel.demos={(stats.get('funnel') or {}).get('demos')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
