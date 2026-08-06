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

# Twilio SMS — free trial (100 SMS, no credit card).
# Used when a lead has a phone but no email.
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM = os.getenv("TWILIO_FROM", "").strip()

# Hunter.io — free tier (25 email searches/month).
# Used to find business emails by domain.
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "").strip()

# Apollo.io — free tier (100 enrichment credits).
# Used as fallback for email/phone enrichment.
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "").strip()

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
BOT_PASSCODE = os.getenv("BOT_PASSCODE", "1980").strip()
MAX_UNLOCK_ATTEMPTS = int(os.getenv("MAX_UNLOCK_ATTEMPTS", "5"))
UNLOCK_COOLDOWN_MIN = int(os.getenv("UNLOCK_COOLDOWN_MIN", "15"))

# ---------------------------------------------------------------- deployment
DEMO_BASE_URL = os.getenv("DEMO_BASE_URL", "https://restaurant-ai-bot-n844.onrender.com").rstrip("/")
DEMO_EXPIRE_HOURS = int(os.getenv("DEMO_EXPIRE_HOURS", "72"))
PORT = int(os.getenv("PORT", "8080"))
DB_PATH = os.getenv("DB_PATH", str(
    Path("/app/persist/data/leads.db") if (Path("/app/persist").exists())
    else BASE_DIR / "data" / "leads.db"
))
DEMO_DIR = Path(os.getenv("DEMO_DIR", str(
    Path("/app/persist/demos") if (Path("/app/persist").exists())
    else BASE_DIR / "demos"
)))

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
# lat/lng = approximate downtown. Each area maps to its own (lat, lng), geocoded
# once ahead of time — scanning hits LocationIQ's /nearby endpoint directly with
# these instead of re-geocoding the area name on every scan, which used to burn
# through the free-tier /search quota fast enough to cause spurious 404s.
CITIES = {
    "houston": {"name": "Houston", "state": "TX", "lat": 29.7604, "lng": -95.3698,
                "areas": {
                    "Montrose": (29.7447, -95.3913), "The Heights": (29.7977, -95.3984),
                    "Midtown": (29.7412, -95.3762), "East End": (29.7497, -95.3073),
                    "Rice Village": (29.7168, -95.4048), "Bellaire": (29.7070, -95.4416),
                    "Katy": (29.7890, -95.7123), "Sugar Land": (29.5896, -95.6303),
                    "Spring Branch": (29.8066, -95.5257), "Galleria": (29.7380, -95.4643),
                    "Third Ward": (29.7244, -95.3591), "Near Northside": (29.7930, -95.3611),
                }},
    "austin": {"name": "Austin", "state": "TX", "lat": 30.2672, "lng": -97.7431,
               "areas": {
                   "East Austin": (30.2745, -97.7165), "South Congress": (30.2385, -97.7505),
                   "Hyde Park": (30.3044, -97.7304), "Mueller": (30.2965, -97.7002),
                   "North Loop": (30.3179, -97.7188), "Zilker": (30.2542, -97.7696),
                   "Cherrywood": (30.2920, -97.7177), "Round Rock": (30.4768, -97.6738),
               }},
    "dallas": {"name": "Dallas", "state": "TX", "lat": 32.7767, "lng": -96.7970,
               "areas": {
                   "Deep Ellum": (32.7843, -96.7805), "Bishop Arts": (32.7490, -96.8244),
                   "Lower Greenville": (32.8235, -96.7701), "Oak Cliff": (32.7393, -96.8111),
                   "Knox Henderson": (32.8159, -96.7897), "Uptown": (32.8007, -96.7999),
                   "Richardson": (32.9482, -96.7297), "Plano": (33.0221, -96.8363),
               }},
    "san-antonio": {"name": "San Antonio", "state": "TX", "lat": 29.4241, "lng": -98.4936,
                    "areas": {
                        "Southtown": (29.4102, -98.4912), "Pearl District": (29.4429, -98.4770),
                        "Alamo Heights": (29.4916, -98.4647), "Monte Vista": (29.4579, -98.4919),
                        "Stone Oak": (29.6494, -98.4513), "Northwest Side": (29.5200, -98.6300),
                    }},
    "miami": {"name": "Miami", "state": "FL", "lat": 25.7617, "lng": -80.1918,
              "areas": {
                  "Little Havana": (25.7682, -80.2335), "Wynwood": (25.8014, -80.1991),
                  "Coral Gables": (25.7331, -80.2585), "Little Haiti": (25.8304, -80.1928),
                  "Brickell": (25.7642, -80.1954), "Hialeah": (25.8268, -80.2814),
                  "Kendall": (25.6793, -80.3173), "North Miami": (25.8901, -80.1867),
                  "Doral": (25.8195, -80.3553), "Coconut Grove": (25.7126, -80.2570),
              }},
    "los-angeles": {"name": "Los Angeles", "state": "CA", "lat": 34.0522, "lng": -118.2437,
                    "areas": {
                        "Highland Park": (34.1099, -118.1970), "Koreatown": (34.0618, -118.3054),
                        "Boyle Heights": (34.0437, -118.2098), "Silver Lake": (34.0897, -118.2694),
                        "Echo Park": (34.0780, -118.2568), "Culver City": (34.0211, -118.3965),
                        "Van Nuys": (34.1866, -118.4487), "Long Beach": (33.7690, -118.1916),
                    }},
    "new-york": {"name": "New York", "state": "NY", "lat": 40.7128, "lng": -74.0060,
                 "areas": {
                     "Astoria": (40.7720, -73.9303), "Sunset Park": (40.6442, -74.0076),
                     "Jackson Heights": (40.7557, -73.8858), "Bushwick": (40.6943, -73.9187),
                     "Harlem": (40.8079, -73.9455), "Flushing": (40.7654, -73.8174),
                     "Bay Ridge": (40.6320, -74.0232), "Washington Heights": (40.8402, -73.9402),
                 }},
    "chicago": {"name": "Chicago", "state": "IL", "lat": 41.8781, "lng": -87.6298,
                "areas": {
                    "Pilsen": (41.8570, -87.6619), "Logan Square": (41.9284, -87.7068),
                    "Bridgeport": (41.8353, -87.6462), "Albany Park": (41.9703, -87.7160),
                    "Hyde Park": (41.7944, -87.5939), "Uptown": (41.9666, -87.6555),
                    "Humboldt Park": (41.9028, -87.7209),
                }},
}

DEFAULT_CITIES = ["houston", "miami", "austin"]

# Chains and franchises the scanner should skip — they already have
# corporate sites and don't need a local demo.
CHAIN_NAMES = {
    "starbucks", "pizza hut", "ihop", "mcdonald", "burger king",
    "wendys", "chick-fil-a", "taco bell", "subway", "dominos",
    "papa john", "dunkin", "kfc", "popeyes", "chick-fil",
    "panera", "chipotle", "taco bell", "pizza hut", "kfc",
    "burger king", "mcdonalds", "wendy", "dominos", "subway",
    "papa johns", "dunkin donuts", "chick fil a",
}

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
