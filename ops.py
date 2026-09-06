"""Ops dashboard payload — live Turso counts, no paste-to-Claude loop.

Today's focus, weekday rotation, and Houston/Miami/Austin waves are
derived from the calendar + ops_meta overrides. Pipeline rows come
straight from the leads table.
"""

from __future__ import annotations

from datetime import date, datetime

import claim
import config as C
import db
from config import DEMO_BASE_URL, FROM_EMAIL, RESEND_API_KEY

LEAD_STATUSES = ("new", "site_generated", "proposed", "replied", "claimed", "sold", "dead")

STATUS_LABEL = {
    "new": "Lead",
    "site_generated": "Demo",
    "proposed": "Emailed",
    "replied": "Replied",
    "claimed": "Claimed",
    "sold": "Sold",
    "dead": "Dead",
}


def _city_label(key: str) -> str:
    meta = C.CITIES.get(key) or {}
    if meta:
        return f"{meta['name']}"
    return (key or "").replace("-", " ").title()


def _cat_label(key: str) -> str:
    for k, label in C.OPS_WEEKLY_ROTATION:
        if k == key:
            return label
    meta = C.BUSINESS_CATEGORIES.get(key) or {}
    return (meta.get("label") or key or "business").title()


def _weekday_index(today: date | None = None) -> int:
    d = today or date.today()
    return min(d.weekday(), 4)  # Sat/Sun → Friday


def _default_wave(today: date | None = None) -> str:
    waves = list(C.DEFAULT_CITIES)
    if not waves:
        return "houston"
    d = today or date.today()
    return waves[(d.isocalendar()[1] - 1) % len(waves)]


def _focus_blurb(category: str, city: str, stats: dict, qc: dict) -> str:
    label = _cat_label(category).lower()
    city_l = _city_label(city)
    return (
        f"Warm-up: no-website {label} in {city_l}. "
        f"{qc.get('new', 0)} new leads, {qc.get('need_site', 0)} waiting on a demo, "
        f"{qc.get('need_send', 0)} ready to email, "
        f"{stats.get('claimed', 0)} claimed, {stats.get('sold', 0)} sold."
    )


def _queue_counts(c) -> dict:
    return {
        "new": c.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0],
        "need_site": c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='new' "
            "AND (demo_token IS NULL OR demo_token='')"
        ).fetchone()[0],
        "need_send": c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='site_generated' AND emailed=0"
        ).fetchone()[0],
        "need_claim": c.execute(
            "SELECT COUNT(*) FROM leads WHERE emailed=1 AND COALESCE(claimed,0)=0 "
            "AND status NOT IN ('sold','dead','claimed')"
        ).fetchone()[0],
    }


def _sending() -> dict:
    from_email = (FROM_EMAIL or "").strip()
    sending_ok = bool(RESEND_API_KEY) and not from_email.endswith("@resend.dev")
    return {
        "ok": sending_ok,
        "from": from_email or "(unset)",
        "why": "" if sending_ok else (
            "Outreach email is OFF. FROM_EMAIL is still Resend's test address, which can only "
            "deliver to the Resend account owner — not to business owners. Verify a sending "
            "domain in Resend, then set FROM_EMAIL and RESEND_API_KEY."
        ),
    }


def ops_payload(today: date | None = None) -> dict:
    """Everything /ops needs in one call. Reads the live DB; no cache."""
    day = today or date.today()
    waves = list(C.DEFAULT_CITIES)
    rotation = list(C.OPS_WEEKLY_ROTATION)
    wd = _weekday_index(day)
    focus_cat, focus_cat_label = rotation[wd] if rotation else ("restaurant", "Restaurants")

    saved_wave = (db.get_meta("active_wave") or "").strip().lower()
    focus_city = saved_wave if saved_wave in waves else _default_wave(day)
    notes = db.get_meta("overall_notes")
    stats = db.get_stats()

    with db.conn() as c:
        qc = _queue_counts(c)
        lead_rows = c.execute(
            "SELECT leads.*, businesses.review_count AS review_count, "
            "businesses.website AS biz_website "
            "FROM leads LEFT JOIN businesses ON businesses.id = leads.business_id "
            "ORDER BY leads.id DESC LIMIT 200"
        ).fetchall()
        research_missing = [dict(r) for r in c.execute(
            "SELECT id, name, city, phone, category FROM leads "
            "WHERE (email IS NULL OR email = '') AND status NOT IN ('dead','sold') "
            "ORDER BY id DESC LIMIT 50"
        ).fetchall()]
        log_rows = [dict(r) for r in c.execute(
            "SELECT created_at, to_email, subject, status FROM email_log "
            "ORDER BY id DESC LIMIT 40"
        ).fetchall()]

    leads = []
    for r in lead_rows:
        l = dict(r)
        token = l.get("demo_token")
        l["demo_url"] = f"{DEMO_BASE_URL}/demo/{token}" if token else None
        l["claim_url"] = claim.start_url(token, l.get("care_plan") or "none") if token else None
        l["status_label"] = STATUS_LABEL.get(l.get("status") or "new", l.get("status"))
        l["review_count"] = l.get("review_count") or 0
        l.pop("business_id", None)
        leads.append(l)

    entries = []
    for x in log_rows:
        entries.append({
            "when": (x.get("created_at") or "")[:16],
            "what": f"email {x.get('status') or ''} → {x.get('to_email') or ''} · {x.get('subject') or ''}",
        })
    for l in leads:
        if l.get("notes"):
            for line in str(l["notes"]).splitlines():
                entries.append({
                    "when": line[1:17] if line.startswith("[") else "",
                    "what": f"{l['name']}: {line[19:] if line.startswith('[') else line}",
                })
    entries.sort(key=lambda e: e["when"], reverse=True)

    by_cat = stats.get("by_category") or {}
    industries = []
    for i, (key, label) in enumerate(rotation):
        n = by_cat.get(key, 0)
        industries.append({
            "category": key,
            "label": label,
            "count": n,
            "next": i == wd,
            "status": "Not started — build template on first day" if n == 0
                      else f"{n} leads in pipeline",
        })

    funnel = stats.get("funnel") or {}
    return {
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
        "sending": _sending(),
        "today": {
            "weekday": day.strftime("%A"),
            "date": day.isoformat(),
            "city": focus_city,
            "city_label": _city_label(focus_city),
            "category": focus_cat,
            "category_label": focus_cat_label,
            "blurb": _focus_blurb(focus_cat, focus_city, stats, qc),
            "weekend": day.weekday() >= 5,
        },
        "rhythm": [
            {
                "n": 1,
                "title": "Scan & qualify",
                "mins": 15,
                "detail": f"Find no-website {_cat_label(focus_cat).lower()} in {_city_label(focus_city)}.",
                "count": qc["new"],
                "hint": f"{qc['new']} new",
            },
            {
                "n": 2,
                "title": "Build demos",
                "mins": 15,
                "detail": "Generate a preview site for each qualified lead.",
                "count": qc["need_site"],
                "hint": f"{qc['need_site']} waiting",
            },
            {
                "n": 3,
                "title": "Email & claim",
                "mins": 15,
                "detail": "Send the demo, then start the $99 claim (Care optional).",
                "count": qc["need_send"] + qc["need_claim"],
                "hint": f"{qc['need_send']} to send · {qc['need_claim']} to claim",
            },
        ],
        "rotation": [
            {
                "day": ("Mon", "Tue", "Wed", "Thu", "Fri")[i],
                "category": key,
                "label": label,
                "today": i == wd,
                "count": by_cat.get(key, 0),
            }
            for i, (key, label) in enumerate(rotation)
        ],
        "waves": [
            {
                "city": key,
                "label": _city_label(key),
                "active": key == focus_city,
                "count": (stats.get("by_city") or {}).get(key, 0),
            }
            for key in waves
        ],
        "funnel": funnel,
        "stats": stats,
        "queue_counts": qc,
        "website_status": stats.get("by_website_status") or {},
        "leads": leads,
        "research": {"industries": industries, "need_email": research_missing},
        "log": entries[:60],
        "notes": notes,
        "claim": {
            "configured": claim.stripe_configured(),
            "stub": not claim.stripe_configured(),
            "pricing": claim.pricing(),
        },
        "statuses": list(LEAD_STATUSES),
    }
