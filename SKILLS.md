# Skills Reference

Collection of skills and patterns learned across projects. No personal info — just techniques, commands, and patterns.

---

## GitHub Skills

### github-auth
- Setup HTTPS token auth or SSH for GitHub
- `gh auth login` / `git config credential.helper store`
- Personal access tokens: `repo`, `workflow`, `read:org` scopes
- Extract token from `~/.git-credentials` if needed

### github-repo-management
- Clone, create, fork, configure repos via `gh` or `git` + `curl`
- `gh repo create`, `gh repo clone`, `gh repo fork`
- Secrets management: `gh secret set KEY --body value`
- Releases: `gh release create v1.0.0 --generate-notes`
- Branch protection via API
- Workflow management: `gh workflow list`, `gh run list`, `gh run view`

### github-pr-workflow
- Branch naming: `feat/description`, `fix/description`, `ci/description`
- Conventional commits: `type(scope): short description`
- PR lifecycle: branch → commit → push → PR → monitor CI → merge
- Auto-fix CI failures loop: check → read logs → fix → push → verify
- Merge methods: squash, merge, rebase
- Code review checklist: correctness, security, code quality, testing, performance, docs

### Pipeline Best Practices (from awesome-copilot)
- Pin all GitHub Actions to full SHA (not branch/tag)
- Use OIDC instead of static credentials for cloud auth
- Use `permissions:` at job level for least-privilege
- Use `paths-ignore` to skip pipeline for doc-only changes
- Use reusable workflows for shared pipeline steps
- Use `gh actions-importer` to migrate from Jenkins/CircleCI

---

## Deployment Skills

### Render Deploy
- GitHub Actions auto-deploy on push to main
- `.github/workflows/deploy.yml` with `RENDER_API_KEY` and `RENDER_SERVICE_ID` secrets
- Service-level PATCH to set env vars: `curl -X PATCH https://api.render.com/v1/services/{id} -d '{"KEY":"value"}'`
- Env vars endpoint returns 405 for POST/PUT; use service-level PATCH instead
- Verify deploy: `curl -s https://your-app.onrender.com/`

### Railway Deploy
- `railway login`, `railway project link`, `railway deploy`
- Persistent volumes: `railway volume add --mount-path /data`
- SQLite persistence: set `DATABASE_URL=sqlite:///data/app.db`
- Co-host bot + web server: `python bot.py & gunicorn server:app`
- Token auth workarounds for expired CLI sessions
- GitHub Actions deploy with project token

### Vercel Deploy
- `npx vercel --yes --prod`
- Cache busting: `CACHE_BUST=$(date +%s)` env var
- Never overwrite production URLs without checking first
- API keys in env vars, never in scripts

---

## Bot Passcode Gate Pattern

### config.py
```python
BOT_PASSCODE = os.getenv("BOT_PASSCODE", "9911").strip()
MAX_UNLOCK_ATTEMPTS = int(os.getenv("MAX_UNLOCK_ATTEMPTS", "5"))
UNLOCK_COOLDOWN_MIN = int(os.getenv("UNLOCK_COOLDOWN_MIN", "15"))
```

### db.py
```python
def is_unlocked(user_id: int) -> bool:
    r = c.execute("SELECT unlocked_at FROM bot_auth WHERE user_id = ?", (user_id,)).fetchone()
    return bool(r and r["unlocked_at"])

def unlock_user(user_id: int, username: str = ""):
    now = datetime.utcnow().isoformat()
    c.execute("""INSERT INTO bot_auth (user_id, username, unlocked_at, attempts, last_attempt)
                 VALUES (?,?,?,0,?)
                 ON CONFLICT(user_id) DO UPDATE SET
                       unlocked_at = excluded.unlocked_at, attempts = 0,
                       last_attempt = excluded.last_attempt""",
              (user_id, username, now, now))

def lock_user(user_id: int):
    c.execute("UPDATE bot_auth SET unlocked_at = NULL WHERE user_id = ?", (user_id,))

def lock_all_users():
    """Revoke all active unlocks. Used when the passcode is rotated."""
    c.execute("UPDATE bot_auth SET unlocked_at = NULL WHERE unlocked_at IS NOT NULL")

def record_failed_attempt(user_id: int, username: str = "") -> tuple[int, str | None]:
    # increments counter, returns (attempts, last_attempt_iso)
```

### bot.py
- `/unlock <passcode>` — one-time per Telegram account
- `/lock` — revoke own access
- Passcode deleted from chat history immediately
- Rate-limited: 5 attempts, 15-min coolout
- Admin IDs bypass the gate

---

## Free-Tier Services Pipeline

| Service | Free Tier | Purpose |
|---------|-----------|---------|
| Twilio | 100 SMS, no CC | SMS fallback for leads with phone but no email |
| Hunter.io | 25 searches/month | Find business emails by domain |
| Apollo.io | 100 enrichment credits | Email/phone enrichment fallback |
| Resend | Transactional email | Send emails via API |

### Pipeline Flow
1. Scan → build demo sites → find emails (scrape → Hunter → Apollo)
2. Send email via Resend if email found
3. Send SMS via Twilio if phone but no email
4. Skip if neither available

---

## Render API Patterns

### Set env var (service-level PATCH)
```python
import json, urllib.request

payload = json.dumps({"KEY": "value"})
req = urllib.request.Request(
    f"https://api.render.com/v1/services/{SVC_ID}",
    data=payload.encode(),
    headers={
        "Authorization": f"Bearer {RENDER_KEY}",
        "Content-Type": "application/json",
    },
    method="PATCH"
)
```

### Get env vars
```python
req = urllib.request.Request(
    f"https://api.render.com/v1/services/{SVC_ID}/env-vars",
    headers={"Authorization": f"Bearer {RENDER_KEY}"},
    method="GET"
)
```

### Note
- The `/env-vars` endpoint returns 405 for POST/PUT
- The service-level PATCH endpoint works for most vars but may not persist all of them
- If a var disappears after PATCH, it may have been removed from the env-vars store

---

## Apollo.io API

### Company Search
```
GET https://api.apollo.io/v1/company/search?q={domain}&api_key={key}
```

### Email Search
```
GET https://api.apollo.io/v1/email/search?q={domain}&api_key={key}
```

### Note
- Use `/v1/company/search` not `/v1/mixed_company/search` (the latter is deprecated)
- Free tier: 100 enrichment credits

---

## Common Patterns

### Selftest
```python
# Run from project root
python3 scanner/scanner.py --selftest
```

### Deploy Check
```bash
curl -s https://your-app.onrender.com/ | python3 -m json.tool
```

### Git Commit Convention
```
type(scope): short description

- Detail lines wrapped at 72 chars
Types: feat, fix, refactor, docs, test, ci, chore, perf
```

---

## Bug Bounty Tools

### Recon
- `nmap` — port scanning
- `ffuf` — fuzzing endpoints
- `nuclei` — template-based vulnerability scanning
- `amass` — subdomain enumeration
- `httpx` — HTTP probing

### Custom Detectors
- Every lens fires real code, validated against real targets
- Pattern: write detector → validate against known-bad target → refine

### Video Evidence
- `ffmpeg` — capture video evidence with burned timestamps
- Every P1 gets video proof

---

## Obsidian Tools

### Plugin Development
- Obsidian plugins use TypeScript + the Obsidian API
- Plugin manifest in `manifest.json`
- Main entry: `src/main.ts`
- Use `obsidian` npm package for types

### Quick Plugin Setup
```bash
mkdir my-plugin && cd my-plugin
npm init -y
npm install obsidian
```

### Key Patterns
- `Plugin.registerEvent()` for lifecycle hooks
- `Workspace.getActiveFile()` for current file
- `Vault.read()` / `Vault.modify()` for file operations
- `Notice()` for user feedback
- `Setting()` for plugin settings UI

### Build & Deploy
```bash
# Build
npx esbuild main.ts --bundle --outfile=dist/main.js --format=cjs --platform=node

# Package
zip -r my-plugin.zip manifest.json dist/
```

---

## AI/ML Tools

### Local Models
- `ollama` — run models locally at `127.0.0.1:11434`
- `qwen3-8b-local:latest`, `qwen3:8b`
- `llama.cpp` — run quantized models, tune context windows

### Fine-tuning
- LoRA, QLoRA, Axolotl — for custom model training

### Cloud Models
- OpenRouter, HuggingFace Pro — any model, any task

### Dolphin (uncensored)
- Local uncensored model at `127.0.0.1:9001`

---

## Data Tools

### PostgreSQL / Supabase
- Relational, real-time, scalable
- `supabase` CLI for local dev

### Scraping
- `Browser-harness` / `Puppeteer` — scrape anything
- Python pipelines for ETL, enrichment, dataset building

---

## DevOps Tools

### Vercel
- `npx vercel --yes --prod`
- `npx vercel redeploy <url>`
- `npx vercel env add KEY`

### Railway
- `railway login`, `railway project link`, `railway deploy`
- `railway variable set KEY=value`
- `railway volume add --mount-path /data`

### GitHub Actions
- `gh workflow list`, `gh run list`, `gh run view`
- `gh secret set KEY --body value`
- `gh actions-importer` — migrate from Jenkins/CircleCI

---

## Security Tools

### API Key Safety
- Never embed API keys directly in scripts
- Use env vars or file-based auth
- `.env.example` for placeholders, `.gitignore` for `.env`

### Shell Escaping
- Keys with `$`, backticks, quotes break inline commands
- Use `$(cat file)` or env vars instead
- For Python `subprocess`, pass key as separate env var

### Token Revocation
- GitHub auto-revokes tokens that appear in chat logs
- Use file-based auth for testing APIs