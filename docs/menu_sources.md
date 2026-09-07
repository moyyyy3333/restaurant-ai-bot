# Demo menu sources

Snapshot not yet filled — run:

```sh
python3 scripts/report_menu_sources.py --fetch-live --out docs/menu_sources.md
```

Turso/local DB is preferred when `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` (or `LOCAL_DB_PATH`) are set. Without secrets the script uses known tokens from public pipeline logs and Growth PR URLs, then fetches live `/demo/<token>` HTML.

## Totals (this snapshot)

- **0 real**
- **0 sample**
- **0 unknown/missing**

No outreach. Menus are not invented.
