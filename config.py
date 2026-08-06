"""
Configuration for the Local Business AI Bot.

Everything secret comes from the environment (.env). Everything structural —
cities, categories, templates — lives here so the bot can scale to new markets
by editing one dict.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:  # dotenv optional; env vars may already be exported
    pass

BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------- credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
LOCATIONIQ_API_KEY = os.getenv("LOCATIONIQ_API_KEY", "").strip()
# Optional: used only to double-check a lead right before emailing it, since
# LocationIQ's free OSM data under-reports websites (see scanner.verify_website).
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()

# Optional: powers per-business demo copy in writer.py. Any one of these is
# enough — checked in this order, first one set wins. None set = generic
# static copy (still works, just not personalized). No Hermes install needed.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

# Comma-separated Telegram user ids allowed to drive the bot.
# Empty = anyone who knows the passcode below.
ADMIN_USER_IDS = [
    int(x) for x in os.getenv("ADMIN_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()
]

# Passcode gate: a user must /unlock <code> once before any command works.
# A short numeric code is guessable by brute force, so attempts are rate-limited
# (see MAX_UNLOCK_ATTEMPTS) and the message containing it is deleted immediately.
BOT_PASSCODE = os.getenv("BOT_PASSCODE", "").strip()
MAX_UNLOCK_ATTEMPTS = int(os.getenv("MAX_UNLOCK_ATTEMPTS", "5"))
UNLOCK_COOLDOWN_MIN = int(os.getenv("UNLOCK_COOLDOWN_MIN", "15"))

# ---------------------------------------------------------------- deployment
DEMO_BASE_URL = os.getenv("DEMO_BASE_URL", "http://localhost:8080").rstrip("/")
DEMO_EXPIRE_HOURS = int(os.getenv("DEMO_EXPIRE_HOURS", "72"))
PORT = int(os.getenv("PORT", "8080"))
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "leads.db"))
DEMO_DIR = Path(os.getenv("DEMO_DIR", str(BASE_DIR / "demos")))

# ---------------------------------------------------------------- sender identity
# CAN-SPAM requires accurate sender identification, a real postal address, and a
# working opt-out in every commercial email. These are not optional extras.
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
FROM_NAME = os.getenv("FROM_NAME", "Local Web Studio")
REPLY_TO = os.getenv("REPLY_TO", "").strip()
SENDER_POSTAL_ADDRESS = os.getenv("SENDER_POSTAL_ADDRESS", "").strip()
UNSUBSCRIBE_BASE = os.getenv("UNSUBSCRIBE_BASE", DEMO_BASE_URL).rstrip("/")
PRICE_USD = int(os.getenv("PRICE_USD", "299"))

# How many proposal emails the automated daily pipeline (/pipeline/run) may
# send in one run. Manual /propose in Telegram is not affected by this.
DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", "15"))

# ---------------------------------------------------------------- markets
# lat/lng = approximate downtown, used to geolocate each area within the city.
CITIES = {
    "houston": {"name": "Houston", "state": "TX", "lat": 29.7604, "lng": -95.3698,
                "areas": ["Montrose", "The Heights", "Midtown", "East End", "Rice Village",
                          "Bellaire", "Katy", "Sugar Land", "Spring Branch", "Galleria",
                          "Third Ward", "Near Northside"]},
    "austin": {"name": "Austin", "state": "TX", "lat": 30.2672, "lng": -97.7431,
               "areas": ["East Austin", "South Congress", "Hyde Park", "Mueller",
                         "North Loop", "Zilker", "Cherrywood", "Round Rock"]},
    "dallas": {"name": "Dallas", "state": "TX", "lat": 32.7767, "lng": -96.7970,
               "areas": ["Deep Ellum", "Bishop Arts", "Lower Greenville", "Oak Cliff",
                         "Knox Henderson", "Uptown", "Richardson", "Plano"]},
    "san-antonio": {"name": "San Antonio", "state": "TX", "lat": 29.4241, "lng": -98.4936,
                    "areas": ["Southtown", "Pearl District", "Alamo Heights", "Monte Vista",
                              "Stone Oak", "Northwest Side"]},
    "miami": {"name": "Miami", "state": "FL", "lat": 25.7617, "lng": -80.1918,
              "areas": ["Little Havana", "Wynwood", "Coral Gables", "Little Haiti",
                        "Brickell", "Hialeah", "Kendall", "North Miami", "Doral",
                        "Coconut Grove"]},
    "los-angeles": {"name": "Los Angeles", "state": "CA", "lat": 34.0522, "lng": -118.2437,
                    "areas": ["Highland Park", "Koreatown", "Boyle Heights", "Silver Lake",
                              "Echo Park", "Culver City", "Van Nuys", "Long Beach"]},
    "new-york": {"name": "New York", "state": "NY", "lat": 40.7128, "lng": -74.0060,
                 "areas": ["Astoria", "Sunset Park", "Jackson Heights", "Bushwick",
                           "Harlem", "Flushing", "Bay Ridge", "Washington Heights"]},
    "chicago": {"name": "Chicago", "state": "IL", "lat": 41.8781, "lng": -87.6298,
                "areas": ["Pilsen", "Logan Square", "Bridgeport", "Albany Park",
                          "Hyde Park", "Uptown", "Humboldt Park"]},
}

DEFAULT_CITIES = ["houston", "miami", "austin"]

# ---------------------------------------------------------------- categories
# `types` are Google Places (New) primary types. `label` is human copy used in
# emails and demo sites. `hero` drives the demo template's headline.
# OSM amenity/shop tag values, used both as the LocationIQ /nearby `tag` filter
# and to classify results back into a category (see category_for_types).
BUSINESS_CATEGORIES = {
    "restaurant": {"types": ["restaurant"], "label": "restaurant",
                   "hero": "Real food. Real people. Right here.",
                   "sections": ["Menu", "Hours", "Location", "Order"]},
    "cafe": {"types": ["cafe"], "label": "cafe",
             "hero": "Your neighborhood cup.",
             "sections": ["Drinks", "Hours", "Location"]},
    "bakery": {"types": ["bakery"], "label": "bakery",
               "hero": "Baked fresh, every morning.",
               "sections": ["Fresh Today", "Hours", "Orders"]},
    "barber": {"types": ["hairdresser"], "label": "barber shop",
               "hero": "Sharp cuts. No waiting.",
               "sections": ["Services", "Hours", "Book"]},
    "salon": {"types": ["beauty"], "label": "salon",
              "hero": "Look the way you want to look.",
              "sections": ["Services", "Hours", "Book"]},
    "auto": {"types": ["car_repair"], "label": "auto shop",
             "hero": "Honest work. Fair prices.",
             "sections": ["Services", "Hours", "Estimate"]},
    "gym": {"types": ["fitness_centre"], "label": "gym",
            "hero": "Show up. That's the hard part.",
            "sections": ["Classes", "Hours", "Join"]},
    "florist": {"types": ["florist"], "label": "florist",
                "hero": "Arrangements that say it better.",
                "sections": ["Arrangements", "Hours", "Order"]},
    "dentist": {"types": ["dentist"], "label": "dental office",
                "hero": "A practice that puts you at ease.",
                "sections": ["Services", "Hours", "Book"]},
    "lawyer": {"types": ["lawyer"], "label": "law office",
               "hero": "Straight answers. Real advocacy.",
               "sections": ["Practice Areas", "Hours", "Consult"]},
    "plumber": {"types": ["plumber"], "label": "plumbing service",
                "hero": "Fixed right the first time.",
                "sections": ["Services", "Hours", "Estimate"]},
    "electrician": {"types": ["electrician"], "label": "electrical service",
                    "hero": "Licensed, insured, on time.",
                    "sections": ["Services", "Hours", "Estimate"]},
    "roofer": {"types": ["roofer"], "label": "roofing company",
               "hero": "Built to take the weather.",
               "sections": ["Services", "Hours", "Estimate"]},
    "locksmith": {"types": ["locksmith"], "label": "locksmith",
                  "hero": "Locked out? Not for long.",
                  "sections": ["Services", "Hours", "Call"]},
    "jewelry": {"types": ["jewelry"], "label": "jeweler",
                "hero": "Pieces made to keep.",
                "sections": ["Collections", "Hours", "Visit"]},
    "tattoo": {"types": ["tattoo"], "label": "tattoo shop",
               "hero": "Your idea, done right.",
               "sections": ["Artists", "Hours", "Book"]},
    "veterinary": {"types": ["veterinary"], "label": "vet clinic",
                   "hero": "Care for the whole family.",
                   "sections": ["Services", "Hours", "Book"]},
    "optician": {"types": ["optician"], "label": "optician",
                 "hero": "See clearly. Look good doing it.",
                 "sections": ["Services", "Hours", "Book"]},
    "dry_cleaning": {"types": ["dry_cleaning"], "label": "dry cleaner",
                      "hero": "Fresh, pressed, ready.",
                      "sections": ["Services", "Hours", "Drop Off"]},
    "photo": {"types": ["photo"], "label": "photo studio",
              "hero": "Moments worth keeping.",
              "sections": ["Portfolio", "Hours", "Book"]},
    "accountant": {"types": ["accountant"], "label": "accounting firm",
                   "hero": "Numbers you can trust.",
                   "sections": ["Services", "Hours", "Consult"]},
    "estate_agent": {"types": ["estate_agent"], "label": "real estate agency",
                      "hero": "Local expertise, real results.",
                      "sections": ["Listings", "Hours", "Contact"]},
    "insurance": {"types": ["insurance"], "label": "insurance agency",
                  "hero": "Coverage that actually makes sense.",
                  "sections": ["Coverage", "Hours", "Get a Quote"]},
    "pet": {"types": ["pet"], "label": "pet shop",
            "hero": "Everything your pet needs.",
            "sections": ["Services", "Hours", "Visit"]},
    "hardware": {"types": ["hardware"], "label": "hardware store",
                 "hero": "If it's for the job, it's here.",
                 "sections": ["Departments", "Hours", "Visit"]},
    "books": {"types": ["books"], "label": "bookstore",
              "hero": "Shelves worth getting lost in.",
              "sections": ["Sections", "Hours", "Visit"]},
}

DEFAULT_CATEGORIES = list(BUSINESS_CATEGORIES.keys())


def get_city(key: str) -> dict:
    return CITIES.get((key or "").lower(), CITIES["houston"])


def get_city_label(key: str) -> str:
    c = get_city(key)
    return f"{c['name']} {c['state']}"


def category_for_types(types) -> str:
    """Map Google place types back to one of our categories."""
    types = set(types or [])
    for cat, meta in BUSINESS_CATEGORIES.items():
        if types & set(meta["types"]):
            return cat
    return "restaurant"
