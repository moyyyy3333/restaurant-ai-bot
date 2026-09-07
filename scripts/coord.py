#!/usr/bin/env python3
"""Work-splitting between concurrent agents (Claude, Grok Bot, cron).

Two agents on one Turso DB collide in exactly two ways: they scan the same
city twice, and they race for the same daily API budget. Both are fixed with
rows in ops_meta, which every agent already shares — no new service.

    coord.py claim miami --owner claude --minutes 90
    coord.py budget google_places --owner claude --cap 50 --share 0.5
    coord.py status
    coord.py release miami --owner claude

Exit code 0 = you may proceed, 1 = someone else holds it / no allowance left,
so it composes with shell:  coord.py claim miami --owner claude && ./run.sh
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402

LEASE = "lease:{scope}"
SPEND = "budget:{api}:{date}:{owner}"


def _now():
    return datetime.now(timezone.utc)


def _today():
    return _now().date().isoformat()


def claim(scope: str, owner: str, minutes: int) -> bool:
    """Take the lease on scope unless a live one is held by someone else.

    The upsert is conditional so two agents racing can't both win: SQLite
    applies DO UPDATE ... WHERE atomically, and changes() tells us if we won.
    """
    db.ensure_schema()
    key = LEASE.format(scope=scope)
    expires = (_now() + timedelta(minutes=minutes)).isoformat()
    value = f"{owner}|{expires}"
    with db.conn() as c:
        c.execute(
            "INSERT INTO ops_meta (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at "
            # win if the lease is ours already, or the holder's time is up
            "WHERE substr(ops_meta.value, 1, instr(ops_meta.value, '|') - 1) = ? "
            "   OR substr(ops_meta.value, instr(ops_meta.value, '|') + 1) < ?",
            (key, value, db.now(), owner, _now().isoformat()))
        row = c.execute("SELECT value FROM ops_meta WHERE key = ?", (key,)).fetchone()
    return bool(row) and row["value"] == value


def release(scope: str, owner: str) -> bool:
    key = LEASE.format(scope=scope)
    held = db.get_meta(key)
    if held and held.split("|", 1)[0] != owner:
        return False
    db.set_meta(key, f"{owner}|{_now().isoformat()}")  # expire it now
    return True


def budget(api: str, owner: str, cap: int, share: float, amount: int = 1) -> int:
    """Reserve `amount` calls from this owner's slice. Returns calls remaining.

    Additive on purpose: db.consume_daily_budget still enforces the real cap.
    This only stops one agent from eating the whole day before the other runs.
    """
    db.ensure_schema()
    mine = int(cap * share)
    key = SPEND.format(api=api, date=_today(), owner=owner)
    used = int(db.get_meta(key) or 0)
    if used + amount > mine:
        return -1
    db.set_meta(key, str(used + amount))
    return mine - used - amount


def status() -> list:
    db.ensure_schema()
    out = []
    with db.conn() as c:
        rows = c.execute(
            "SELECT key, value FROM ops_meta WHERE key LIKE 'lease:%' "
            "OR key LIKE 'budget:%' ORDER BY key").fetchall()
    now = _now().isoformat()
    for r in rows:
        key, val = r["key"], r["value"]
        if key.startswith("lease:"):
            owner, _, exp = val.partition("|")
            state = "LIVE " if exp > now else "free "
            out.append(f"{state} {key:24} {owner:10} until {exp[:19]}")
        elif key.count(":") == 3:  # per-owner spend
            out.append(f"spend {key:44} {val}")
    return out


def demo():
    """Self-check against a scratch DB: leases are exclusive, budgets split.

    Re-execs itself with the DB env set BEFORE any import: config caches the
    Turso URL at import time, so reload(db) alone would still hit production
    (it did once, and wrote junk leases into the live ops_meta).
    """
    import os
    if os.environ.get("COORD_SELFCHECK") != "1":
        import subprocess, tempfile
        env = dict(os.environ)
        # Empty, not absent: config.py calls load_dotenv, which would otherwise
        # refill these from the repo's .env and point the check at production.
        env.update(COORD_SELFCHECK="1", TURSO_DATABASE_URL="", TURSO_AUTH_TOKEN="",
                   LOCAL_DB_PATH=tempfile.mktemp(suffix=".db"))
        sys.exit(subprocess.call([sys.executable, __file__, "demo"], env=env))
    assert not db.turso_configured(), "self-check must not run against Turso"

    assert claim("miami", "claude", 60), "first claim should win"
    assert not claim("miami", "grok", 60), "second agent must be locked out"
    assert claim("miami", "claude", 60), "owner may re-claim (extend)"
    assert claim("houston", "grok", 60), "different scope is independent"
    assert release("miami", "claude"), "owner can release"
    assert claim("miami", "grok", 60), "released lease is takeable"

    assert budget("google_places", "claude", cap=50, share=0.5, amount=20) == 5
    assert budget("google_places", "claude", cap=50, share=0.5, amount=5) == 0
    assert budget("google_places", "claude", cap=50, share=0.5) == -1, "own slice spent"
    assert budget("google_places", "grok", cap=50, share=0.5) == 24, "other slice intact"
    print("coord self-check passed")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("claim", help="take a work lease on a scope (e.g. a city)")
    c.add_argument("scope")
    c.add_argument("--owner", required=True)
    c.add_argument("--minutes", type=int, default=90)

    r = sub.add_parser("release", help="give the lease back early")
    r.add_argument("scope")
    r.add_argument("--owner", required=True)

    b = sub.add_parser("budget", help="reserve API calls from your own slice")
    b.add_argument("api")
    b.add_argument("--owner", required=True)
    b.add_argument("--cap", type=int, required=True)
    b.add_argument("--share", type=float, default=0.5)
    b.add_argument("--amount", type=int, default=1)

    sub.add_parser("status", help="who holds what")
    sub.add_parser("demo", help="run the self-check")

    a = p.parse_args()
    if a.cmd == "claim":
        ok = claim(a.scope, a.owner, a.minutes)
        holder = db.get_meta(LEASE.format(scope=a.scope)).split("|", 1)[0]
        print(f"{'claimed' if ok else 'DENIED'} {a.scope} (holder: {holder})")
        sys.exit(0 if ok else 1)
    if a.cmd == "release":
        ok = release(a.scope, a.owner)
        print(f"{'released' if ok else 'NOT YOURS'} {a.scope}")
        sys.exit(0 if ok else 1)
    if a.cmd == "budget":
        left = budget(a.api, a.owner, a.cap, a.share, a.amount)
        print(f"{a.api}: {'no allowance left' if left < 0 else str(left) + ' left'} for {a.owner}")
        sys.exit(1 if left < 0 else 0)
    if a.cmd == "status":
        print("\n".join(status()) or "nothing held")
    if a.cmd == "demo":
        demo()


if __name__ == "__main__":
    main()
