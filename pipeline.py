"""Daily scan → build → enrich → outreach pipeline.

DAILY_SEND_LIMIT=0 is a real dry run: discovery, site generation, enrichment,
and truthfulness verification still run, but no email or SMS is sent.
"""

from datetime import datetime, timedelta

import db
from config import (
    DAILY_SEND_LIMIT,
    DEMO_BASE_URL,
    DEMO_EXPIRE_HOURS,
    PIPELINE_SCAN_BUDGET,
    PIPELINE_WORK_LIMIT,
)


def run_daily(send_limit: int | None = None, scan_budget: int | None = None) -> dict:
    from emailer import build_sms, send_proposal, send_sms
    from generator import generate_site
    from scanner.email_finder import find_email
    from scanner.scanner import check_website, daily_scan_sample

    send_limit = DAILY_SEND_LIMIT if send_limit is None else max(0, send_limit)
    scan_budget = PIPELINE_SCAN_BUDGET if scan_budget is None else max(0, scan_budget)
    dry_run = send_limit == 0
    work_limit = max(1, PIPELINE_WORK_LIMIT)
    errors = []

    try:
        found = daily_scan_sample(budget=scan_budget) if scan_budget else 0
    except Exception as exc:
        found = 0
        errors.append({"stage": "scan", "error": str(exc)})

    made = []
    for lead in db.leads_needing_site(limit=work_limit):
        try:
            html_str, token = generate_site(
                name=lead["name"], address=lead["address"] or "",
                phone=lead["phone"] or "", category=lead["category"] or "restaurant",
                rating=lead["rating"], city=lead["city"] or "", lead_id=lead["id"],
                business_id=lead["business_id"], fetch_place=True)
            db.create_demo_site(
                lead["id"], lead["business_id"], html_str, token,
                template_used=lead["category"])
            db.update_lead(
                lead["id"], status="site_generated", demo_token=token,
                demo_created_at=datetime.now().isoformat(),
                demo_expires_at=(
                    datetime.now() + timedelta(hours=DEMO_EXPIRE_HOURS)
                ).isoformat())
            made.append({"lead": lead["id"], "name": lead["name"], "token": token})
        except Exception as exc:
            errors.append({"stage": "site", "lead": lead["id"], "error": str(exc)})

    enriched = []
    for lead in db.leads_missing_email(limit=work_limit * 2):
        try:
            email = find_email(
                lead["name"], lead["biz_website"], lead["website_status"])
            if email:
                db.set_email(lead["id"], lead["business_id"], email)
                enriched.append({"lead": lead["id"], "email": email})
        except Exception as exc:
            errors.append({"stage": "email_find", "lead": lead["id"], "error": str(exc)})

    sent, would_send, skipped_unknown = [], [], []
    candidate_limit = work_limit if dry_run else max(send_limit, 1)
    for lead in db.leads_needing_email(limit=candidate_limit):
        if not dry_run and len(sent) >= send_limit:
            break
        if lead["email"] and db.is_suppressed(lead["email"]):
            continue
        try:
            status, _real_site = check_website(
                lead["name"], lead["address"] or "")
        except Exception as exc:
            errors.append({"stage": "verify", "lead": lead["id"], "error": str(exc)})
            continue
        if status == "has_site":
            db.update_lead(lead["id"], website_status="has_site", status="dead")
            continue
        if status == "unknown":
            db.update_lead(lead["id"], website_status="unknown")
            skipped_unknown.append({"lead": lead["id"], "name": lead["name"]})
            continue
        db.update_lead(lead["id"], website_status=status)
        url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"
        channel = "email" if lead["email"] else "sms"
        target = lead["email"] or lead["phone"]
        if dry_run:
            would_send.append({
                "lead": lead["id"], "name": lead["name"],
                "channel": channel, "target": target, "demo_url": url,
            })
            continue
        if channel == "email":
            result = send_proposal(
                business_name=str(lead["name"]), demo_url=url,
                owner_email=lead["email"], category=lead["category"] or "business",
                city=lead["city"] or "", lead_id=lead["id"])
        else:
            result = send_sms(
                lead["phone"], build_sms(str(lead["name"]), url))
        if result:
            db.update_lead(
                lead["id"], emailed=1, email_sent_at=datetime.now().isoformat(),
                status="proposed")
            sent.append({"lead": lead["id"], channel: target})

    return {
        "ok": not errors,
        "dry_run": dry_run,
        "scan_budget": scan_budget,
        "send_limit": send_limit,
        "scanned_new": found,
        "sites_generated": len(made),
        "emails_found": len(enriched),
        "proposals_sent": len(sent),
        "would_send": len(would_send),
        "skipped_unverified": len(skipped_unknown),
        "sites": made,
        "enriched": enriched,
        "sent": sent,
        "would_send_items": would_send,
        "unverified": skipped_unknown,
        "errors": errors,
    }
