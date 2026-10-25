# restaurant-ai-bot — Finish it and make it sell

Paste everything below this line into Cursor (Agent mode, Composer) or grokbot as the opening message. It is written from a read of the actual repo on 2026-09-07, so every fact in here is current. Do not re-derive the plan; execute it.

---

You are the lead engineer on `restaurant-ai-bot` (repo root is this folder, remote `github.com/moyyyy3333/restaurant-ai-bot`). It is a Python 3 product that finds independent restaurants and local businesses with no real website, builds them a sample site, emails/SMSes them the preview, and sells them the site. Your job is to take it from "mostly built" to "money comes in without me touching anything." Work autonomously through the phases below in order. Do not stop to ask permission between tasks. The ONLY reason to pause and ask me is when you need a secret or an account I have to create (Stripe keys, a domain, a Twilio number). Everything else, decide and ship.

## Ground truth — what already exists (do not rebuild these)

- `server.py` — stdlib HTTP server (no Flask). Routes: `/` marketing home, `/stats`, `/health`, `/demo/<token>` (expiring sample sites), `/board` + `/ops` (token-gated operator dashboards, `?k=PIPELINE_TOKEN`), `/claim/start|stub|success|cancel`, `/unsubscribe`, `/webhook/resend`, `/webhook/stripe`, `/pipeline/run` (POST, `X-Pipeline-Token`), `/api/board`, `/api/ops`, `/api/lead`, `/api/ops/meta`, `/api/claim/checkout`, `/api/pipeline`.
- `run.py` — supervises `server.py` + `bot.py` as one Render service. `Procfile: web: python3 run.py`.
- `bot.py` — Telegram admin bot. Commands: unlock lock setemail start help board cities scan leads lead generate preview propose stats.
- `scanner/scanner.py` — LocationIQ (OSM) + Google Places (New) discovery; `check_website()` returns tri-state `has_site | social_only | none | unknown` with name-match and liveness checks. `scanner/email_finder.py` — email discovery (Hunter/Apollo keys are wired but NOT set).
- `generator.py` (1000 lines) — category-aware single-file HTML sites; `profiles.py` cuisine/theme inference; `menu_enrich.py` fail-closed real-menu scraping (JSON-LD, partner menus, OCR); `writer.py` LLM copy (Anthropic/OpenAI/DeepSeek/Hermes — NO key is set, so it falls back).
- `emailer.py` — Resend email (CAN-SPAM postal address enforced, refuses to send without it) + Twilio SMS (keys NOT set). One proposal email only; no follow-ups.
- `claim.py` — Stripe Checkout via raw HTTP (no SDK). $99 one-time build + Care $29/mo or $249/yr. Falls back to a visible "stub" page because STRIPE_SECRET_KEY is NOT set. `/webhook/stripe` only marks the lead `claimed` — nothing is delivered after payment.
- `landing.py` — marketing homepage. The "Get free preview" form posts to `mailto:`. There is no self-serve flow.
- `db.py` — libSQL/Turso (hosted) with local SQLite fallback. Tables: businesses, leads, demo_sites, claims, email_log, suppression, auth, meta. Lead statuses: new, site_generated, proposed, replied, claimed, sold, dead.
- `ops.py`, `ops.html`, `board.html` — operator dashboards.
- `tests/` — test_emailer, test_menu_enrich, test_ops, test_server, test_site_quality, test_website_accuracy. Run with `python3 -m unittest discover tests` (and `python3 -m tests.test_site_quality`, `python3 -m tests.test_website_accuracy`).
- `SPEC_accuracy_and_quality.md` — the quality bar for generated sites and the "never say 'no website' unless confirmed" rule. Treat it as law.
- Deploy: GitHub Actions `deploy.yml` (push to main → Render deploy → health check at `https://restaurant-ai-bot-n844.onrender.com/`), `pipeline.yml` (daily 14:17 UTC POST to `/pipeline/run`). There is also a Vercel project linked (`.vercel/project.json`) — that split is a liability.
- `.env` exists locally with Telegram, Turso, LocationIQ, Google Places, Resend, PIPELINE_TOKEN set. `DEMO_BASE_URL` and `UNSUBSCRIBE_BASE` are still `localhost:8080`. Stripe, Twilio, Hunter, Apollo, and all LLM keys are EMPTY. Never print, commit, or overwrite `.env`; only add new keys to `.env.example` and tell me what to fill in.
- Pricing in code: BUILD $99 one-time, CARE $29/mo or $249/yr. Keep those. (`OUTREACH.md` mentions $299; ignore it.)

## Non-negotiable rules

1. Truthfulness gate stays. Never email or text anyone a "you have no website" pitch unless `website_status` is `none` or `social_only`. `unknown` waits. Never invent hours, menu items, prices, reviews, or photos on a generated site — omit the section instead.
2. Keep the server stdlib-only. No Flask/FastAPI/Django. `requirements.txt` is `python-telegram-bot`, `python-dotenv`, `libsql-experimental`; add a dependency only if there is no reasonable stdlib way.
3. Every phase ends with: all tests green, new tests for new behavior, one commit per logical change with a clear message, and a short report to me (what shipped, what env vars I must set, what URL to click to verify).
4. Do not break Render. `run.py` must keep both processes alive. `/health` must return 200 in under 1s.
5. Anything that costs money per call (Google Places, Hunter, Apollo, LLM, Twilio) gets a per-day budget in `config.py` and a counter in `meta`.
6. CAN-SPAM / TCPA: postal address in every email, working one-click unsubscribe, suppression list honored everywhere, SMS only to businesses (not consumers), STOP handling on inbound SMS, no sends between 9pm and 8am recipient local time.

## Phase 0 — Make what exists actually run in production (do this first, today)

- Run the whole test suite. Fix anything red before touching features.
- Consolidate on Render as the single deployment. Remove the Vercel wiring (`.vercel/`, any Vercel-specific branches in `server.py`/`db.py`) unless there is a reason to keep it; if you keep it, make it a documented mirror, not a second source of truth. One public base URL.
- `DEMO_BASE_URL` / `UNSUBSCRIBE_BASE` must resolve from env on Render to the public URL; add a startup assertion that logs loudly if either is `localhost` in production.
- Verify the daily pipeline end to end against the live DB with `DAILY_SEND_LIMIT=0` (scan → site → email-find → would-send) and print a dry-run report. Fix whatever breaks.
- Add `make check` (or `scripts/check.sh`) that runs tests + a dry-run pipeline + hits `/health`. This is what I run before trusting a deploy.
- Report: the public URL, `/ops` link with key placeholder, and any keys still missing.

## Phase 1 — Real checkout on the demo page itself

Right now the only way to pay is from the operator ops board. The buyer must be able to pay from the preview they were emailed.

- On every `/demo/<token>` page inject a slim sticky bar (mobile-first, non-intrusive, respects the site's theme): "This is a preview built for {Business}. Make it yours — $99 one-time, optional Care $29/mo." Buttons: "Claim this site" → `/claim/start?t={token}&care=none`, and a "with Care" variant. Add a tiny "What you get" expander (hosting, mobile, Google Maps, click-to-call, edits for 30 days, live in 48h).
- Wire live Stripe: read `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, optional `STRIPE_PRICE_*`. When set, no stub anywhere. Checkout collects email + phone. Metadata carries `lead_id`, `demo_token`, `care_plan`.
- `/claim/success` becomes a real confirmation page: what happens next, a link to the onboarding form (Phase 2), and "text us" click-to-SMS.
- Webhook: `checkout.session.completed` → `mark_claimed(status="paid")`, extend `demo_expires_at` to never, notify me on Telegram immediately ("PAID $99 — {Business}, {city}, {email}"), send the buyer a receipt/welcome email via Resend.
- Handle `checkout.session.expired`, `invoice.paid` (Care renewals), `customer.subscription.deleted` (Care cancelled → flag lead).
- Tests: signed webhook fixture, idempotency (same event twice → one claim), success page renders without a session.
- Ask me for: Stripe live keys + webhook secret. Give me the exact webhook URL and event list to paste into the Stripe dashboard.

## Phase 2 — Fulfillment: paid means live, with zero manual work

- On paid: promote the demo to a permanent site. Copy `demo_sites` row into a `sites` table (slug, lead_id, html, custom_domain, status, published_at). Serve at `/s/<slug>` with no expiry and proper caching headers, `robots` allowed, sitemap entry.
- Custom domain: support `sites.custom_domain`. Implement the cheapest reliable path: Render custom domains via the Render API (`RENDER_API_KEY`, `RENDER_SERVICE_ID` already exist as GitHub secrets), with the server routing on `Host` header → slug. Fall back to a subdomain `{slug}.{PUBLIC_SITES_DOMAIN}` if the buyer has no domain. Document the DNS instructions the buyer gets in the welcome email.
- Onboarding form at `/onboard/<claim_token>` (token emailed on payment): confirm/correct hours, phone, address, upload logo + up to 6 photos, paste menu or upload a menu photo (route through `menu_enrich` OCR), choose domain option, pick primary color. On submit → regenerate the site with the corrections → republish → email "your site is updated" with the live link. Store uploads in the DB as blobs or on Render disk under `DEMO_DIR`; keep each image under 400KB (resize with stdlib-free approach or a single small dependency like Pillow if needed).
- Edit requests after launch: a `/edit/<claim_token>` page with a free-text box that files a `site_edits` row and pings me on Telegram. Care subscribers get it unlimited; non-Care gets 30 days.
- Telegram: `/sites`, `/site <slug>`, `/publish <lead_id>`, `/domain <slug> example.com`.
- Tests: paid → site row exists and `/s/<slug>` serves; onboarding submit regenerates without inventing data; host-header routing.

## Phase 3 — Outreach that closes without me

- Email discovery: chain Google Places website → scrape contact page/mailto → Hunter → Apollo, in that order, stopping at first verified hit. Budget-capped. Store `email_source` and `email_confidence`.
- Sequence, not a single email. Day 0 proposal (exists), Day 3 "did you see it?" with a screenshot of their preview (generate a PNG via a headless render if available on Render, else a static "preview card" HTML→image is fine to skip; text-only follow-up is acceptable), Day 7 last-call with a deadline tied to `demo_expires_at`. Stop the sequence on reply, click, claim, unsubscribe, or bounce. Track in a `sequences` table.
- SMS: when a business has a phone and no email, send the SMS variant (Twilio). Handle inbound SMS webhook (`/webhook/twilio`): STOP → suppress; anything else → mark `replied`, notify me, auto-reply once with the preview link.
- Reply handling: `/webhook/resend` inbound already flips to `replied`. Add an auto-acknowledge that includes the claim link, and a Telegram alert with the reply text so I can jump in from my phone.
- Demo view tracking already bumps `views`; add "viewed but not claimed after 48h" → SMS nudge if phone exists.
- Raise `DAILY_SEND_LIMIT` to 40 and make it env-tunable per city. Add per-domain and per-hour send throttles. Warm the Resend domain: start at 15/day, +10 every 3 days up to the cap, automatically.
- Ask me for: Twilio number + keys, Hunter and Apollo keys (free tiers are fine to start).

## Phase 4 — Self-serve funnel on the homepage

Replace the `mailto:` form on `/` with a real flow so businesses that find the site can buy without outreach.

- Form: business name + city (or Google Maps link). POST `/api/preview` → Google Places lookup → create lead + demo site synchronously if under 20s, otherwise return a job id and poll. Show the preview inline with the same claim bar as Phase 1.
- Rate-limit by IP, honeypot field, cap at 20 previews/day until I raise it.
- Add a `source` column on leads (`outreach` vs `inbound`) and show conversion by source on `/ops`.
- Homepage copy: lead with the outcome ("A real website for your restaurant, live in 48 hours, $99"), show 3 real generated examples (pick the best from `demos/`), one pricing block, FAQ (domain, edits, cancel anytime on Care). No stock-photo hero; use a generated-site screenshot or a plain typographic hero.

## Phase 5 — Site quality to the SPEC bar

- Generate 6 sites across categories (restaurant, coffee, taqueria, salon, auto repair, gym) from real leads in the DB, render them headless, and look at them. Fix everything that reads as a template fill. Hold to `SPEC_accuracy_and_quality.md` Part 2: fluid type scale, asymmetric hero, menu with leader dots, real hours table only when hours are confirmed, sticky click-to-call on mobile, AA contrast, `LocalBusiness` JSON-LD, print stylesheet, no web-font blocking, single inline stylesheet, Lighthouse mobile 95+.
- Photos: use Google Places photos (we have the key; attribution required) when the place has them; otherwise no photo block. Never a stock image, never a fake frame.
- Copy: wire one LLM provider (I will set `ANTHROPIC_API_KEY`) for the hero line and about paragraph only, with `writer.py`'s JSON contract. If the key is missing, fall back to the current deterministic copy — never a blank.
- `test_site_quality.py` must cover each new guarantee.

## Phase 6 — Ops so I can run this from my phone

- Telegram digest at 9:30am Houston: leads found, sites built, emails/SMS sent, views, replies, paid, MRR, and anything that errored. Immediate pings for: reply, payment, edit request, pipeline failure.
- `/ops`: add funnel numbers (found → verified no-site → sent → viewed → replied → paid), revenue (one-time + MRR), and a "needs me" list (replies unanswered > 2h, edit requests open, domains pending DNS).
- A `RUNBOOK.md`: how to deploy, rotate keys, add a city, change pricing, handle a refund, what each webhook does.

## How to work

- Start by printing a one-screen plan for the current phase, then execute it. Do not re-plan the whole project.
- Read the file before editing it. Prefer small, surgical diffs over rewrites; `generator.py` and `server.py` are the heart and must stay readable.
- When a decision is reversible, make it and move on. When it is not (schema, pricing, domains), say what you chose and why in the commit message.
- After each phase, give me a short plain-text report: what works now, exact env vars to add (name only), exact URLs to test, and the next phase you are starting. No bold formatting in reports.

Begin with Phase 0 now.
