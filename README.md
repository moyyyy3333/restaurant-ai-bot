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

## Production

Render is the only public runtime. The service command is defined in the
`Procfile` as `python3 run.py`. Set `PUBLIC_BASE_URL` to the Render service URL;
demo and unsubscribe links inherit it. Render startup fails loudly if either
link points to localhost.

Pushes to `main` trigger `.github/workflows/deploy.yml`, which deploys Render
and verifies `/health`. The daily workflow calls `/pipeline/run` with
`X-Pipeline-Token`.

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
area expands to only one business lookup.

API-provider daily ceilings are configured with the `*_DAILY_BUDGET` variables
in `.env.example`; shared counters are stored in `ops_meta`.
