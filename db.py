"""
Turso (hosted libSQL) layer. Three tables: businesses (what we found), leads
(what we're working), demo_sites (what we built). Plus a suppression list so
an opt-out is permanent.

All read helpers return a Row, so callers can use row["column"] like sqlite3.Row.
Turso's client returns plain tuples with no named params, so this wraps it to
keep the rest of the codebase (bot.py, server.py, ...) untouched.
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone

import libsql_experimental as libsql

from config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

# Empty libsql URL is a new in-memory DB per connect(), so schema created in
# ensure_schema() would vanish before get_stats(). Use a local file instead.
_LOCAL_DB = os.environ.get("LOCAL_DB_PATH", "/tmp/restaurant-ai-bot.db")


def _connect_url() -> str:
    return TURSO_DATABASE_URL or _LOCAL_DB


class Row:
    """dict-style bracket access over a Turso result tuple, sqlite3.Row-compatible."""
    __slots__ = ("_cols", "_vals")

    def __init__(self, cols, vals):
        self._cols = cols
        self._vals = vals

    def __getitem__(self, key):
        return self._vals[self._cols.index(key)] if isinstance(key, str) else self._vals[key]

    def keys(self):
        return list(self._cols)

    def __repr__(self):
        return repr(dict(zip(self._cols, self._vals)))


class _Cursor:
    def __init__(self, cur):
        self._cur = cur

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def _wrap(self, row):
        if row is None:
            return None
        return Row([d[0] for d in self._cur.description], row)

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _Conn:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        cur = self._raw.execute(sql, tuple(params)) if params is not None else self._raw.execute(sql)
        return _Cursor(cur)

    def executescript(self, sql):
        return self._raw.executescript(sql)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    google_place_id TEXT UNIQUE,
    name            TEXT NOT NULL,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    city            TEXT,
    area            TEXT,
    category        TEXT,
    rating          REAL,
    review_count    INTEGER,
    website         TEXT,
    website_status  TEXT DEFAULT 'none',   -- none | social_only | has_site
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS leads (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id      INTEGER NOT NULL,
    name             TEXT,
    phone            TEXT,
    email            TEXT,
    address          TEXT,
    city             TEXT,
    area             TEXT,
    category         TEXT,
    rating           REAL,
    website_status   TEXT DEFAULT 'none',
    status           TEXT DEFAULT 'new',   -- new | site_generated | proposed | replied | claimed | sold | dead
    demo_token       TEXT,
    demo_created_at  TEXT,
    demo_expires_at  TEXT,
    emailed          INTEGER DEFAULT 0,
    email_sent_at    TEXT,
    replied          INTEGER DEFAULT 0,
    sold             INTEGER DEFAULT 0,
    claimed          INTEGER DEFAULT 0,
    claimed_at       TEXT,
    care_plan        TEXT,                 -- none | monthly | yearly
    notes            TEXT,
    created_at       TEXT,
    FOREIGN KEY (business_id) REFERENCES businesses(id)
);

CREATE TABLE IF NOT EXISTS demo_sites (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id       INTEGER NOT NULL,
    business_id   INTEGER,
    token         TEXT UNIQUE NOT NULL,
    html_path     TEXT,
    html          TEXT,            -- full page; required on hosts with no persistent disk
    template_used TEXT,
    views         INTEGER DEFAULT 0,
    is_live       INTEGER DEFAULT 1,
    created_at    TEXT,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

-- An opt-out must outlive the lead record that caused it.
CREATE TABLE IF NOT EXISTS suppression (
    email       TEXT PRIMARY KEY,
    reason      TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS email_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id    INTEGER,
    to_email   TEXT,
    subject    TEXT,
    provider_id TEXT,
    status     TEXT,
    created_at TEXT
);

-- Passcode gate: who has unlocked the bot, and failed-attempt tracking.
CREATE TABLE IF NOT EXISTS bot_auth (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    unlocked_at   TEXT,
    attempts      INTEGER DEFAULT 0,
    last_attempt  TEXT,
    reply_to_email TEXT
);

CREATE TABLE IF NOT EXISTS claims (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id            INTEGER,
    kind               TEXT,            -- build | build_plus_care
    amount_cents       INTEGER,
    care_plan          TEXT,            -- none | monthly | yearly
    stripe_session_id  TEXT,
    stripe_subscription_id TEXT,
    stripe_customer_id TEXT,
    buyer_email        TEXT,
    buyer_phone        TEXT,
    claim_token        TEXT,
    status             TEXT,            -- stub | pending | paid | failed
    created_at         TEXT,
    updated_at         TEXT
);

CREATE TABLE IF NOT EXISTS stripe_events (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT,
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS ops_meta (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_city   ON leads(city);
CREATE INDEX IF NOT EXISTS idx_demo_token   ON demo_sites(token);
"""


@contextmanager
def conn():
    raw = libsql.connect(_connect_url(), auth_token=TURSO_AUTH_TOKEN or "")
    c = _Conn(raw)
    try:
        yield c
        c.commit()
    finally:
        c.close()


_schema_ready = False


def turso_configured() -> bool:
    return bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)


def _ensure_column(c, table: str, name: str, decl: str):
    cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
    if name not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        _ensure_column(c, "bot_auth", "reply_to_email", "TEXT")
        _ensure_column(c, "demo_sites", "html", "TEXT")
        _ensure_column(c, "leads", "claimed", "INTEGER DEFAULT 0")
        _ensure_column(c, "leads", "claimed_at", "TEXT")
        _ensure_column(c, "leads", "care_plan", "TEXT")
        _ensure_column(c, "leads", "care_status", "TEXT")
        _ensure_column(c, "claims", "stripe_subscription_id", "TEXT")
        _ensure_column(c, "claims", "stripe_customer_id", "TEXT")
        _ensure_column(c, "claims", "buyer_email", "TEXT")
        _ensure_column(c, "claims", "buyer_phone", "TEXT")
        _ensure_column(c, "claims", "claim_token", "TEXT")
        _ensure_column(c, "claims", "updated_at", "TEXT")


def ensure_schema():
    """Create tables once per process, including before direct Handler tests."""
    global _schema_ready
    if _schema_ready:
        return
    init_db()
    _schema_ready = True


def db_status() -> dict:
    """Never raises — used by /stats and /health so a missing DB cannot 500 the site."""
    if not turso_configured():
        return {"db": "unconfigured", "persistent": False}
    try:
        ensure_schema()
        with conn() as c:
            c.execute("SELECT 1 FROM leads LIMIT 1")
        return {"db": "ok", "persistent": True}
    except Exception as e:
        return {"db": "error", "persistent": True, "db_error": str(e)}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ businesses
def upsert_business(**kw) -> int | None:
    """Insert a business; returns its id, or None if we've already seen it."""
    with conn() as c:
        existing = c.execute("SELECT id FROM businesses WHERE google_place_id = ?",
                             (kw.get("google_place_id"),)).fetchone()
        if existing:
            return None
        cur = c.execute(
            """INSERT INTO businesses
               (google_place_id, name, phone, email, address, city, area, category,
                rating, review_count, website, website_status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kw.get("google_place_id"), kw.get("name"), kw.get("phone"), kw.get("email"),
             kw.get("address"), kw.get("city"), kw.get("area"), kw.get("category"),
             kw.get("rating"), kw.get("review_count"), kw.get("website"),
             kw.get("website_status", "none"), now()))
        return cur.lastrowid


def create_lead(business_id: int, **kw) -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO leads
               (business_id, name, phone, email, address, city, area, category, rating,
                website_status, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,'new',?)""",
            (business_id, kw.get("name"), kw.get("phone"), kw.get("email"), kw.get("address"),
             kw.get("city"), kw.get("area"), kw.get("category"), kw.get("rating"),
             kw.get("website_status", "none"), now()))
        return cur.lastrowid


# ----------------------------------------------------------------------- leads
def get_leads(limit: int = 20, status: str | None = None, city: str | None = None):
    q = "SELECT * FROM leads"
    where, args = [], []
    if status:
        where.append("status = ?"); args.append(status)
    if city:
        where.append("city = ?"); args.append(city)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return c.execute(q, args).fetchall()


def get_lead(lead_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def get_lead_by_token(token: str):
    with conn() as c:
        return c.execute("SELECT * FROM leads WHERE demo_token = ?", (token,)).fetchone()


def update_lead(lead_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE leads SET {cols} WHERE id = ?", (*fields.values(), lead_id))


def leads_needing_site(limit: int = 25):
    with conn() as c:
        return c.execute(
            "SELECT * FROM leads WHERE demo_token IS NULL AND status = 'new' "
            "ORDER BY rating DESC NULLS LAST LIMIT ?", (limit,)).fetchall()


def leads_needing_email(limit: int = 25):
    with conn() as c:
        return c.execute(
            "SELECT * FROM leads WHERE emailed = 0 AND demo_token IS NOT NULL "
            "AND ((email IS NOT NULL AND email != '') "
            "OR (phone IS NOT NULL AND phone != '')) LIMIT ?", (limit,)).fetchall()


def leads_missing_email(limit: int = 25):
    """Leads with a demo already built but no email on file yet, plus the
    business's website/website_status so the caller has something to scrape."""
    with conn() as c:
        return c.execute(
            "SELECT leads.*, businesses.website AS biz_website "
            "FROM leads JOIN businesses ON businesses.id = leads.business_id "
            "WHERE leads.demo_token IS NOT NULL AND leads.status != 'dead' "
            "AND (leads.email IS NULL OR leads.email = '') LIMIT ?", (limit,)).fetchall()


def set_email(lead_id: int, business_id: int, email: str):
    with conn() as c:
        c.execute("UPDATE leads SET email = ? WHERE id = ?", (email, lead_id))
        c.execute("UPDATE businesses SET email = ? WHERE id = ?", (email, business_id))


# ------------------------------------------------------------------ demo sites
def create_demo_site(lead_id: int, business_id, html: str, token: str, template_used=None):
    """Write the generated HTML to disk and record it."""
    from config import DEMO_DIR
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    path = DEMO_DIR / f"{token}.html"
    path.write_text(html, encoding="utf-8")
    with conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO demo_sites
               (lead_id, business_id, token, html_path, html, template_used, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (lead_id, business_id, token, str(path), html, template_used, now()))
    return str(path)


def save_demo_html(token: str, html: str):
    with conn() as c:
        c.execute("UPDATE demo_sites SET html = ? WHERE token = ?", (html, token))


def get_demo(token: str):
    with conn() as c:
        return c.execute("SELECT * FROM demo_sites WHERE token = ?", (token,)).fetchone()


def bump_demo_views(token: str):
    with conn() as c:
        c.execute("UPDATE demo_sites SET views = views + 1 WHERE token = ?", (token,))


# ----------------------------------------------------------------- suppression
def suppress(email: str, reason: str = "unsubscribe"):
    if not email:
        return
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO suppression (email, reason, created_at) VALUES (?,?,?)",
                  (email.strip().lower(), reason, now()))
        c.execute("UPDATE leads SET status = 'dead', notes = COALESCE(notes,'') || ' [opted out]' "
                  "WHERE lower(email) = ?", (email.strip().lower(),))


def is_suppressed(email: str) -> bool:
    if not email:
        return False
    with conn() as c:
        return c.execute("SELECT 1 FROM suppression WHERE email = ?",
                         (email.strip().lower(),)).fetchone() is not None


def log_email(lead_id, to_email, subject, provider_id, status):
    with conn() as c:
        c.execute("""INSERT INTO email_log (lead_id, to_email, subject, provider_id, status, created_at)
                     VALUES (?,?,?,?,?,?)""",
                  (lead_id, to_email, subject, provider_id, status, now()))


# ------------------------------------------------------------------ auth gate
def is_unlocked(user_id: int) -> bool:
    with conn() as c:
        r = c.execute("SELECT unlocked_at FROM bot_auth WHERE user_id = ?", (user_id,)).fetchone()
        return bool(r and r["unlocked_at"])


def unlock_user(user_id: int, username: str = ""):
    with conn() as c:
        c.execute("""INSERT INTO bot_auth (user_id, username, unlocked_at, attempts, last_attempt)
                     VALUES (?,?,?,0,?)
                     ON CONFLICT(user_id) DO UPDATE SET
                       unlocked_at = excluded.unlocked_at, attempts = 0,
                       username = excluded.username""",
                  (user_id, username, now(), now()))


def lock_user(user_id: int):
    with conn() as c:
        c.execute("UPDATE bot_auth SET unlocked_at = NULL WHERE user_id = ?", (user_id,))


def lock_all_users():
    """Revoke all active unlocks. Used when the passcode is rotated."""
    with conn() as c:
        c.execute("UPDATE bot_auth SET unlocked_at = NULL WHERE unlocked_at IS NOT NULL")


def record_failed_attempt(user_id: int, username: str = "") -> tuple[int, str | None]:
    """Increments the failure counter. Returns (attempts, last_attempt_iso)."""
    with conn() as c:
        c.execute("""INSERT INTO bot_auth (user_id, username, attempts, last_attempt)
                     VALUES (?,?,1,?)
                     ON CONFLICT(user_id) DO UPDATE SET
                       attempts = bot_auth.attempts + 1, last_attempt = excluded.last_attempt,
                       username = excluded.username""",
                  (user_id, username, now()))
        r = c.execute("SELECT attempts, last_attempt FROM bot_auth WHERE user_id = ?",
                      (user_id,)).fetchone()
        return (r["attempts"], r["last_attempt"]) if r else (1, now())


def get_auth_row(user_id: int):
    with conn() as c:
        return c.execute("SELECT * FROM bot_auth WHERE user_id = ?", (user_id,)).fetchone()


def set_reply_to(user_id: int, email: str):
    with conn() as c:
        c.execute("UPDATE bot_auth SET reply_to_email = ? WHERE user_id = ?", (email, user_id))


def get_reply_to(user_id: int) -> str:
    row = get_auth_row(user_id)
    return (row["reply_to_email"] or "") if row else ""


# ------------------------------------------------------------------ ops meta
def get_meta(key: str, default: str = "") -> str:
    ensure_schema()
    with conn() as c:
        r = c.execute("SELECT value FROM ops_meta WHERE key = ?", (key,)).fetchone()
        return (r["value"] if r and r["value"] is not None else default)


def set_meta(key: str, value: str):
    ensure_schema()
    with conn() as c:
        c.execute(
            "INSERT INTO ops_meta (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, value, now()))


def consume_daily_budget(name: str, daily_limit: int, amount: int = 1) -> bool:
    """Reserve API calls in UTC-backed meta storage; False means stop calling."""
    if daily_limit <= 0 or amount <= 0:
        return False
    ensure_schema()
    key = f"budget:{name}:{datetime.now(timezone.utc).date().isoformat()}"
    with conn() as c:
        row = c.execute("SELECT value FROM ops_meta WHERE key = ?", (key,)).fetchone()
        used = int(row["value"] or 0) if row else 0
        if used + amount > daily_limit:
            return False
        c.execute(
            "INSERT INTO ops_meta (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, str(used + amount), now()))
    return True


def mark_claimed(
    lead_id: int,
    care_plan: str = "none",
    session_id: str = "",
    amount_cents: int = 0,
    status: str = "paid",
    subscription_id: str = "",
    customer_id: str = "",
    buyer_email: str = "",
    buyer_phone: str = "",
):
    """Flip a lead to claimed and upsert its Stripe Checkout claim."""
    import secrets
    plan = care_plan if care_plan in ("monthly", "yearly") else "none"
    update_lead(
        lead_id, status="claimed", claimed=1, claimed_at=now(), care_plan=plan,
        care_status="active" if plan != "none" else "none",
        demo_expires_at=None,
    )
    kind = "build_plus_care" if plan in ("monthly", "yearly") else "build"
    with conn() as c:
        existing = c.execute(
            "SELECT id, claim_token FROM claims WHERE stripe_session_id = ? "
            "ORDER BY id DESC LIMIT 1", (session_id or "",)).fetchone() if session_id else None
        claim_token = (
            existing["claim_token"]
            if existing and existing["claim_token"]
            else secrets.token_urlsafe(24)
        )
        values = (
            kind, amount_cents, plan, subscription_id or "", customer_id or "",
            buyer_email or "", buyer_phone or "", claim_token, status, now(),
        )
        if existing:
            c.execute(
                """UPDATE claims SET kind=?, amount_cents=?, care_plan=?,
                   stripe_subscription_id=?, stripe_customer_id=?, buyer_email=?,
                   buyer_phone=?, claim_token=?, status=?, updated_at=? WHERE id=?""",
                (*values, existing["id"]))
        else:
            c.execute(
                """INSERT INTO claims
                   (lead_id, kind, amount_cents, care_plan, stripe_session_id,
                    stripe_subscription_id, stripe_customer_id, buyer_email,
                    buyer_phone, claim_token, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (lead_id, kind, amount_cents, plan, session_id or "",
                 subscription_id or "", customer_id or "", buyer_email or "",
                 buyer_phone or "", claim_token, status, now(), now()))
    return get_claim_by_session(session_id)


def record_claim_pending(lead_id: int, care_plan: str, session_id: str, amount_cents: int):
    plan = care_plan if care_plan in ("monthly", "yearly") else "none"
    kind = "build_plus_care" if plan in ("monthly", "yearly") else "build"
    with conn() as c:
        c.execute(
            """INSERT INTO claims
               (lead_id, kind, amount_cents, care_plan, stripe_session_id, status, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (lead_id, kind, amount_cents, plan, session_id or "", "pending", now()))


def get_claim_by_session(session_id: str):
    if not session_id:
        return None
    with conn() as c:
        return c.execute("SELECT * FROM claims WHERE stripe_session_id = ?",
                         (session_id,)).fetchone()


def stripe_event_seen(event_id: str) -> bool:
    if not event_id:
        return False
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM stripe_events WHERE event_id = ?", (event_id,)
        ).fetchone() is not None


def record_stripe_event(event_id: str, event_type: str):
    if not event_id:
        return
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO stripe_events (event_id, event_type, processed_at) "
            "VALUES (?,?,?)", (event_id, event_type, now()))


def mark_checkout_expired(session_id: str):
    if not session_id:
        return
    with conn() as c:
        c.execute(
            "UPDATE claims SET status='expired', updated_at=? "
            "WHERE stripe_session_id=? AND status='pending'",
            (now(), session_id))


def _lead_for_subscription(subscription_id: str = "", customer_id: str = ""):
    with conn() as c:
        if subscription_id:
            row = c.execute(
                "SELECT lead_id FROM claims WHERE stripe_subscription_id=? "
                "ORDER BY id DESC LIMIT 1", (subscription_id,)).fetchone()
            if row:
                return row["lead_id"]
        if customer_id:
            row = c.execute(
                "SELECT lead_id FROM claims WHERE stripe_customer_id=? "
                "ORDER BY id DESC LIMIT 1", (customer_id,)).fetchone()
            if row:
                return row["lead_id"]
    return None


def mark_care_paid(
    lead_id: int = 0, subscription_id: str = "", customer_id: str = ""
) -> bool:
    lead_id = lead_id or _lead_for_subscription(subscription_id, customer_id) or 0
    if not lead_id:
        return False
    update_lead(lead_id, care_status="active")
    with conn() as c:
        c.execute(
            "UPDATE claims SET status='paid', updated_at=? WHERE lead_id=? "
            "AND care_plan IN ('monthly','yearly')",
            (now(), lead_id))
    return True


def mark_care_cancelled(
    lead_id: int = 0, subscription_id: str = "", customer_id: str = ""
) -> bool:
    lead_id = lead_id or _lead_for_subscription(subscription_id, customer_id) or 0
    if not lead_id:
        return False
    lead = get_lead(lead_id)
    previous = (lead["notes"] or "") if lead else ""
    note = f"[{now()[:16]}] Care subscription cancelled"
    update_lead(
        lead_id, care_status="cancelled",
        notes=(previous + "\n" if previous else "") + note)
    return True


# ----------------------------------------------------------------------- stats
def get_stats() -> dict:
    ensure_schema()
    with conn() as c:
        one = lambda q: c.execute(q).fetchone()[0]
        by_city = {r["city"] or "?": r["n"] for r in c.execute(
            "SELECT city, COUNT(*) n FROM leads GROUP BY city ORDER BY n DESC")}
        by_cat = {r["category"] or "?": r["n"] for r in c.execute(
            "SELECT category, COUNT(*) n FROM leads GROUP BY category ORDER BY n DESC")}
        by_ws = {r["website_status"] or "none": r["n"] for r in c.execute(
            "SELECT website_status, COUNT(*) n FROM leads GROUP BY website_status")}
        claimed_n = one(
            "SELECT COUNT(*) FROM leads WHERE COALESCE(claimed,0) = 1 OR status = 'claimed'")
        care_n = one(
            "SELECT COUNT(*) FROM leads WHERE care_plan IN ('monthly','yearly')")
        demos_n = one(
            "SELECT COUNT(*) FROM leads WHERE demo_token IS NOT NULL AND demo_token != ''")
        return {
            "businesses": one("SELECT COUNT(*) FROM businesses"),
            "leads": one("SELECT COUNT(*) FROM leads"),
            "sites": one("SELECT COUNT(*) FROM demo_sites"),
            "emailed": one("SELECT COUNT(*) FROM leads WHERE emailed = 1"),
            "replied": one("SELECT COUNT(*) FROM leads WHERE replied = 1"),
            "claimed": claimed_n,
            "sold": one("SELECT COUNT(*) FROM leads WHERE sold = 1"),
            "care": care_n,
            "suppressed": one("SELECT COUNT(*) FROM suppression"),
            "by_city": by_city,
            "by_category": by_cat,
            "by_website_status": by_ws,
            "funnel": {
                "leads": one("SELECT COUNT(*) FROM leads WHERE status != 'dead'"),
                "demos": demos_n,
                "emailed": one("SELECT COUNT(*) FROM leads WHERE emailed = 1"),
                "claimed": claimed_n,
                "sold": one("SELECT COUNT(*) FROM leads WHERE sold = 1"),
                "care": care_n,
            },
        }


if __name__ == "__main__":
    init_db()
    print(f"initialized {_connect_url()}")
    print(get_stats())
