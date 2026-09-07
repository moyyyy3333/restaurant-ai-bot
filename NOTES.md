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
