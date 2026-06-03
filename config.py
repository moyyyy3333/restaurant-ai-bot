import os
from dotenv import load_dotenv
load_dotenv()

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_USER_IDS = [int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "8057854284").split(",") if x.strip()]

# === Google Places API ===
GOOGLE_PLACES_API_KEY = "GOOGLE_PLACES_API_KEY_REMOVED"

# === Email (Resend) ===
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = "neo@restaurant.ai"  # Need to verify domain in Resend

# === Database ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///restaurant-bot.db")

# === Demo Server ===
DEMO_BASE_URL = os.getenv("DEMO_BASE_URL", "http://localhost:8080")
DEMO_EXPIRE_HOURS = int(os.getenv("DEMO_EXPIRE_HOURS", "72"))  # 3 days

# === Scanner ===
HOUSTON_AREAS = [
    "Heights", "Montrose", "Midtown", "Downtown Houston",
    "Rice Village", "River Oaks", "Upper Kirby", "Museum District",
    "EaDo", "East Downtown", "Washington Ave", "Galleria",
    "Uptown", "Memorial", "Energy Corridor", "Sugar Land",
    "Katy", "Pearland", "Missouri City", "The Woodlands",
    "Cypress", "Klein", "Tomball", "Kingwood"
]
SCAN_RADIUS_METERS = 1600  # ~1 mile
