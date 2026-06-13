import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "restaurant-bot.db")

# Allow DATABASE_URL env var override (e.g. sqlite:///data/restaurant-bot.db)
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url and _db_url.startswith("sqlite:///"):
    DB_PATH = _db_url[len("sqlite:///"):]

# Ensure parent directory exists
_db_dir = os.path.dirname(DB_PATH)
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_id TEXT UNIQUE,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            cuisine TEXT,
            rating REAL,
            price_level INTEGER,
            user_ratings_total INTEGER,
            has_website INTEGER DEFAULT 0,
            website_url TEXT,
            website_status TEXT DEFAULT 'unknown',
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER REFERENCES restaurants(id),
            status TEXT DEFAULT 'new',
            priority INTEGER DEFAULT 0,
            notes TEXT,
            generated_site_path TEXT,
            demo_token TEXT UNIQUE,
            demo_created_at TIMESTAMP,
            demo_expires_at TIMESTAMP,
            demo_viewed INTEGER DEFAULT 0,
            emailed INTEGER DEFAULT 0,
            email_sent_at TIMESTAMP,
            email_opened INTEGER DEFAULT 0,
            email_replied INTEGER DEFAULT 0,
            followed_up INTEGER DEFAULT 0,
            sold INTEGER DEFAULT 0,
            sold_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS generated_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES leads(id),
            restaurant_id INTEGER,
            html_content TEXT,
            template_used TEXT,
            protected_url TEXT,
            token TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES leads(id),
            to_email TEXT,
            subject TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            opened INTEGER DEFAULT 0,
            replied INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT,
            results_count INTEGER,
            leads_found INTEGER,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def add_restaurant(place):
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT OR IGNORE INTO restaurants 
            (place_id, name, address, phone, cuisine, rating, price_level, user_ratings_total, has_website, website_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            place.get("place_id"),
            place.get("name"),
            place.get("address"),
            place.get("phone"),
            ", ".join(place.get("types", [])),
            place.get("rating"),
            place.get("price_level"),
            place.get("user_ratings_total"),
            1 if place.get("website") else 0,
            "has_site" if place.get("website") else "no_site"
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def add_lead(restaurant_id, priority=0):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO leads (restaurant_id, priority) VALUES (?, ?)",
            (restaurant_id, priority)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_leads(status=None, limit=20):
    conn = get_db()
    try:
        query = """
            SELECT l.*, r.name, r.address, r.phone, r.cuisine, r.rating, r.website_status, r.website_url
            FROM leads l
            JOIN restaurants r ON l.restaurant_id = r.id
        """
        params = []
        if status:
            query += " WHERE l.status = ?"
            params.append(status)
        query += " ORDER BY l.priority DESC, l.created_at DESC LIMIT ?"
        params.append(limit)
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()

def get_restaurant(id):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM restaurants WHERE id = ?", (id,)).fetchone()
    finally:
        conn.close()

def update_lead(lead_id, **kwargs):
    if not kwargs:
        return
    conn = get_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [lead_id]
        conn.execute(f"UPDATE leads SET {sets} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()

def create_demo_site(lead_id, restaurant_id, html, token):
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO generated_sites (lead_id, restaurant_id, html_content, token)
            VALUES (?, ?, ?, ?)
        """, (lead_id, restaurant_id, html, token))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_demo_by_token(token):
    conn = get_db()
    try:
        return conn.execute("""
            SELECT gs.*, r.name, r.address, r.phone
            FROM generated_sites gs
            JOIN restaurants r ON gs.restaurant_id = r.id
            WHERE gs.token = ?
        """, (token,)).fetchone()
    finally:
        conn.close()

def log_scan(area, total, leads):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO scan_log (area, results_count, leads_found) VALUES (?, ?, ?)",
            (area, total, leads)
        )
        conn.commit()
    finally:
        conn.close()

def get_stats():
    conn = get_db()
    try:
        r = conn.execute("SELECT COUNT(*) as c FROM restaurants").fetchone()["c"]
        l = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
        e = conn.execute("SELECT COUNT(*) as c FROM leads WHERE emailed=1").fetchone()["c"]
        s = conn.execute("SELECT COUNT(*) as c FROM leads WHERE sold=1").fetchone()["c"]
        return {"restaurants": r, "leads": l, "emailed": e, "sold": s}
    finally:
        conn.close()
