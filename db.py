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
from datetime import datetime

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
    status           TEXT DEFAULT 'new',   -- new | site_generated | proposed | replied | sold | dead
    demo_token       TEXT,
    demo_created_at  TEXT,
    demo_expires_at  TEXT,
    emailed          INTEGER DEFAULT 0,
    email_sent_at    TEXT,
    replied          INTEGER DEFAULT 0,
    sold             INTEGER DEFAULT 0,
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


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(bot_auth)")}
        if "reply_to_email" not in cols:
            c.execute("ALTER TABLE bot_auth ADD COLUMN reply_to_email TEXT")
        demo_cols = {r["name"] for r in c.execute("PRAGMA table_info(demo_sites)")}
        if "html" not in demo_cols:
            c.execute("ALTER TABLE demo_sites ADD COLUMN html TEXT")


def ensure_schema():
    """Create tables if needed. Vercel invokes Handler without main(), so this
    must run on the first request rather than only at process startup."""
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
            "AND email IS NOT NULL AND email != '' LIMIT ?", (limit,)).fetchall()


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


# ----------------------------------------------------------------------- stats
def get_stats() -> dict:
    ensure_schema()
    with conn() as c:
        one = lambda q: c.execute(q).fetchone()[0]
        by_city = {r["city"] or "?": r["n"] for r in c.execute(
            "SELECT city, COUNT(*) n FROM leads GROUP BY city ORDER BY n DESC")}
        by_cat = {r["category"] or "?": r["n"] for r in c.execute(
            "SELECT category, COUNT(*) n FROM leads GROUP BY category ORDER BY n DESC")}
        return {
            "businesses": one("SELECT COUNT(*) FROM businesses"),
            "leads": one("SELECT COUNT(*) FROM leads"),
            "sites": one("SELECT COUNT(*) FROM demo_sites"),
            "emailed": one("SELECT COUNT(*) FROM leads WHERE emailed = 1"),
            "replied": one("SELECT COUNT(*) FROM leads WHERE replied = 1"),
            "sold": one("SELECT COUNT(*) FROM leads WHERE sold = 1"),
            "suppressed": one("SELECT COUNT(*) FROM suppression"),
            "by_city": by_city,
            "by_category": by_cat,
        }


if __name__ == "__main__":
    init_db()
    print(f"initialized {DB_PATH}")
    print(get_stats())
