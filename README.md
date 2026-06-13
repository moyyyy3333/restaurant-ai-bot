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

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/restaurant-ai-bot?referralCode=moyyyy3333)

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
| `/scan [area]` | Scan specific Houston area (e.g., `/scan Heights`) |
| `/leads` | Show recent qualified leads |
| `/lead [id]` | Show lead details |
| `/generate [lead_id]` | Generate website for a lead |
| `/preview [lead_id]` | Get protected preview link |
| `/email [lead_id]` | Send outreach email to owner |
| `/sms [id]` | Send SMS with demo link (Twilio) |
| `/smscheck` | Check SMS replies |
| `/status` | Bot statistics |
| `/pipeline` | **Run full automation pipeline** (scan → generate → email) |
| `/scanall` | **Scan all remaining unscanned areas** |
| `/genall` | **Generate sites for all leads without one** |
| `/emailall` | **Email all leads with sites but no contact yet** |

## Pipeline Automation

The bot now includes a fully autonomous pipeline (`pipeline.py`) that can be triggered via:

- **Telegram:** `/pipeline`
- **Cron:** `cd /app && python pipeline.py`
- **Railway cron:** Can be configured to run every 6 hours

The pipeline runs all stages automatically:
1. **Scan** — finds next unscanned area and discovers restaurants without websites
2. **Generate** — builds custom restaurant sites for any new leads
3. **Email** — sends outreach to leads with generated sites

### Webhook Endpoints (server.py)

| Endpoint | Purpose |
|----------|---------|
| `POST /webhook/resend` | Detects YES replies from incoming emails |
| `POST /webhook/twilio` | Detects YES replies from SMS |
| `POST /webhook/stripe` | Processes payment confirmations ($299) |
| `GET /buy/<lead_id>` | Customer checkout page with Stripe payment link |

## Protection System
- Demo sites served via server (not static files)
- Time-limited links (expire after X days)
- Watermark overlay on demo
- CSS user-select: none, -webkit-user-drag: none
- Right-click disabled
- Periodic overlay checks
- Links generated with unique tokens

## Deployment
Deploy on Railway with the button above or use the Dockerfile directly.

```bash
# Or deploy manually:
railway up
```

### Required Environment Variables
| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `GOOGLE_PLACES_API_KEY` | Google Places API key |
| `RESEND_API_KEY` | Resend.com API key for email |
| `ADMIN_USER_IDS` | Your Telegram user ID(s) |
| `DEMO_BASE_URL` | Public URL of your demo server |
