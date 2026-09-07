#!/usr/bin/env python3
"""Add Resend's DNS records to the cPanel zone, without hand-typing them.

Zone Editor takes ~6 clicks per record and silently double-appends the domain
if you paste an FQDN, so this reads the records straight from the Resend API
and writes them through cPanel's UAPI instead.

Auth: a cPanel API token (cPanel > Security > Manage API Tokens > Create).
Store it outside the repo and export it:

    export CPANEL_USER=founneou
    export CPANEL_HOST=server229.web-hosting.com
    export CPANEL_TOKEN="$(cat ~/.cpanel_token)"
    export RESEND_API_KEY="$(cat ~/.resend_key)"

    python3 scripts/dns_add.py outreach.foundrydesk.vip --zone foundrydesk.vip
    python3 scripts/dns_add.py outreach.foundrydesk.vip --zone foundrydesk.vip --apply

Without --apply it only prints what it would add (dry run is the default).
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def resend_records(domain: str, api_key: str) -> list:
    """Fetch the domain's required DNS records from Resend."""
    req = urllib.request.Request(
        "https://api.resend.com/domains",
        headers={"Authorization": f"Bearer {api_key}",
                 "User-Agent": "restaurant-ai-bot/1.0"})  # Resend 403s urllib default
    data = json.load(urllib.request.urlopen(req, timeout=30)).get("data", [])
    match = next((d for d in data if d["name"] == domain), None)
    if not match:
        sys.exit(f"{domain} is not in this Resend account")
    req = urllib.request.Request(
        f"https://api.resend.com/domains/{match['id']}",
        headers={"Authorization": f"Bearer {api_key}",
                 "User-Agent": "restaurant-ai-bot/1.0"})  # Resend 403s urllib default
    detail = json.load(urllib.request.urlopen(req, timeout=30))
    return detail.get("records", []), detail.get("status", "?")


def uapi(host: str, user: str, token: str, module: str, func: str, **params):
    url = (f"https://{host}:2083/execute/{module}/{func}?"
           + urllib.parse.urlencode(params))
    req = urllib.request.Request(
        url, headers={"Authorization": f"cpanel {user}:{token}"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def existing_names(host, user, token, zone) -> set:
    """Names already in the zone, so re-running is safe (no duplicate DKIM)."""
    res = uapi(host, user, token, "DNS", "parse_zone", zone=zone)
    names = set()
    for row in res.get("data", []):
        if row.get("type") != "record":
            continue
        parts = row.get("dname_b64") or row.get("dname")
        if parts:
            import base64
            name = (base64.b64decode(parts).decode() if row.get("dname_b64")
                    else parts)
            names.add(name.rstrip(".").lower())
    return names


def main():
    p = argparse.ArgumentParser()
    p.add_argument("domain", help="e.g. outreach.foundrydesk.vip")
    p.add_argument("--zone", required=True, help="cPanel zone, e.g. foundrydesk.vip")
    p.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    a = p.parse_args()

    api_key = os.environ.get("RESEND_API_KEY") or sys.exit("set RESEND_API_KEY")
    records, status = resend_records(a.domain, api_key)
    print(f"{a.domain} status={status}, {len(records)} records required\n")

    host = os.environ.get("CPANEL_HOST", "server229.web-hosting.com")
    user = os.environ.get("CPANEL_USER")
    token = os.environ.get("CPANEL_TOKEN")

    have = set()
    if a.apply:
        if not (user and token):
            sys.exit("set CPANEL_USER and CPANEL_TOKEN to apply")
        have = existing_names(host, user, token, a.zone)

    for r in records:
        # Resend gives the host relative to the zone already; cPanel appends
        # the zone itself, so passing an FQDN here is what causes the
        # dreaded name.domain.tld.domain.tld duplication.
        name = r["name"]
        fqdn = f"{name}.{a.zone}".lower()
        line = f"{r['type']:5} {name:34} {str(r.get('priority') or ''):>3}  {r['value'][:60]}"
        if fqdn in have:
            print("skip  " + line + "   (already present)")
            continue
        if not a.apply:
            print("would " + line)
            continue
        kw = {"zone": a.zone, "name": name, "type": r["type"],
              "ttl": 14400, "class": "IN"}
        if r["type"] == "TXT":
            kw["txtdata"] = r["value"]
        elif r["type"] == "MX":
            kw["exchange"] = r["value"]
            kw["preference"] = r.get("priority", 10)
        elif r["type"] == "CNAME":
            kw["cname"] = r["value"]
        res = uapi(host, user, token, "DNS", "mass_edit_zone",
                   serial=0, add=json.dumps(kw))
        ok = not res.get("errors")
        print(("added " if ok else "FAIL  ") + line
              + ("" if ok else f"   {res.get('errors')}"))

    if not a.apply:
        print("\ndry run — re-run with --apply to write")


if __name__ == "__main__":
    main()
