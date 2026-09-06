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
BOT_PASSCODE = os.getenv("BOT_PASSCODE", "9911").strip()
MAX_UNLOCK_ATTEMPTS = int(os.getenv("MAX_UNLOCK_ATTEMPTS", "5"))
UNLOCK_COOLDOWN_MIN = int(os.getenv("UNLOCK_COOLDOWN_MIN", "15"))

# ---------------------------------------------------------------- deployment
DEMO_BASE_URL = os.getenv("DEMO_BASE_URL", "https://restaurant-ai-bot-n844.onrender.com").rstrip("/")
DEMO_EXPIRE_HOURS = int(os.getenv("DEMO_EXPIRE_HOURS", "72"))
PORT = int(os.getenv("PORT", "8080"))
# Turso (hosted libSQL) — replaces local SQLite so data survives redeploys
# on hosts with no persistent disk (e.g. Render free/starter plans).
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
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
                   "hero": "A table in the neighborhood.",
                   "sections": ["Menu", "Hours", "Location", "Order"]},
    "cafe": {"types": ["cafe"], "label": "cafe",
             "hero": "Coffee, and a place to sit.",
             "sections": ["Drinks", "Hours", "Location"]},
    "bakery": {"types": ["bakery"], "label": "bakery",
               "hero": "Warm from the oven.",
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

# Visual systems for generated demos. Each category maps to a family with its
# own color, type, hero, and offering layout — not one skin plus a tagline.
# Families: supper, cafe, bakery, chair, atelier, floor, clinic, practice,
# trade, counter, gallery, library, luxe.
_SERIF_DISPLAY = "Didot, 'Bodoni MT', 'Hoefler Text', 'Iowan Old Style', Palatino, Georgia, serif"
_SERIF_SOFT = "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Helvetica, Arial, sans-serif"
_SANS_GEO = "'Avenir Next', 'Century Gothic', Futura, 'Gill Sans', 'Trebuchet MS', sans-serif"
_SANS_COND = "'Avenir Next Condensed', 'Franklin Gothic Medium', 'Arial Narrow', Arial, sans-serif"

CATEGORY_THEMES = {
    "restaurant": {
        "family": "supper",
        "ink": "#14110e", "accent": "#c4a46a", "surface": "#efe6d6", "paper": "#faf6ee",
        "hero_bg": "#14110e", "hero_fg": "#f4ead8", "muted": "#6f675c",
        "display": _SERIF_DISPLAY, "body": _SANS,
        "cta": "Call for a table", "cta_ghost": "See the menu",
        "offer_kicker": "On the table", "visit_kicker": "Find the table",
        "atmosphere": "A neighborhood kitchen — seasonal plates, no fuss.",
        "hours": [("Tue – Thu", "17:00 – 22:00"), ("Fri – Sat", "17:00 – 23:00"),
                  ("Sunday", "17:00 – 21:00"), ("Monday", "Closed")],
    },
    "cafe": {
        "family": "cafe",
        "ink": "#2a2018", "accent": "#b56a3c", "surface": "#f6efe6", "paper": "#fffaf4",
        "hero_bg": "#f6efe6", "hero_fg": "#2a2018", "muted": "#7a6a5c",
        "display": _SERIF_SOFT, "body": _SANS,
        "cta": "Call the shop", "cta_ghost": "See the drinks",
        "offer_kicker": "On the board", "visit_kicker": "Come in",
        "atmosphere": "A quiet counter, a good cup, a place to sit.",
        "hours": [("Mon – Fri", "07:00 – 17:00"), ("Saturday", "08:00 – 17:00"),
                  ("Sunday", "08:00 – 15:00")],
    },
    "bakery": {
        "family": "bakery",
        "ink": "#3a2418", "accent": "#c47a4a", "surface": "#f8efe4", "paper": "#fff8f1",
        "hero_bg": "#f8efe4", "hero_fg": "#3a2418", "muted": "#8a6e5c",
        "display": _SERIF_SOFT, "body": _SANS,
        "cta": "Call to order", "cta_ghost": "See what's fresh",
        "offer_kicker": "In the case", "visit_kicker": "The window",
        "atmosphere": "Warm from the oven, gone by afternoon.",
        "hours": [("Tue – Sat", "07:00 – 15:00"), ("Sunday", "08:00 – 14:00"),
                  ("Monday", "Closed")],
    },
    "barber": {
        "family": "chair",
        "ink": "#0e1013", "accent": "#8ea0b3", "surface": "#eef1f4", "paper": "#f7f8fa",
        "hero_bg": "#0e1013", "hero_fg": "#eef1f4", "muted": "#5c6570",
        "display": _SANS_GEO, "body": _SANS,
        "cta": "Call for a chair", "cta_ghost": "See services",
        "offer_kicker": "The chair", "visit_kicker": "Walk in",
        "atmosphere": "Classic cuts. Hot towel. No gimmicks.",
        "hours": [("Tue – Fri", "09:00 – 19:00"), ("Saturday", "09:00 – 17:00"),
                  ("Sun – Mon", "Closed")],
    },
    "salon": {
        "family": "atelier",
        "ink": "#2a1e26", "accent": "#c492b0", "surface": "#f7f1f5", "paper": "#fffafc",
        "hero_bg": "#f7f1f5", "hero_fg": "#2a1e26", "muted": "#7a6874",
        "display": _SERIF_DISPLAY, "body": _SANS,
        "cta": "Book a visit", "cta_ghost": "See services",
        "offer_kicker": "The chair", "visit_kicker": "The studio",
        "atmosphere": "Color, cut, and the time to get it right.",
        "hours": [("Tue – Sat", "10:00 – 18:00"), ("Sun – Mon", "Closed")],
    },
    "auto": {
        "family": "trade",
        "ink": "#16181c", "accent": "#e07c3c", "surface": "#f1f2f4", "paper": "#fff",
        "hero_bg": "#16181c", "hero_fg": "#f1f2f4", "muted": "#5e646c",
        "display": _SANS_COND, "body": _SANS,
        "cta": "Call for an estimate", "cta_ghost": "See services",
        "offer_kicker": "In the bay", "visit_kicker": "The shop",
        "atmosphere": "Honest work. Fair prices. Same-day on most jobs.",
        "hours": [("Mon – Fri", "08:00 – 18:00"), ("Saturday", "08:00 – 14:00"),
                  ("Sunday", "Closed")],
    },
    "gym": {
        "family": "floor",
        "ink": "#0c0e10", "accent": "#7fd1a6", "surface": "#eef3f0", "paper": "#f7faf8",
        "hero_bg": "#0c0e10", "hero_fg": "#eef3f0", "muted": "#5a6560",
        "display": _SANS_COND, "body": _SANS,
        "cta": "Call the desk", "cta_ghost": "See classes",
        "offer_kicker": "On the floor", "visit_kicker": "Hours",
        "atmosphere": "Show up. That's the hard part.",
        "hours": [("Mon – Fri", "05:00 – 22:00"), ("Sat – Sun", "07:00 – 20:00")],
    },
    "florist": {
        "family": "atelier",
        "ink": "#1c2418", "accent": "#7a9a4a", "surface": "#f3f6ec", "paper": "#fbfcf7",
        "hero_bg": "#f3f6ec", "hero_fg": "#1c2418", "muted": "#66705c",
        "display": _SERIF_SOFT, "body": _SANS,
        "cta": "Call to order", "cta_ghost": "See arrangements",
        "offer_kicker": "In the shop", "visit_kicker": "Visit",
        "atmosphere": "Arrangements that say it better than words.",
        "hours": [("Tue – Sat", "09:00 – 17:00"), ("Sunday", "10:00 – 14:00"),
                  ("Monday", "Closed")],
    },
    "dentist": {
        "family": "clinic",
        "ink": "#1a2428", "accent": "#4aa8b0", "surface": "#f2f6f6", "paper": "#fff",
        "hero_bg": "#f2f6f6", "hero_fg": "#1a2428", "muted": "#5c6a6e",
        "display": _SANS, "body": _SANS,
        "cta": "Book an appointment", "cta_ghost": "See services",
        "offer_kicker": "Care", "visit_kicker": "The office",
        "atmosphere": "A practice that puts you at ease.",
        "hours": [("Mon – Thu", "08:00 – 17:00"), ("Friday", "08:00 – 14:00"),
                  ("Sat – Sun", "Closed")],
    },
    "lawyer": {
        "family": "practice",
        "ink": "#1a1914", "accent": "#b89b5e", "surface": "#f4f1ea", "paper": "#fbf9f4",
        "hero_bg": "#1a1914", "hero_fg": "#f4f1ea", "muted": "#6a6558",
        "display": _SERIF_DISPLAY, "body": _SERIF_SOFT,
        "cta": "Request a consult", "cta_ghost": "Practice areas",
        "offer_kicker": "Practice", "visit_kicker": "The office",
        "atmosphere": "Straight answers. Real advocacy.",
        "hours": [("Mon – Fri", "09:00 – 17:00"), ("Sat – Sun", "By appointment")],
    },
    "plumber": {
        "family": "trade",
        "ink": "#121820", "accent": "#4a8ec8", "surface": "#eef2f6", "paper": "#fff",
        "hero_bg": "#121820", "hero_fg": "#eef2f6", "muted": "#5a6570",
        "display": _SANS_COND, "body": _SANS,
        "cta": "Call now", "cta_ghost": "See services",
        "offer_kicker": "What we fix", "visit_kicker": "Service area",
        "atmosphere": "Fixed right the first time.",
        "hours": [("Mon – Fri", "07:00 – 18:00"), ("Saturday", "08:00 – 14:00"),
                  ("Emergency", "On call")],
    },
    "electrician": {
        "family": "trade",
        "ink": "#1a160e", "accent": "#e0b03a", "surface": "#f6f3ea", "paper": "#fffdf8",
        "hero_bg": "#1a160e", "hero_fg": "#f6f3ea", "muted": "#6a6458",
        "display": _SANS_COND, "body": _SANS,
        "cta": "Call now", "cta_ghost": "See services",
        "offer_kicker": "What we do", "visit_kicker": "Service area",
        "atmosphere": "Licensed, insured, on time.",
        "hours": [("Mon – Fri", "07:00 – 18:00"), ("Saturday", "08:00 – 14:00"),
                  ("Emergency", "On call")],
    },
    "roofer": {
        "family": "trade",
        "ink": "#1a1210", "accent": "#c0392b", "surface": "#f4f1ef", "paper": "#fff",
        "hero_bg": "#1a1210", "hero_fg": "#f4f1ef", "muted": "#6a5e5a",
        "display": _SANS_COND, "body": _SANS,
        "cta": "Call for an estimate", "cta_ghost": "See services",
        "offer_kicker": "What we do", "visit_kicker": "Service area",
        "atmosphere": "Built to take the weather.",
        "hours": [("Mon – Fri", "07:00 – 18:00"), ("Saturday", "08:00 – 14:00"),
                  ("Sunday", "Emergency only")],
    },
    "locksmith": {
        "family": "trade",
        "ink": "#161418", "accent": "#a89f6b", "surface": "#f3f2ee", "paper": "#fff",
        "hero_bg": "#161418", "hero_fg": "#f3f2ee", "muted": "#646058",
        "display": _SANS_GEO, "body": _SANS,
        "cta": "Call now", "cta_ghost": "See services",
        "offer_kicker": "What we do", "visit_kicker": "Service area",
        "atmosphere": "Locked out? Not for long.",
        "hours": [("Daily", "08:00 – 20:00"), ("Emergency", "24 / 7")],
    },
    "jewelry": {
        "family": "luxe",
        "ink": "#16110c", "accent": "#d4b46a", "surface": "#f4eee4", "paper": "#fbf7f0",
        "hero_bg": "#16110c", "hero_fg": "#f4eee4", "muted": "#6e6658",
        "display": _SERIF_DISPLAY, "body": _SANS,
        "cta": "Visit the shop", "cta_ghost": "See collections",
        "offer_kicker": "In the case", "visit_kicker": "The atelier",
        "atmosphere": "Pieces made to keep.",
        "hours": [("Tue – Sat", "11:00 – 18:00"), ("Sun – Mon", "By appointment")],
    },
    "tattoo": {
        "family": "floor",
        "ink": "#0c0c0e", "accent": "#9a6cff", "surface": "#f0eef4", "paper": "#f7f6fa",
        "hero_bg": "#0c0c0e", "hero_fg": "#f0eef4", "muted": "#6a6574",
        "display": _SANS_COND, "body": _SANS,
        "cta": "Book a session", "cta_ghost": "See the work",
        "offer_kicker": "The studio", "visit_kicker": "Walk-ins",
        "atmosphere": "Your idea, done right.",
        "hours": [("Tue – Sat", "12:00 – 20:00"), ("Sun – Mon", "Closed")],
    },
    "veterinary": {
        "family": "clinic",
        "ink": "#18241c", "accent": "#5aaa72", "surface": "#eef4f0", "paper": "#f7fbf8",
        "hero_bg": "#eef4f0", "hero_fg": "#18241c", "muted": "#5c6e62",
        "display": _SANS, "body": _SANS,
        "cta": "Book a visit", "cta_ghost": "See services",
        "offer_kicker": "Care", "visit_kicker": "The clinic",
        "atmosphere": "Care for the whole family.",
        "hours": [("Mon – Fri", "08:00 – 18:00"), ("Saturday", "08:00 – 14:00"),
                  ("Sunday", "Emergency only")],
    },
    "optician": {
        "family": "clinic",
        "ink": "#182028", "accent": "#4a96b4", "surface": "#eef3f6", "paper": "#fff",
        "hero_bg": "#eef3f6", "hero_fg": "#182028", "muted": "#5c6a74",
        "display": _SANS_GEO, "body": _SANS,
        "cta": "Book an exam", "cta_ghost": "See services",
        "offer_kicker": "In the shop", "visit_kicker": "Visit",
        "atmosphere": "See clearly. Look good doing it.",
        "hours": [("Mon – Fri", "09:00 – 18:00"), ("Saturday", "10:00 – 16:00"),
                  ("Sunday", "Closed")],
    },
    "dry_cleaning": {
        "family": "counter",
        "ink": "#182028", "accent": "#5aa8c4", "surface": "#eef4f7", "paper": "#fff",
        "hero_bg": "#eef4f7", "hero_fg": "#182028", "muted": "#5c6c74",
        "display": _SANS_GEO, "body": _SANS,
        "cta": "Call the counter", "cta_ghost": "See services",
        "offer_kicker": "At the counter", "visit_kicker": "Drop off",
        "atmosphere": "Fresh, pressed, ready.",
        "hours": [("Mon – Fri", "07:00 – 19:00"), ("Saturday", "08:00 – 16:00"),
                  ("Sunday", "Closed")],
    },
    "photo": {
        "family": "gallery",
        "ink": "#101012", "accent": "#c4a0d0", "surface": "#f2f0f4", "paper": "#faf8fb",
        "hero_bg": "#101012", "hero_fg": "#f2f0f4", "muted": "#6a6670",
        "display": _SERIF_DISPLAY, "body": _SANS,
        "cta": "Book a session", "cta_ghost": "See the work",
        "offer_kicker": "Sessions", "visit_kicker": "The studio",
        "atmosphere": "Moments worth keeping.",
        "hours": [("Tue – Sat", "10:00 – 18:00"), ("Sun – Mon", "By appointment")],
    },
    "accountant": {
        "family": "practice",
        "ink": "#141816", "accent": "#4f9d69", "surface": "#eef3f0", "paper": "#f7faf8",
        "hero_bg": "#141816", "hero_fg": "#eef3f0", "muted": "#5a6860",
        "display": _SERIF_DISPLAY, "body": _SANS,
        "cta": "Request a consult", "cta_ghost": "See services",
        "offer_kicker": "How we help", "visit_kicker": "The office",
        "atmosphere": "Numbers you can trust.",
        "hours": [("Mon – Fri", "09:00 – 17:00"), ("Sat – Sun", "By appointment")],
    },
    "estate_agent": {
        "family": "practice",
        "ink": "#1c1812", "accent": "#c98a3a", "surface": "#f4efe6", "paper": "#fbf7f0",
        "hero_bg": "#1c1812", "hero_fg": "#f4efe6", "muted": "#6e6658",
        "display": _SERIF_SOFT, "body": _SANS,
        "cta": "Talk to an agent", "cta_ghost": "See listings",
        "offer_kicker": "How we help", "visit_kicker": "The office",
        "atmosphere": "Local expertise, real results.",
        "hours": [("Mon – Sat", "09:00 – 18:00"), ("Sunday", "By appointment")],
    },
    "insurance": {
        "family": "practice",
        "ink": "#141820", "accent": "#4a90d9", "surface": "#eef2f7", "paper": "#f7f9fc",
        "hero_bg": "#141820", "hero_fg": "#eef2f7", "muted": "#5a6574",
        "display": _SANS, "body": _SANS,
        "cta": "Get a quote", "cta_ghost": "See coverage",
        "offer_kicker": "Coverage", "visit_kicker": "The office",
        "atmosphere": "Coverage that actually makes sense.",
        "hours": [("Mon – Fri", "09:00 – 17:00"), ("Sat – Sun", "Closed")],
    },
    "pet": {
        "family": "counter",
        "ink": "#241c14", "accent": "#d4924a", "surface": "#f6f0e8", "paper": "#fbf7f2",
        "hero_bg": "#f6f0e8", "hero_fg": "#241c14", "muted": "#6e6458",
        "display": _SERIF_SOFT, "body": _SANS,
        "cta": "Call the shop", "cta_ghost": "See services",
        "offer_kicker": "In the shop", "visit_kicker": "Visit",
        "atmosphere": "Everything your pet needs.",
        "hours": [("Mon – Sat", "09:00 – 19:00"), ("Sunday", "10:00 – 16:00")],
    },
    "hardware": {
        "family": "counter",
        "ink": "#1a1816", "accent": "#d67d3e", "surface": "#f3f1ee", "paper": "#faf9f7",
        "hero_bg": "#f3f1ee", "hero_fg": "#1a1816", "muted": "#6a6460",
        "display": _SANS_GEO, "body": _SANS,
        "cta": "Call the store", "cta_ghost": "See departments",
        "offer_kicker": "In the aisles", "visit_kicker": "Visit",
        "atmosphere": "If it's for the job, it's here.",
        "hours": [("Mon – Sat", "07:00 – 19:00"), ("Sunday", "09:00 – 16:00")],
    },
    "books": {
        "family": "library",
        "ink": "#1a1624", "accent": "#8f7bc4", "surface": "#f2eef6", "paper": "#faf8fc",
        "hero_bg": "#1a1624", "hero_fg": "#f2eef6", "muted": "#6a6478",
        "display": _SERIF_DISPLAY, "body": _SERIF_SOFT,
        "cta": "Call the shop", "cta_ghost": "Browse sections",
        "offer_kicker": "On the shelves", "visit_kicker": "The shop",
        "atmosphere": "Shelves worth getting lost in.",
        "hours": [("Mon – Sat", "10:00 – 20:00"), ("Sunday", "11:00 – 18:00")],
    },
}


def theme_for(category: str) -> dict:
    """Visual tokens for a generated demo. Unknown categories use restaurant."""
    return CATEGORY_THEMES.get(category, CATEGORY_THEMES["restaurant"])


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
