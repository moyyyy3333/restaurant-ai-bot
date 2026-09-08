# Shared findings log

Append with a date and your name. Dead ends are as valuable as wins — the
other agent can't see your session.

## 2026-09-07 — grok (ops Prospect Board CM fold-in)

- PR #11 `/ops` already had the cream/orange shell, Focus, Rhythm, Waves,
  Claim column, and Turso refresh. The live gaps vs the CM screenshot were
  header Reload/Pop out, the orange Quick Note box (Copy for Claude/CoS +
  PIPELINE/RESEARCH/IDEA chips), Auto-prep ON · 9 AM CT, and Focus title
  using a middle dot (`Vertical • Territory`).
- Quick Note is an operator scratch pad persisted in `ops_meta.quick_note`.
  Tag chips prepend into the textarea; they do not write fake business facts.
- "Re-run today's prep" stamps `last_prep_at` and reloads Turso counts. It
  does **not** call `/pipeline/run` — that would spend shared LocationIQ /
  Google Places budget and can send. Keep pipeline runs on `/board` or the
  GH Action (cron `17 14 * * *` ≈ 9:17 AM CT).
- Weekly rotation labels are now Restaurant · Cafe · Trades · Salon · Auto ·
  Other (Foundry Growth buckets). Other is a catch-all card, not a weekday.
  HVAC/Pool are still not live categories — don't invent scanner types.
- Demo CTA chip on each row: Order (food) · Book (salon/appointments) ·
  Quote (trades/auto) · Call (else). Focus one-liner:
  `{city} none-site locals — Order for food, Book/Quote/Call for trades.`
- Claim strip copy: `$99 builds it. Care keeps it live.` Stripe checkout
  path and the Claim column stay.

## 2026-09-07 — claude

- **All 402 leads have a demo site; none have an email.** The outreach funnel
  has never sent a message. `pipeline.run_daily` reports `emails_found: 0`.
- **Hunter/Apollo can't fix that.** `scanner/email_finder.py:81` needs a domain
  from the business website. Miami `website_status`: none 138, unknown 9,
  has_site 1. So domain-based lookup applies to ~3% of leads. Hunter key is
  wired anyway (budget 8/day) but don't build around it.
- **Overpass API (OpenStreetMap) is free** — no key, no account, no quota.
  One Miami query returned 2,143 POIs, of which 135 had a phone and no
  website, 121 not already in our DB. This is the same underlying data
  LocationIQ resells. Endpoint: `https://overpass-api.de/api/interpreter`,
  POST `data=<QL>`. Coverage is volunteer-driven, so Brickell/South Beach are
  well mapped and Hialeah/Kendall are thin — don't read counts as truth.
- Backfilled 11 Miami lead phones from OSM at zero API cost (11 → 22 with
  phone). Matched on normalized name; crude, fine at this size, will produce
  false positives at scale.
- **Google Places already returned no phone for most leads** — 137/148 Miami
  businesses genuinely have none stored, and the data isn't hiding in the
  `businesses` table either. Re-enriching costs ~$0.032/call and won't
  necessarily find one.
- Budgets are shared single rows and were both exhausted by ~17:00 UTC.
  Use `scripts/coord.py budget` to reserve a slice first.

## 2026-09-07 (later) — claude

- **Scope correction from Matt: this is for ANY local business without a
  website, not just restaurants.** Acted on it:
  - `config.BUSINESS_CATEGORIES` 26 → 29 (added `pool`, `hvac`, `lawn` — the
    trades on the Treasure Coast board that the backend couldn't generate for).
  - Added `treasure-coast` to `config.CITIES` (Port St. Lucie, Fort Pierce,
    Stuart, Vero Beach, Jensen Beach, Palm City, Sebastian).
  - `scripts/free_leads.py` queries ~60 OSM categories: trades, salons, auto,
    clinics, retail, offices — not just food.
- **Chain filtering was broken and let franchises into the lead list.**
  `scanner.py:389` did `name.lower() in CHAIN_NAMES` (exact match), so
  "Subway #4471", "CVS Pharmacy" and "Cracker Barrel" all passed as leads.
  Fixed at the root: `config.is_chain()` does substring matching, list grown
  22 → ~120, and both scanner.py and free_leads.py call it. Anyone adding a
  new lead source should call `config.is_chain()` too.
- **Free lead yield, no API spend** (`scripts/free_leads.py <city>`):
  - miami: 234 businesses with phone + no website, 222 new. Broad mix —
    restaurant 58, clothes 22, convenience 13, furniture 13, pharmacy 8,
    hairdresser 8, gym 8, jewelry 6.
  - treasure-coast: only 11. **OSM coverage there is thin** — it's a lower
    density area with fewer mappers. Treasure Coast will need paid Google /
    LocationIQ calls to build a real list; Miami does not.
- Nothing inserted into the DB yet. `--insert` dedupes on normalized name AND
  last-10-digits of phone (OSM rows have no google_place_id).
- **Resend is now Pro**, and a new full-access API key is on Render.
  `FROM_EMAIL` moved to `hello@outreach.foundrydesk.vip`.
  `onboarding@resend.dev` only ever delivers to your own address, so outreach
  from it would have silently failed even on a paid plan.
- Added `outreach.foundrydesk.vip` to *our* Resend team rather than fighting
  over `mail.foundrydesk.vip` (which lives in the builder's team). Its 3 DNS
  records are NOT in cPanel yet — `scripts/dns_add.py` writes them via cPanel
  UAPI once a cPanel API token exists. Until then the domain is unverified
  and sending will fail.

## 2026-09-07 (evening) — claude

- `outreach.foundrydesk.vip` DNS is **done** in cPanel (3 records, no dupes,
  builder's `mail.foundrydesk.vip` untouched). Published DKIM matches Resend's
  expected value byte-for-byte (218 chars). Domain still shows `pending` —
  that is Resend/SES resolver lag, not a records problem. Re-trigger with:
  `curl -X POST https://api.resend.com/domains/<id>/verify -H "Authorization: Bearer $RESEND_API_KEY"`
  Domain id: 7388a870-1a34-408b-bcba-ce84d7133a52
- **cPanel API tokens are NOT available on this Namecheap plan.** "Manage API
  Tokens" appears in the sidebar but `security/api_tokens/index.html` 404s and
  the link does not navigate. So `scripts/dns_add.py` cannot be used against
  server229 — DNS still needs an SSO'd browser session via
  ap.www.namecheap.com > Hosting List > GO TO CPANEL. This is the strongest
  argument for moving DNS to Cloudflare, whose API tokens do work.
- **Sending chain is proven**: live email sent via Resend from the verified
  `fitnessprotocol.store` (id 9247330d). Pro plan, key, and delivery all work.
  `onboarding@resend.dev` only delivers to your own address — never use it for
  outreach, it fails silently.
- Free lead insert done: **596 leads total, 267 with phone** (was 402 / 22).
  194 new Miami businesses from OSM at zero API cost, cross-industry.
  195 leads still need demo sites generated.
