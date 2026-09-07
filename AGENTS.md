# Working agreement: Claude + Grok Bot

Two agents share one Turso database, one repo, one Render service, and one set
of daily API budgets. Nothing here is enforced by the platform — it works only
because both sides follow it. Read this before touching anything.

## 1. Take a lease before you work a city

```sh
python3 scripts/coord.py claim miami --owner claude --minutes 90 && ...work...
python3 scripts/coord.py release miami --owner claude
```

`claim` exits non-zero if someone else holds it, so it chains with `&&`.
Leases auto-expire, so a crashed agent never blocks the other permanently —
pick a duration you'll actually finish inside rather than a huge one.
`coord.py status` shows who holds what.

Default split: **Grok Bot owns houston. Claude owns miami.** Austin is
unclaimed; take a lease before starting it.

## 2. Reserve your slice of the API budget

The budget counters (`budget:<api>:<date>`) are single shared rows. Whoever
runs first spends the whole day — this already happened on 2026-09-07, when
LocationIQ (30) and Google Places (50) were exhausted before the second agent
ran at all.

```sh
python3 scripts/coord.py budget google_places --owner claude --cap 50 --share 0.5 --amount 20
```

This is advisory and additive: `db.consume_daily_budget` still enforces the
real ceiling. It only stops one agent from eating the other's half. Check it
*before* a scan, not after.

## 3. Never overwrite the other agent's data

- Fill empty fields; don't replace non-empty ones. Re-read the row immediately
  before writing — the preview you built five minutes ago may be stale.
- `businesses.google_place_id` is UNIQUE and catches duplicate Google-sourced
  rows. It does **not** catch OSM/Overpass rows, which have no place ID —
  dedupe those by normalized name before inserting.
- Never `DELETE` from `leads`, `businesses`, or `demo_sites`. Set
  `status='dead'` instead.

## 4. Test scripts must not touch production

`config.py` calls `load_dotenv()` at import, so unsetting `TURSO_DATABASE_URL`
in `os.environ` is not enough — dotenv refills it and your "local" test writes
to the live database. This bit us: a self-check wrote fake leases into
`ops_meta`. Set the vars to empty strings and re-exec before import, and assert
`not db.turso_configured()` at the top of the test. See `coord.py demo()`.

## 5. Env vars go through GitHub, never the Render dashboard

No Render API key exists on the dev machines. Set values with
`gh secret set` / `gh variable set`, add the name to `sync-payment-env.yml`,
then run that workflow.

**Render's env-vars GET returns 20 items by default and the PUT replaces the
whole set.** A truncated read silently deletes every var beyond the first 20.
This destroyed `PYTHON_VERSION`, `RESEND_API_KEY`, `LOCATIONIQ_API_KEY`, and
six others on 2026-09-07. All reads now use `?limit=100` and the workflow
refuses to write a set that looks truncated — keep both guards.

## 6. Deploys are serialized; don't fight over them

Push to `main` triggers a Render deploy. If the other agent is mid-deploy,
wait for it rather than pushing on top. A failed deploy leaves the previous
version live, so the site stays up — but two racing deploys make it very hard
to tell which change broke what.

## 7. Leave findings behind, not just changes

Append what you learned to `NOTES.md` with a date and your name, especially
dead ends. The other agent cannot see your session. Things worth writing down:
an API that returned nothing useful, a field that's always empty, a budget
that ran out, a matching heuristic that produced false positives.

## What each side is currently better at

Not a rule, just where the work has naturally landed — trade accordingly.

- **Grok Bot** has no repo access and works through the deployed surface:
  running the pipeline, the `/ops` board, Stripe and Vercel dashboards, DNS.
  Good at "is the live thing behaving."
- **Claude** has the repo, the DB, and the shell: reading code paths, tracing
  why a stage produced zero, writing scripts, workflows, migrations.
  Good at "why is the live thing behaving that way."

The useful handoff is Grok Bot reporting a symptom from production and Claude
finding the cause in the code — that's how the `emails_found: 0` stall got
traced to `email_finder.py` needing a domain that 93% of leads don't have.

## Open state as of 2026-09-07

- Stripe live: checkout works, webhook `we_1UD8lb…` enabled with 4 events.
- **0 of 402 leads have an email address.** The funnel has never sent one.
  Hunter/Apollo need a domain; ~93% of leads have no website, so they can't
  help. Phone + SMS is the reachable channel.
- Overpass (OpenStreetMap) is free, needs no key, and has no quota — it found
  135 Miami businesses with a phone and no website, 121 of them new. That is
  the cheapest lead source available and it is not wired into the pipeline yet.
