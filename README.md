# Restaurant AI Bot — Houston Lead Gen + Website Generator

A Telegram-controlled bot system that:
1. Searches Houston for restaurants without websites or with outdated sites
2. Generates beautiful custom restaurant websites with takeout ordering
3. Emails owners with protected demo links (time-limited, anti-copy)
4. Tracks leads and responses

## Architecture

```
telegram bot → scanner (Google Places) → generator (site builder) → email outreach → tracking
```

## Setup

```bash
pip install -r requirements.txt
```

### Environment Variables (.env)
```
TELEGRAM_BOT_TOKEN=            # Bot token from BotFather
GOOGLE_PLACES_API_KEY=         # Google Places API key
RESEND_API_KEY=                # Resend.com for email delivery (free tier)
ADMIN_USER_IDS=8057854284      # Telegram user IDs
DATABASE_URL=sqlite:///restaurant-bot.db
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + menu |
| `/scan` | Start scanning Houston restaurants |
| `/scan [area]` | Scan specific Houston area (e.g., "/scan Heights") |
| `/leads` | Show recent qualified leads |
| `/generate [lead_id]` | Generate website for a lead |
| `/preview [lead_id]` | Get protected preview link |
| `/email [lead_id]` | Send outreach email to owner |
| `/status` | Bot stats |

## Protection System
- Demo sites served via server (not static files)
- Time-limited links (expire after X days)
- Watermark overlay on demo
- CSS user-select: none, -webkit-user-drag: none
- Right-click disabled
- Periodic overlay checks
- Links generated with unique tokens

## Deployment
Deploy on Railway with Dockerfile.
