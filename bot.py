"""
Telegram control panel for the Local Business AI Bot.
Admin-only. Commands for scanning, generating demos, sending proposals, stats.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import html as html_module

sys.path.insert(0, os.path.dirname(__file__))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import (
    TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS, DEMO_BASE_URL, DEMO_EXPIRE_HOURS,
    CITIES, BUSINESS_CATEGORIES, DEFAULT_CATEGORIES,
    BOT_PASSCODE, MAX_UNLOCK_ATTEMPTS, UNLOCK_COOLDOWN_MIN
)
import db
from scanner.scanner import scan_city, scan_area, verify_website
from generator import generate_site
from emailer import send_proposal


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS if ADMIN_USER_IDS else True  # open if no admins set


def reply(update: Update):
    """Works for both plain messages and callback-query updates."""
    return update.effective_message


def is_locked_out(uid: int) -> int:
    """Returns minutes remaining in cooldown, or 0 if not locked out."""
    row = db.get_auth_row(uid)
    if not row or (row["attempts"] or 0) < MAX_UNLOCK_ATTEMPTS or not row["last_attempt"]:
        return 0
    try:
        last = datetime.fromisoformat(row["last_attempt"])
    except (TypeError, ValueError):
        return 0
    elapsed = (datetime.now() - last).total_seconds() / 60
    return max(0, int(UNLOCK_COOLDOWN_MIN - elapsed) + 1) if elapsed < UNLOCK_COOLDOWN_MIN else 0


def has_access(uid: int) -> bool:
    """Admin ids bypass the gate; everyone else must have unlocked with the passcode."""
    if ADMIN_USER_IDS and uid in ADMIN_USER_IDS:
        return True
    if not BOT_PASSCODE:          # no passcode configured -> fall back to admin list
        return is_admin(uid)
    return db.is_unlocked(uid)


def require_admin(func):
    """Gate every command behind the passcode (and the admin list, if set)."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not has_access(uid):
            await reply(update).reply_text(
                "🔒 Locked. Send `/unlock <passcode>` to continue.", parse_mode="Markdown")
            return
        if not is_admin(uid):
            await reply(update).reply_text("⛔ Unauthorized.")
            return
        return await func(update, context)
    return wrapper


async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unlock <passcode> — one-time per Telegram account."""
    uid = update.effective_user.id
    uname = update.effective_user.username or ""
    msg = update.effective_message

    # Delete the message so the passcode isn't left sitting in chat history.
    try:
        await msg.delete()
    except Exception:
        pass

    if not BOT_PASSCODE:
        await context.bot.send_message(uid, "No passcode is configured (BOT_PASSCODE is empty).")
        return

    if db.is_unlocked(uid):
        await context.bot.send_message(uid, "✅ Already unlocked. /help for commands.")
        return

    wait = is_locked_out(uid)
    if wait:
        await context.bot.send_message(
            uid, f"⛔ Too many failed attempts. Try again in {wait} minute(s).")
        return

    supplied = (context.args[0].strip() if context.args else "")
    if supplied and supplied == BOT_PASSCODE:
        db.unlock_user(uid, uname)
        print(f"  unlocked: {uid} (@{uname})")
        await context.bot.send_message(
            uid, "🔓 *Unlocked.* This device is remembered — /lock to revoke.\n\n"
                 "Send /help for commands.", parse_mode="Markdown")
    else:
        attempts, _ = db.record_failed_attempt(uid, uname)
        left = max(0, MAX_UNLOCK_ATTEMPTS - attempts)
        print(f"  failed unlock: {uid} (@{uname}) attempt {attempts}")
        if left:
            await context.bot.send_message(uid, f"❌ Wrong passcode. {left} attempt(s) left.")
        else:
            await context.bot.send_message(
                uid, f"⛔ Locked out for {UNLOCK_COOLDOWN_MIN} minutes.")


async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/lock — revoke this account's access."""
    uid = update.effective_user.id
    db.lock_user(uid)
    await reply(update).reply_text("🔒 Locked. Send /unlock <passcode> to get back in.")


@require_admin
async def setemail_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setemail <address> — where replies to your proposals should land."""
    uid = update.effective_user.id
    if not context.args:
        current = db.get_reply_to(uid)
        await reply(update).reply_text(
            f"Current reply-to: {current or '(not set)'}\n\n"
            "Usage: /setemail you@example.com")
        return
    email = context.args[0].strip()
    if "@" not in email:
        await reply(update).reply_text("That doesn't look like an email. Try again.")
        return
    db.set_reply_to(uid, email)
    await reply(update).reply_text(f"✅ Replies will now go to {email}")


# ========== COMMANDS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        await reply(update).reply_text(
            "🔒 This bot is private.\n\nSend `/unlock <passcode>` to continue.",
            parse_mode="Markdown")
        return

    empty = ""
    try:
        if db.get_stats().get("sites", 0) == 0:
            empty = (
                "\n\nNo sites yet. Point us at a restaurant without a website "
                "and we’ll draft one."
            )
    except Exception:
        pass

    text = (
        "🏪 *Local Business AI Bot*\n\n"
        "Find independent businesses without real websites, "
        "generate clean demo sites, and send *proposal* emails "
        "(free sample, no invoice)."
        f"{empty}\n\n"
        "*Commands*\n"
        "/cities — list available cities\n"
        "/scan `[city]` — scan a city (or all defaults)\n"
        "/leads — recent leads\n"
        "/lead `[id]` — lead details\n"
        "/generate `[id]` — create demo site\n"
        "/preview `[id]` — get demo link\n"
        "/propose `[id] [email]` — send proposal email\n"
        "/stats — numbers\n"
        "/lock — revoke this device\n"
        "/help — this message"
    )
    await reply(update).reply_text(text, parse_mode="Markdown")


@require_admin
async def cities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["*Available cities*\n"]
    for key, c in CITIES.items():
        lines.append(f"`{key}` — {c['name']}, {c['state']} ({len(c['areas'])} areas)")
    await reply(update).reply_text("\n".join(lines), parse_mode="Markdown")


@require_admin
async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await reply(update).reply_text("🔍 Preparing scan…")

    if context.args:
        city_key = context.args[0].lower()
        if city_key not in CITIES:
            await msg.edit_text(f"❌ Unknown city `{city_key}`. Use /cities.")
            return
        await msg.edit_text(f"🔍 Scanning {CITIES[city_key]['name']}… this can take several minutes.")
        total = await asyncio.to_thread(scan_city, city_key, DEFAULT_CATEGORIES, 8)
        await msg.edit_text(f"✅ {CITIES[city_key]['name']} done — *{total}* new leads.", parse_mode="Markdown")
    else:
        await msg.edit_text("🔍 Scanning default city set (this will take a while)…")
        from scanner.scanner import scan_multiple
        total = await asyncio.to_thread(scan_multiple, None, None, 5)
        await msg.edit_text(f"✅ Multi-city scan complete — *{total}* new leads.", parse_mode="Markdown")


@require_admin
async def leads_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = 12
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])

    rows = db.get_leads(limit=limit)
    if not rows:
        await reply(update).reply_text("No leads yet. Run /scan first.")
        return

    lines = ["🎯 *Recent leads*\n"]
    for r in rows:
        name = html_module.escape(str(r["name"])[:32])
        status = r["status"]
        city = r["city"] or "?"
        cat = r["category"] or "?"
        lines.append(f"`{r['id']}` {name} · {city}/{cat} · {status}")

    await reply(update).reply_text("\n".join(lines), parse_mode="Markdown")


@require_admin
async def lead_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update).reply_text("Usage: /lead [id]")
        return
    try:
        lid = int(context.args[0])
    except ValueError:
        await reply(update).reply_text("Invalid id")
        return

    lead = db.get_lead(lid)
    if not lead:
        await reply(update).reply_text("Lead not found")
        return

    text = (
        f"📋 *Lead #{lead['id']}*\n\n"
        f"*{html_module.escape(str(lead['name']))}*\n"
        f"📍 {lead['address'] or '—'}\n"
        f"📞 {lead['phone'] or '—'}\n"
        f"🏙 {lead['city']} / {lead['category']}\n"
        f"⭐ {lead['rating'] or 'n/a'}\n"
        f"Status: `{lead['status']}`\n"
        f"Website status: {lead['website_status']}\n"
        f"Emailed: {'yes' if lead['emailed'] else 'no'}\n"
        f"Sold: {'yes' if lead['sold'] else 'no'}"
    )
    kb = [
        [InlineKeyboardButton("Generate demo", callback_data=f"gen_{lid}")],
        [InlineKeyboardButton("Preview link", callback_data=f"prev_{lid}")],
    ]
    await reply(update).reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


@require_admin
async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update).reply_text("Usage: /generate [lead_id]")
        return
    try:
        lid = int(context.args[0])
    except ValueError:
        await reply(update).reply_text("Invalid id")
        return

    lead = db.get_lead(lid)
    if not lead:
        await reply(update).reply_text("Lead not found")
        return

    msg = await reply(update).reply_text(f"🖥️ Generating demo for {html_module.escape(str(lead['name']))}…")

    html, token = await asyncio.to_thread(
        generate_site,
        name=lead["name"],
        address=lead["address"] or "",
        phone=lead["phone"] or "",
        category=lead["category"] or "default",
        rating=lead["rating"],
        city=lead["city"] or "",
        lead_id=lid,
        business_id=lead["business_id"],
        watermark=True,
    )

    db.create_demo_site(lid, lead["business_id"], html, token, template_used=lead["category"])
    expires = datetime.now() + timedelta(hours=DEMO_EXPIRE_HOURS)
    db.update_lead(
        lid,
        status="site_generated",
        demo_token=token,
        demo_created_at=datetime.now().isoformat(),
        demo_expires_at=expires.isoformat(),
    )

    url = f"{DEMO_BASE_URL}/demo/{token}"
    await msg.edit_text(
        f"✅ Demo ready\n\n"
        f"🔗 `{url}`\n"
        f"⏳ Expires {expires.strftime('%b %d %I:%M %p')}\n"
        f"Token: `{token}`",
        parse_mode="Markdown"
    )


@require_admin
async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update).reply_text("Usage: /preview [lead_id]")
        return
    try:
        lid = int(context.args[0])
    except ValueError:
        await reply(update).reply_text("Invalid id")
        return

    lead = db.get_lead(lid)
    if not lead or not lead["demo_token"]:
        await reply(update).reply_text("No demo yet. Run /generate first.")
        return

    url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"
    await reply(update).reply_text(
        f"🔗 Demo link:\n`{url}`\n\nExpires: {lead['demo_expires_at'] or '?'}",
        parse_mode="Markdown"
    )


@require_admin
async def propose_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /propose [lead_id] [email] """
    if len(context.args) < 2:
        await reply(update).reply_text("Usage: /propose [lead_id] [owner_email@example.com]")
        return
    try:
        lid = int(context.args[0])
    except ValueError:
        await reply(update).reply_text("Invalid lead id")
        return

    uid = update.effective_user.id
    reply_to = db.get_reply_to(uid)
    if not reply_to:
        await reply(update).reply_text(
            "📧 What email do you want replies sent to? Set it once with:\n"
            "/setemail you@example.com")
        return

    email = context.args[1].strip()
    lead = db.get_lead(lid)
    if not lead:
        await reply(update).reply_text("Lead not found")
        return
    if not lead["demo_token"]:
        await reply(update).reply_text("Generate a demo first with /generate")
        return

    if lead["website_status"] != "has_site":
        found = verify_website(lead["name"], lead["address"] or "")
        if found:
            db.update_lead(lid, website_status="has_site", status="dead")
            await reply(update).reply_text(
                f"⚠️ Skipped — {lead['name']} actually has a website: {found}\n"
                f"(LocationIQ's data missed it; marked dead so it won't come up again.)")
            return

    url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"
    msg = await reply(update).reply_text(f"📧 Sending proposal to {email}…")

    result = send_proposal(
        business_name=str(lead["name"]),
        demo_url=url,
        owner_email=email,
        category=lead["category"] or "business",
        city=lead["city"] or "",
        lead_id=lid,
        reply_to=reply_to,
    )

    if result:
        db.update_lead(lid, emailed=1, email_sent_at=datetime.now().isoformat(), status="proposed")
        await msg.edit_text(f"✅ Proposal sent to {email}")
    else:
        await msg.edit_text("❌ Failed to send (check RESEND_API_KEY, SENDER_POSTAL_ADDRESS, and logs)")


@require_admin
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.get_stats()
    lines = [
        "📊 *Stats*\n",
        f"Businesses: {s['businesses']}",
        f"Leads: {s['leads']}",
        f"Sites: {s['sites']}",
    ]
    if s["sites"] == 0:
        lines.append(
            "No sites yet. Point us at a restaurant without a website and we’ll draft one."
        )
    lines += [
        f"Proposed: {s['emailed']}",
        f"Replied: {s['replied']}",
        f"Sold: {s['sold']}",
        f"Opted out: {s['suppressed']}",
        "",
        "*By city*",
    ]
    for city, cnt in list(s["by_city"].items())[:12]:
        lines.append(f"  {city}: {cnt}")
    lines.append("\n*By category*")
    for cat, cnt in s["by_category"].items():
        lines.append(f"  {cat}: {cnt}")
    await reply(update).reply_text("\n".join(lines), parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    data = query.data or ""

    if data.startswith("gen_"):
        context.args = [data.split("_")[1]]
        await generate_cmd(update, context)
    elif data.startswith("prev_"):
        context.args = [data.split("_")[1]]
        await preview_cmd(update, context)


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in environment / .env")
        return

    db.init_db()
    print("🏪 Local Business AI Bot starting…")
    print(f"Cities loaded: {len(CITIES)}")
    print(f"Categories: {list(BUSINESS_CATEGORIES.keys())}")
    if BOT_PASSCODE:
        print(f"🔐 Passcode gate ON ({len(BOT_PASSCODE)} digits, "
              f"{MAX_UNLOCK_ATTEMPTS} attempts then {UNLOCK_COOLDOWN_MIN}m lockout)")
    elif not ADMIN_USER_IDS:
        print("⚠️  No BOT_PASSCODE and no ADMIN_USER_IDS — bot is OPEN to anyone who finds it.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("unlock", unlock_cmd))
    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("setemail", setemail_cmd))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("cities", cities_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("leads", leads_cmd))
    app.add_handler(CommandHandler("lead", lead_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("preview", preview_cmd))
    app.add_handler(CommandHandler("propose", propose_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Polling…")
    app.run_polling()


if __name__ == "__main__":
    main()
