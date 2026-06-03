"""Restaurant website generator with protection system"""
import uuid
import hashlib
import time
from datetime import datetime, timedelta
import os

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

def generate_token(restaurant_id, lead_id):
    """Generate unique token for protected demo access"""
    raw = f"{restaurant_id}-{lead_id}-{uuid.uuid4()}-{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def generate_restaurant_html(name, address="", phone="", cuisine="", rating=None, 
                             menu_items=None, hours=None, lead_id=0, restaurant_id=0,
                             watermark=True):
    """Generate a complete restaurant website with protection layers"""
    token = generate_token(restaurant_id, lead_id)
    
    menu_html = ""
    if menu_items:
        for item in menu_items:
            menu_html += f"""
            <div class="menu-item">
                <div class="menu-item-info">
                    <h3 class="menu-item-name">{item.get('name', 'Item')}</h3>
                    <p class="menu-item-desc">{item.get('desc', '')}</p>
                </div>
                <span class="menu-item-price">${item.get('price', '0.00')}</span>
            </div>"""
    else:
        menu_html = '<p class="menu-placeholder">Menu available upon visit.</p>'
    
    hours_html = ""
    if hours:
        for day, time_slot in hours.items():
            hours_html += f"""
            <div class="hours-row">
                <span class="hours-day">{day}</span>
                <span class="hours-time">{time_slot}</span>
            </div>"""
    
    rating_html = f'★ {rating}' if rating else ''
    cuisine_id = cuisine.lower().replace(' ', '-')[:20] if cuisine else 'restaurant'
    safe_name = name.replace("'", "\\'").replace('"', '&quot;')
    
    # Phone cleanup
    phone_digits = ''.join(filter(str.isdigit, phone)) if phone else ""
    phone_display = phone if phone else "(713) 555-XXXX"
    
    watermark_overlay = ""
    if watermark:
        watermark_overlay = """
        <!-- PROTECTION: Watermark overlay -->
        <div class="demo-watermark" aria-hidden="true">
            <div class="demo-watermark-inner">
                <span>PROTOCOL</span>
                <span>DEMO</span>
                <span>PREVIEW</span>
            </div>
        </div>"""
    
    # Current year for copyright
    year = datetime.now().year
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{safe_name} | Houston, TX</title>
    <meta name="description" content="{safe_name} — {cuisine or 'restaurant'} in Houston, Texas. Order takeout online.">
    <meta name="robots" content="noindex, nofollow">
    <style>
    /* === PROTECTION: Prevent selection, drag, and print === */
    * {{ -webkit-user-select: none !important; user-select: none !important; -webkit-user-drag: none !important; }}
    body {{ -webkit-touch-callout: none; }}
    @media print {{ body {{ display: none !important; }} }}
    
    /* === PROTECTION: Screenshot deterrent === */
    .demo-watermark {{
        position: fixed; inset: 0; pointer-events: none; z-index: 9999;
        display: flex; align-items: center; justify-content: center;
        opacity: 0.04; transform: rotate(-25deg) scale(1.5);
    }}
    .demo-watermark-inner {{
        font-size: 3rem; font-weight: 900; letter-spacing: 0.3em;
        color: #888; text-align: center; line-height: 1.8;
        font-family: system-ui, sans-serif;
    }}
    .demo-watermark-inner span {{ display: block; }}
    
    /* === STYLES === */
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    html{{scroll-behavior:smooth}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#fafafa;color:#333;line-height:1.6;overflow-x:hidden}}
    .container{{max-width:1100px;margin:0 auto;padding:0 20px}}
    
    /* Hero */
    .hero{{background:linear-gradient(135deg,#1a1a1a,#2a2a2a);color:#fff;padding:80px 0 60px;text-align:center;position:relative}}
    .hero h1{{font-size:clamp(2rem,5vw,3.2rem);font-weight:800;margin-bottom:8px;letter-spacing:-0.02em}}
    .hero-tagline{{font-size:1.1rem;color:#aaa;margin-bottom:24px}}
    .hero-badge{{display:inline-flex;gap:20px;flex-wrap:wrap;justify-content:center;font-size:0.9rem;color:#ccc}}
    .hero-badge span{{display:flex;align-items:center;gap:6px}}
    .hero-badge a{{color:#f0c040;text-decoration:none;font-weight:600}}
    .hero-badge a:hover{{text-decoration:underline}}
    
    /* Order bar */
    .order-bar{{background:#f0c040;color:#1a1a1a;padding:14px 0;text-align:center;font-weight:700;font-size:1.05rem;position:sticky;top:0;z-index:100}}
    .order-bar a{{color:#1a1a1a;text-decoration:none}}
    .phone-btn{{display:inline-flex;align-items:center;gap:8px;background:#1a1a1a;color:#f0c040!important;padding:10px 24px;border-radius:100px;font-weight:700;font-size:0.95rem;margin-left:12px;transition:all 0.3s;text-decoration:none!important}}
    .phone-btn:hover{{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}}
    
    /* Menu section */
    .menu-section{{padding:60px 0;background:#fff}}
    .section-title{{font-size:1.8rem;font-weight:700;margin-bottom:8px;text-align:center}}
    .section-sub{{color:#888;text-align:center;margin-bottom:40px}}
    .menu-grid{{max-width:700px;margin:0 auto}}
    .menu-item{{display:flex;justify-content:space-between;padding:16px 0;border-bottom:1px solid #eee;gap:16px}}
    .menu-item:last-child{{border-bottom:0}}
    .menu-item-name{{font-size:1rem;font-weight:600;margin-bottom:4px}}
    .menu-item-desc{{font-size:0.85rem;color:#888;line-height:1.4}}
    .menu-item-price{{font-weight:700;white-space:nowrap;flex-shrink:0}}
    .menu-placeholder{{text-align:center;color:#aaa;font-style:italic;padding:20px}}
    
    /* Hours */
    .hours-section{{padding:60px 0;background:#f5f5f0}}
    .hours-card{{max-width:400px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 12px rgba(0,0,0,0.06)}}
    .hours-row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:0.9rem}}
    .hours-row:last-child{{border-bottom:0}}
    .hours-day{{font-weight:500}}
    .hours-time{{color:#555}}
    
    /* Contact */
    .contact-section{{padding:60px 0;background:#1a1a1a;color:#fff;text-align:center}}
    .contact-section a{{color:#f0c040;text-decoration:none;font-size:1.3rem;font-weight:600}}
    .contact-section a:hover{{text-decoration:underline}}
    .contact-address{{color:#888;margin-top:8px;font-size:0.9rem}}
    
    /* Footer */
    .footer{{padding:24px 0;background:#0d0d0d;color:#555;text-align:center;font-size:0.8rem}}
    .footer .demo-note{{color:#f0c040;margin-top:8px;font-size:0.75rem;letter-spacing:0.05em}}
    
    /* PROTECTION: Anti-screenshot overlay */
    #protect-overlay{{position:fixed;inset:0;z-index:9998;pointer-events:none;background:transparent;display:none}}
    @media(max-width:768px){{.hero h1{{font-size:1.8rem}}.phone-btn{{display:block;margin:12px auto 0;width:fit-content}}}}
    </style>
</head>
<body>

{watermark_overlay}

<div id="protect-overlay"></div>

<!-- PROTECTION: Invisible canvas that blocks screenshot tools -->
<canvas id="protect-canvas" style="display:none"></canvas>

<section class="hero">
    <div class="container">
        <h1>{safe_name}</h1>
        <p class="hero-tagline">{cuisine or 'Houston Restaurant'} · {address or 'Houston, TX'}</p>
        <div class="hero-badge">
            <span>⭐ {rating_html or 'New'}</span>
            <span>📍 {address or 'Houston, TX'}</span>
        </div>
    </div>
</section>

<div class="order-bar">
    <span>📞 Call to Order Takeout</span>
    <a href="tel:{phone_digits}" class="phone-btn">{phone_display} →</a>
</div>

<section class="menu-section" id="menu">
    <div class="container">
        <h2 class="section-title">Our Menu</h2>
        <p class="section-sub">Fresh. Local. Made to order.</p>
        <div class="menu-grid">
            {menu_html}
        </div>
    </div>
</section>

<section class="hours-section" id="hours">
    <div class="container">
        <h2 class="section-title" style="margin-bottom:32px">Hours</h2>
        <div class="hours-card">
            {hours_html or '<div class="hours-row"><span>Call for hours</span></div>'}
        </div>
    </div>
</section>

<section class="contact-section" id="contact">
    <div class="container">
        <h2 style="font-weight:300;margin-bottom:16px;font-size:1.2rem;color:#888">Order Takeout</h2>
        <a href="tel:{phone_digits}">{phone_display}</a>
        <p class="contact-address">{address or 'Houston, TX'}</p>
    </div>
</section>

<footer class="footer">
    <div class="container">
        <p>© {year} {safe_name}. All rights reserved.</p>
        <p class="demo-note">🔒 Demo Preview — Site powered by AI</p>
    </div>
</footer>

<script>
(function() {{
    // === PROTECTION: Block right click ===
    document.addEventListener('contextmenu', e => e.preventDefault());
    
    // === PROTECTION: Block common screenshot keys ===
    document.addEventListener('keydown', e => {{
        // PrtScn, Cmd+Shift+3/4/5, Ctrl+Shift+S
        if (e.key === 'PrintScreen' ||
            (e.metaKey && e.shiftKey && ['3','4','5'].includes(e.key)) ||
            (e.ctrlKey && e.shiftKey && e.key === 'S')) {{
            e.preventDefault();
        }}
    }});
    
    // === PROTECTION: Block drag-to-copy ===
    document.addEventListener('dragstart', e => e.preventDefault());
    document.addEventListener('copy', e => e.preventDefault());
    
    // === PROTECTION: Periodic overlay check ===
    setInterval(function() {{
        // Check if DevTools are open via element trick
        var x = document.createElement('div');
        Object.defineProperty(x, 'id', {{get: function() {{
            // DevTools detected - blur content
            document.body.style.filter = 'blur(12px)';
            setTimeout(function() {{ document.body.style.filter = ''; }}, 3000);
            return '';
        }}}});
        console.log(x);
    }}, 2000);

    // === PROTECTION: Block iframe embedding ===
    if (window.top !== window.self) {{
        document.body.innerHTML = '<h1 style="text-align:center;padding:100px 20px;color:#fff;background:#000">Content Protected</h1>';
    }}
}})();
</script>
</body>
</html>"""
    return html, token

def generate_with_sample_menu(name, address, phone, cuisine, rating, lead_id, restaurant_id):
    """Generate site with sample Houston-local menu items"""
    cuisine_lower = (cuisine or "").lower()
    
    # Generate menu based on cuisine type
    if "mexican" in cuisine_lower or "taco" in cuisine_lower or "taqueria" in cuisine_lower:
        menu = [
            {"name": "Street Tacos (3)", "desc": "Carne asada, cilantro, onion, salsa verde", "price": "9.99"},
            {"name": "Barbacoa Plate", "desc": "Slow-cooked beef, rice, beans, tortillas", "price": "13.99"},
            {"name": "Quesadilla Supreme", "desc": "Flour tortilla, Oaxaca cheese, mushrooms, epazote", "price": "11.49"},
            {"name": "Tortas de Milanesa", "desc": "Breaded chicken, avocado, crema, pickled jalapeños", "price": "10.99"},
            {"name": "Agua Fresca", "desc": "Jamaica or horchata — 32oz", "price": "3.50"},
        ]
    elif "vietnamese" in cuisine_lower or "pho" in cuisine_lower:
        menu = [
            {"name": "Pho Dac Biet", "desc": "Special combo pho with rare steak, brisket, meatballs", "price": "12.95"},
            {"name": "Banh Mi Thit Nuong", "desc": "Grilled pork sandwich, pickled daikon, cilantro", "price": "7.50"},
            {"name": "Bun Cha Gio", "desc": "Vermicelli noodles, egg rolls, fish sauce", "price": "10.95"},
            {"name": "Spring Rolls (4)", "desc": "Fresh shrimp, vermicelli, peanut dipping sauce", "price": "6.50"},
            {"name": "Vietnamese Iced Coffee", "desc": "Cà phê sữa đá — traditional drip", "price": "4.50"},
        ]
    elif "chinese" in cuisine_lower:
        menu = [
            {"name": "General Tso Chicken", "desc": "Crispy battered chicken, sweet chili glaze", "price": "11.95"},
            {"name": "Mapo Tofu", "desc": "Silken tofu, Sichuan peppercorn, ground pork", "price": "10.95"},
            {"name": "Fried Rice Combo", "desc": "Choice of chicken, pork, or shrimp", "price": "9.95"},
            {"name": "Dumplings (8)", "desc": "Handmade pork and chive, soy dipping sauce", "price": "8.50"},
            {"name": "Egg Drop Soup", "desc": "Silky broth, scallions, crispy wontons", "price": "4.50"},
        ]
    elif "pizza" in cuisine_lower or "italian" in cuisine_lower:
        menu = [
            {"name": "Margherita Pizza (12\")", "desc": "San Marzano tomatoes, fresh mozzarella, basil", "price": "13.99"},
            {"name": "Pepperoni Pizza (12\")", "desc": "House-made pepperoni, mozzarella, oregano", "price": "14.99"},
            {"name": "Pasta Alfredo", "desc": "Fettuccine, cream, parmesan, garlic bread", "price": "11.99"},
            {"name": "Caesar Salad", "desc": "Romaine, house dressing, croutons, parmesan", "price": "7.99"},
            {"name": "Tiramisu", "desc": "Classic Italian dessert — made fresh daily", "price": "5.50"},
        ]
    elif "burger" in cuisine_lower or "sandwich" in cuisine_lower or "american" in cuisine_lower:
        menu = [
            {"name": "Classic Burger", "desc": "Angus beef, lettuce, tomato, onion, secret sauce", "price": "10.99"},
            {"name": "Texas BBQ Bacon Burger", "desc": "Thick-cut bacon, cheddar, onion rings, BBQ", "price": "13.49"},
            {"name": "Grilled Chicken Sandwich", "desc": "Marinated chicken breast, avocado, ciabatta", "price": "11.49"},
            {"name": "Hand-Cut Fries", "desc": "Seasoned, crispy, served with ranch", "price": "4.49"},
            {"name": "Milkshake", "desc": "Vanilla, chocolate, or strawberry — 16oz", "price": "5.99"},
        ]
    elif "seafood" in cuisine_lower or "crawfish" in cuisine_lower or "gumbo" in cuisine_lower:
        menu = [
            {"name": "Crawfish Boil (lb)", "desc": "Seasoned crawfish, corn, potatoes, sausage", "price": "11.99"},
            {"name": "Fried Shrimp Basket", "desc": "Gulf shrimp, fries, coleslaw, cocktail sauce", "price": "13.99"},
            {"name": "Gumbo Bowl", "desc": "Chicken and sausage gumbo, white rice", "price": "8.99"},
            {"name": "Grilled Redfish", "desc": "Fresh catch, lemon butter, seasonal vegetables", "price": "16.99"},
            {"name": "Po'boy Combo", "desc": "Fried shrimp or oyster, dressed, fries", "price": "12.49"},
        ]
    elif "bbq" in cuisine_lower or "grill" in cuisine_lower:
        menu = [
            {"name": "Brisket Plate (1/2 lb)", "desc": "Oak-smoked 14 hours, house BBQ sauce", "price": "14.99"},
            {"name": "Rib Plate (1/2 rack)", "desc": "St. Louis style, dry-rubbed, glaze", "price": "15.99"},
            {"name": "Sausage Link", "desc": "House-made jalapeño cheddar sausage", "price": "5.99"},
            {"name": "Loaded Baked Potato", "desc": "Brisket, cheese, sour cream, green onions", "price": "9.99"},
            {"name": "Banana Pudding", "desc": "Southern-style, vanilla wafers, meringue", "price": "4.99"},
        ]
    else:
        menu = [
            {"name": "House Special", "desc": "Chef's daily creation — ask your server", "price": "12.99"},
            {"name": "Grilled Plate", "desc": "Choice of protein, rice, seasonal vegetables", "price": "11.99"},
            {"name": "Fresh Salad", "desc": "Mixed greens, tomato, cucumber, house vinaigrette", "price": "7.99"},
            {"name": "Soup of the Day", "desc": "Made fresh each morning", "price": "4.99"},
            {"name": "Daily Dessert", "desc": "Ask about today's selection", "price": "5.49"},
        ]
    
    default_hours = {
        "Monday": "10:00 AM — 9:00 PM",
        "Tuesday": "10:00 AM — 9:00 PM",
        "Wednesday": "10:00 AM — 9:00 PM",
        "Thursday": "10:00 AM — 9:00 PM",
        "Friday": "10:00 AM — 10:00 PM",
        "Saturday": "9:00 AM — 10:00 PM",
        "Sunday": "11:00 AM — 8:00 PM",
    }
    
    return generate_restaurant_html(
        name=name, address=address, phone=phone, cuisine=cuisine,
        rating=rating, menu_items=menu, hours=default_hours,
        lead_id=lead_id, restaurant_id=restaurant_id, watermark=True
    )
