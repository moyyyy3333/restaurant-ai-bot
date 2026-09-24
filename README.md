# Restaurant AI Bot

Restaurant AI Bot discovers independent local businesses with no verified
website, builds private sample sites, and sends compliant outreach. One Render
service runs both the stdlib HTTP server and Telegram operator bot through
`run.py`; Turso stores production data.

## Local setup

1. Install Python 3 dependencies:
   `python3 -m pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill only the providers you use.
3. Start both processes with `python3 run.py`, or only the web server with
   `python3 server.py`.
4. Open `http://localhost:8080/health`.

Never commit `.env`. Local SQLite is used when Turso is not configured.

## Stripe Checkout ($99 claim + Care)

The marketing homepage and every `/demo/<token>` page start Stripe Checkout
for a one-time **$99** site claim. Optional Care is **$29/mo** or **$249/yr**.

Required for live Checkout (otherwise `/claim/start` opens a visible stub):

| Variable | Purpose |
| --- | --- |
| `STRIPE_SECRET_KEY` | Creates Checkout Sessions (`sk_live_…` or `sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | Verifies `POST /webhook/stripe` so paid sessions mark the lead claimed |
| `STRIPE_PUBLISHABLE_KEY` | Optional; not required for server-side Checkout |
| `STRIPE_PRICE_BUILD` | Optional Price ID for the $99 one-time claim |
| `STRIPE_PRICE_CARE_MONTHLY` | Optional Price ID for Care $29/mo |
| `STRIPE_PRICE_CARE_YEARLY` | Optional Price ID for Care $249/yr |
| `PUBLIC_BASE_URL` / `DEMO_BASE_URL` | Success + cancel URLs (cancel returns to `/`) |
| `REPLY_TO` | Preview-request mailto on the landing form |

If a Price ID is empty, Checkout uses inline `price_data` in USD. The $99
line is named **Local Web Studio — site claim**.

Public buy path (no ops token):

- `POST /api/claim/checkout` — JSON `{care, t, business}` or an HTML form; JSON returns `{url}`, form POSTs 302 to Stripe
- `GET /claim/start?care=none|monthly|yearly&t=<demo-token>` — same session, then 302
- `GET /claim/success?session_id=…` — confirmation + reply to dealermatt72@me.com
- `GET /claim/cancel` — no charge; link back to the landing
- `POST /webhook/stripe` — `checkout.session.completed` and Care lifecycle events

`care` is `none` (default), `monthly`, or `yearly`. A demo token or lead id
is attached as Stripe metadata when present; the landing can claim without one.

## Production

Render is the only public runtime. The service command is defined in the
`Procfile` as `python3 run.py`. Set `PUBLIC_BASE_URL` to the Render service URL;
demo and unsubscribe links inherit it. Render startup fails loudly if either
link points to localhost.

Pushes to `main` trigger `.github/workflows/deploy.yml`, which deploys Render
and verifies `/health`. The daily workflow calls `/pipeline/run` with
`X-Pipeline-Token`. A linked Vercel project also deploys `main` to
`https://restaurant-ai-bot-two.vercel.app/`.

After deploy, click these on **both** hosts (Vercel is the buyer-facing
landing; Render is the long-running service):

- `https://restaurant-ai-bot-two.vercel.app/` — primary CTA **Claim for $99**
- `https://restaurant-ai-bot-two.vercel.app/api/claim/checkout` — should 302 to Stripe or the stub
- `https://restaurant-ai-bot-two.vercel.app/claim/start` — same
- `https://restaurant-ai-bot-two.vercel.app/claim/success` — confirmation + dealermatt72@me.com
- `https://restaurant-ai-bot-n844.onrender.com/` — same landing + buy path
- `https://restaurant-ai-bot-n844.onrender.com/demo/<token>` — personalized demo + claim bar
- Stripe webhook endpoint: `https://restaurant-ai-bot-n844.onrender.com/webhook/stripe`
  (also add the Vercel host if Checkout success stays on Vercel)

## Pre-deploy check

Run:

```sh
make check
```

It runs the full unit, quality, and website-accuracy suites, executes every
pipeline stage in zero-send mode, starts an isolated local server, and requires
`/health` to answer successfully within one second.

To exercise metered discovery against the configured database without sending:

```sh
DAILY_SEND_LIMIT=0 python3 scripts/pipeline_dry_run.py --scan-budget 12
```

Production can be exercised safely by sending `X-Pipeline-Dry-Run: true`
alongside the required `X-Pipeline-Token`; this forces an effective send limit
of zero for that request without changing Render configuration. Manual GitHub
workflow runs also set `X-Pipeline-Scan-Budget: 1` to keep the synchronous
end-to-end production probe bounded, plus `X-Pipeline-Scan-Results: 1` so that
area expands to only one business lookup and `X-Pipeline-Work-Limit: 1` so
each downstream backlog stage processes at most one lead.

API-provider daily ceilings are configured with the `*_DAILY_BUDGET` variables
in `.env.example`; shared counters are stored in `ops_meta`.
