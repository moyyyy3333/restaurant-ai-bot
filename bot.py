"""Restaurant AI Bot — Telegram-controlled Houston lead generation system"""
import sys, os, asyncio, json, html as html_module
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS, DEMO_BASE_URL, DEMO_EXPIRE_HOURS
import db
from scanner.scanner import scan_all_houston, scan_area_houston
from generator import generate_with_sample_menu
from emailer import send_outreach
from config import HOUSTON_AREAS

# === AUTH ===
def is_admin(user_id):
    return user_id in ADMIN_USER_IDS

def require_admin(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not is_admin(user.id):
            await update.message.reply_text("⛔ Unauthorized. Only the bot owner can use this.")
            return
        return await func(update, context)
    return wrapper

# === COMMANDS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome screen"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🤖 Restaurant AI Bot — Houston lead generation system.")
        return
    
    lines = [
        "🏪 *Restaurant AI Bot*\n",
        "I find Houston restaurants without websites, build them beautiful sites with takeout ordering, and email the owners.\n",
        "*Commands:*",
        "/scan — Scan all Houston areas for leads",
        "/scan \\[area\\] — Scan specific area (e.g. `/scan Heights`)",
        "/areas — List available Houston areas",
        "/leads — Show recent leads",
        "/lead \\[id\\] — Show lead details",
        "/generate \\[id\\] — Generate website for a lead",
        "/preview \\[id\\] — Get protected demo link",
        "/email \\[id\\] — Send outreach to owner",
        "/stats — Bot statistics",
        "/help — This menu",
        "",
        f"*Houston areas:* {len(HOUSTON_AREAS)}"
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@require_admin
async def areas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available scan areas"""
    areas_list = "\n".join([f"`{a}`" for a in HOUSTON_AREAS])
    await update.message.reply_text(
        f"*Available Houston Areas:*\n\n{areas_list}",
        parse_mode="Markdown"
    )

@require_admin
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scan Houston for restaurant leads"""
    msg = await update.message.reply_text("🔍 Starting scan...")
    
    # Check for specific area
    if context.args:
        area = " ".join(context.args)
        if area in HOUSTON_AREAS:
            await msg.edit_text(f"🔍 Scanning {area}... (this may take a minute)")
            leads = await asyncio.to_thread(scan_area_houston, area)
            await msg.edit_text(f"✅ {area} scan complete — {leads} new leads found!")
        else:
            await msg.edit_text(f"❌ Area '{area}' not found. Use /areas to see available areas.")
        return
    
    # Full scan
    await msg.edit_text("🔍 Scanning all Houston areas... (this may take 5-10 minutes)")
    
    total = await asyncio.to_thread(scan_all_houston)
    
    stats = db.get_stats()
    await msg.edit_text(
        f"✅ *Full scan complete!*\n\n"
        f"🏪 Total restaurants found: {stats['restaurants']}\n"
        f"🎯 New leads: {total}\n"
        f"📊 Total leads: {stats['leads']}",
        parse_mode="Markdown"
    )

@require_admin
async def leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent leads with keyboard"""
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
    
    results = db.get_leads(limit=limit)
    if not results:
        await update.message.reply_text("No leads yet. Use /scan to find some!")
        return
    
    keyboard = []
    lines = ["🎯 *Recent Leads:*\n"]
    
    for i, r in enumerate(results, 1):
        name = html_module.escape(str(r["name"]))
        site_status = "🌐" if r.get("website_status") == "has_site" else "📭"
        rating = f"★{r['rating']}" if r.get("rating") else "New"
        status = r["status"]
        
        lines.append(f"{i}. {site_status} *{name}* — {rating} ({status})")
        keyboard.append([InlineKeyboardButton(
            f"{i}. {name[:30]}",
            callback_data=f"lead_{r['id']}"
        )])
    
    lines.append(f"\n{len(results)} leads shown")
    
    # Add navigation
    keyboard.append([
        InlineKeyboardButton("🔄 Scan All", callback_data="scan_all"),
        InlineKeyboardButton("📊 Stats", callback_data="stats")
    ])
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@require_admin
async def lead_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details for a specific lead"""
    if not context.args:
        await update.message.reply_text("Usage: /lead [id]")
        return
    
    try:
        lead_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID. Use /leads to see IDs.")
        return
    
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    
    if not lead:
        await update.message.reply_text(f"Lead {lead_id} not found.")
        return
    
    lines = [
        f"📋 *Lead #{lead['id']}*\n",
        f"🏪 *{html_module.escape(str(lead['name']))}*",
        f"📍 {lead['address'] or 'No address'}",
        f"📞 {lead['phone'] or 'No phone'}",
        f"⭐ Rating: {lead['rating'] or 'N/A'} ({lead.get('user_ratings_total', 0)} reviews)",
        f"📊 Status: {lead['status']}",
        f"🌐 Website: {'Yes' if lead.get('website_status') == 'has_site' else 'No'}",
        f"📧 Emailed: {'Yes' if lead['emailed'] else 'No'}",
        f"💲 Sold: {'✅' if lead['sold'] else '❌'}",
    ]
    
    keyboard = [
        [InlineKeyboardButton("🖥️ Generate Site", callback_data=f"gen_{lead['id']}")],
        [InlineKeyboardButton("📧 Email Owner", callback_data=f"email_{lead['id']}")],
        [InlineKeyboardButton("🔗 Preview Link", callback_data=f"preview_{lead['id']}")],
        [InlineKeyboardButton("⬅️ Back to Leads", callback_data="list_leads")],
    ]
    
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@require_admin
async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a restaurant website for a lead"""
    if not context.args:
        await update.message.reply_text("Usage: /generate [lead_id]")
        return
    
    try:
        lead_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID.")
        return
    
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    
    if not lead:
        await update.message.reply_text(f"Lead {lead_id} not found.")
        return
    
    msg = await update.message.reply_text(f"🖥️ Generating site for {html_module.escape(str(lead['name']))}...")
    
    # Get the restaurant details
    restaurant = db.get_restaurant(lead["restaurant_id"])
    if not restaurant:
        await msg.edit_text("❌ Restaurant not found in database.")
        return
    
    # Generate the HTML
    html_content, token = generate_with_sample_menu(
        name=restaurant["name"],
        address=restaurant["address"],
        phone=restaurant["phone"],
        cuisine=restaurant.get("cuisine", ""),
        rating=restaurant.get("rating"),
        lead_id=lead_id,
        restaurant_id=restaurant["id"]
    )
    
    # Save to database
    db.create_demo_site(lead_id, restaurant["id"], html_content, token)
    
    # Update lead with demo info
    expires_at = datetime.now() + timedelta(hours=DEMO_EXPIRE_HOURS)
    db.update_lead(lead_id,
        status="site_generated",
        generated_site_path=token,
        demo_token=token,
        demo_created_at=datetime.now().isoformat(),
        demo_expires_at=expires_at.isoformat()
    )
    
    demo_url = f"{DEMO_BASE_URL}/demo/{token}"
    
    await msg.edit_text(
        f"✅ *Site generated!*\n\n"
        f"🏪 {html_module.escape(str(restaurant['name']))}\n"
        f"🔗 Demo: `{demo_url}`\n"
        f"⏳ Expires: {expires_at.strftime('%b %d, %I:%M %p')}\n"
        f"🆔 Token: `{token}`",
        parse_mode="Markdown"
    )

@require_admin
async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get a protected preview link for a lead"""
    if not context.args:
        await update.message.reply_text("Usage: /preview [lead_id]")
        return
    
    try:
        lead_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID.")
        return
    
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    
    if not lead:
        await update.message.reply_text(f"Lead {lead_id} not found.")
        return
    
    token = lead.get("demo_token")
    if not token:
        await update.message.reply_text("No site generated yet. Use /generate first.")
        return
    
    demo_url = f"{DEMO_BASE_URL}/demo/{token}"
    expires = lead.get("demo_expires_at", "Unknown")
    
    await update.message.reply_text(
        f"🔗 *Demo Link:*\n`{demo_url}`\n\n"
        f"⏳ Expires: {expires}\n"
        f"🔒 Screen capture protected\n"
        f"📧 /email {lead_id} to send to owner",
        parse_mode="Markdown"
    )

@require_admin
async def email_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send outreach email to a lead"""
    if not context.args:
        await update.message.reply_text("Usage: /email [lead_id]")
        return
    
    try:
        lead_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID.")
        return
    
    leads = db.get_leads(limit=100)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    
    if not lead:
        await update.message.reply_text(f"Lead {lead_id} not found.")
        return
    
    if not lead.get("demo_token"):
        await update.message.reply_text("No site generated yet. Use /generate first.")
        return
    
    msg = await update.message.reply_text(f"📧 Sending email for {html_module.escape(str(lead['name']))}...")
    
    demo_url = f"{DEMO_BASE_URL}/demo/{lead['demo_token']}"
    
    # For now, log the email (need Resend API key)
    if not os.environ.get("RESEND_API_KEY"):
        await msg.edit_text(
            f"📧 *Email Ready for {html_module.escape(str(lead['name']))}*\n\n"
            f"_No Resend API key configured yet._\n"
            f"Set `RESEND_API_KEY` in .env to enable sending.\n\n"
            f"Demo URL: `{demo_url}`\n\n"
            f"Mark as emailed manually when sent.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Mark Sent", callback_data=f"marksent_{lead_id}")]
            ])
        )
        return
    
    result = send_outreach(
        owner_name="Owner",
        restaurant_name=str(lead["name"]),
        demo_url=demo_url
    )
    
    if result:
        db.update_lead(lead_id, emailed=1, email_sent_at=datetime.now().isoformat(), status="emailed")
        await msg.edit_text(f"✅ Email sent to {html_module.escape(str(lead['name']))}!")
    else:
        await msg.edit_text(f"❌ Failed to send email for {html_module.escape(str(lead['name']))}.")

@require_admin
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot statistics"""
    s = db.get_stats()
    
    lines = [
        "📊 *Bot Statistics*\n",
        f"🏪 Restaurants scanned: {s['restaurants']}",
        f"🎯 Total leads: {s['leads']}",
        f"📧 Emailed: {s['emailed']}",
        f"💲 Sold: {s['sold']}",
        "",
        f"⚡ Rate: {int(s['sold']/max(s['emailed'],1)*100) if s['emailed'] else 0}% conversion",
    ]
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@require_admin
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# === CALLBACK HANDLER ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "scan_all":
        msg = await query.message.reply_text("🔍 Full scan starting...")
        total = await asyncio.to_thread(scan_all_houston)
        await msg.edit_text(f"✅ Scan complete! {total} new leads.")
    
    elif data == "stats":
        s = db.get_stats()
        await query.message.reply_text(
            f"📊 *Stats:* {s['restaurants']} restaurants, {s['leads']} leads, {s['emailed']} emailed, {s['sold']} sold",
            parse_mode="Markdown"
        )
    
    elif data == "list_leads":
        results = db.get_leads(limit=10)
        if not results:
            await query.message.reply_text("No leads yet.")
            return
        lines = ["🎯 *Leads:*\n"]
        for r in results:
            lines.append(f"`{r['id']}` — *{html_module.escape(str(r['name']))}* — {'📧' if r['emailed'] else '📭'} {'💲' if r['sold'] else ''}")
        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    elif data.startswith("lead_"):
        lead_id = int(data.split("_")[1])
        leads = db.get_leads(limit=100)
        lead = next((l for l in leads if l["id"] == lead_id), None)
        if lead:
            lines = [
                f"📋 *Lead #{lead['id']}*\n",
                f"🏪 *{html_module.escape(str(lead['name']))}*",
                f"📍 {lead['address'] or 'N/A'}",
                f"📞 {lead['phone'] or 'N/A'}",
                f"⭐ {lead['rating'] or 'N/A'}",
                f"Status: {lead['status']}",
            ]
            keyboard = [
                [InlineKeyboardButton("🖥️ Generate", callback_data=f"gen_{lead['id']}")],
                [InlineKeyboardButton("📧 Email", callback_data=f"email_{lead['id']}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="list_leads")]
            ]
            await query.message.reply_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif data.startswith("gen_"):
        lead_id = int(data.split("_")[1])
        leads = db.get_leads(limit=100)
        lead = next((l for l in leads if l["id"] == lead_id), None)
        if lead:
            context.args = [str(lead_id)]
            await generate(update, context)
    
    elif data.startswith("email_"):
        lead_id = int(data.split("_")[1])
        context.args = [str(lead_id)]
        await email_lead(update, context)
    
    elif data.startswith("preview_"):
        lead_id = int(data.split("_")[1])
        context.args = [str(lead_id)]
        await preview(update, context)
    
    elif data.startswith("marksent_"):
        lead_id = int(data.split("_")[1])
        from datetime import datetime
        db.update_lead(lead_id, emailed=1, email_sent_at=datetime.now().isoformat(), status="emailed")
        await query.message.edit_text(f"✅ Marked lead #{lead_id} as emailed.")

# === MAIN ===
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return
    
    db.init_db()
    print("🏪 Restaurant AI Bot starting...")
    print(f"👤 Admin user ID: {ADMIN_USER_IDS}")
    print(f"📍 {len(HOUSTON_AREAS)} Houston scan areas configured")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("areas", areas))
    app.add_handler(CommandHandler("leads", leads))
    app.add_handler(CommandHandler("lead", lead_detail))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("preview", preview))
    app.add_handler(CommandHandler("email", email_lead))
    app.add_handler(CommandHandler("stats", stats))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 Bot running! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
