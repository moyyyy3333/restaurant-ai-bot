# Spec: make the bot truthful about websites, and make the sites good

Written 2026-09-05 after the founder reported two faults:
1. "It says it found a restaurant without a website, but that isn't accurate."
2. "The websites it builds are trash — I want Fable-level."

## Part 1 — "no website" must mean CONFIRMED, not UNKNOWN

### What was actually wrong (read from the code, not guessed)
- `classify_website("")` returned `none`. An empty URL means *no data source
  carried one*, which is not the same as the business having no website.
- `google_enrich()` sent `textQuery = "{name}, {address}"`, took `places[0]`
  blindly, and never checked the result was the same business. A wrong match
  imported a wrong (or absent) website.
- On no key / no match / HTTP failure it returned `{}`, and the lead silently
  kept its optimistic `none`.
- `verify_website()` returned `""` for BOTH "confirmed clean" and
  "inconclusive", and its own docstring told callers to treat that as
  "safe to proceed".
- Nothing ever checked whether a listed URL actually resolves, so a dead or
  parked domain counted as "has a website" and a live site that neither OSM
  nor Google listed counted as "no website".

### Rules now
- `website_status` is one of: `has_site` | `social_only` | `none` | `unknown`.
- `none` may ONLY be set when a lookup actually succeeded, matched the
  business, and returned no usable URL. Every failure path yields `unknown`.
- A Google match is accepted only if the returned display name overlaps the
  queried name (normalised token overlap >= 0.6). Otherwise: `unknown`.
- Any candidate URL is liveness-checked. Dead, parked, or non-2xx/3xx ->
  not a real site.
- **Outreach may only target `none` or `social_only`.** `unknown` is never
  pitched; it goes back to the queue for re-check.

### Check
`python3 -m tests.test_website_accuracy` — asserts the tri-state table above.

## Part 2 — site quality

### Bar
The generated page should look like a small studio built it on purpose, not a
template fill. Concretely:
- One typographic system with a fluid scale and real hierarchy; headings and
  body sized off a ratio, not ad-hoc pixels.
- Editorial layout: an asymmetric hero, a menu that reads as a menu with
  leader dots and aligned prices, a real hours table.
- Sticky click-to-call on mobile — the single highest-value action for a
  local business.
- Accessible by construction: semantic landmarks, visible focus rings, AA
  contrast, reduced-motion respected.
- Fast: no blocking web fonts, no frameworks, single inline stylesheet.
- `LocalBusiness` JSON-LD so the page is machine-readable for search.
- Print stylesheet (people print menus).

### Check
`python3 -m tests.test_site_quality` — asserts the generated HTML contains the
structural and accessibility guarantees above.
