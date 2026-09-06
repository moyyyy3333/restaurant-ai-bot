"""The generated site must meet the quality bar in SPEC_accuracy_and_quality.md.

Run: ./venv/bin/python -m tests.test_site_quality
"""
import inspect
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BUSINESS_CATEGORIES, CATEGORY_THEMES, theme_for
from generator import SAMPLE, generate_site, human_address
from profiles import infer_cuisine

HTML, TOKEN = generate_site("Taqueria La Esquina", "1234 Navigation Blvd, Houston, TX",
                            "(713) 555-0142", "restaurant", 4.6, "houston", 1, 1,
                            use_ai=False)

CAFE, _ = generate_site("Morning Light Coffee", "812 Westheimer Rd, Houston, TX",
                        "(713) 555-0190", "cafe", 4.8, "houston", use_ai=False)
BAKERY, _ = generate_site("Hearth & Rye", "2101 Yale St, Houston, TX",
                         "(713) 555-0166", "bakery", 4.7, "houston", use_ai=False)
BARBER, _ = generate_site("East End Barber Co.", "401 Navigation Blvd, Houston, TX",
                         "(713) 555-0118", "barber", 4.9, "houston", use_ai=False)
LAWYER, _ = generate_site("Voss & Lane", "909 Fannin St, Houston, TX",
                         "(713) 555-0177", "lawyer", 4.5, "houston", use_ai=False)

def test_semantic_landmarks():
    for tag in ("<nav", "<header", "<main", "<footer", "<section"):
        assert tag in HTML, f"missing landmark {tag}"

def test_skip_link_and_focus_ring():
    assert 'class="skip"' in HTML, "no skip-to-content link"
    assert ":focus-visible" in HTML, "no visible focus ring"

def test_click_to_call_is_present_and_sticky_on_mobile():
    assert 'href="tel:7135550142"' in HTML, "phone not click-to-call"
    assert "callbar" in HTML, "no sticky mobile call bar"

def test_fluid_type_scale():
    assert HTML.count("clamp(") >= 5, "type/space not fluid"

def test_structured_data_is_valid_json():
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', HTML, re.S)
    assert m, "no LocalBusiness JSON-LD"
    data = json.loads(m.group(1))
    assert data["@type"] == "LocalBusiness" and data["name"]

def test_print_and_reduced_motion():
    assert "@media print" in HTML, "no print stylesheet"
    assert "prefers-reduced-motion" in HTML, "motion not gated"

def test_no_blocking_webfonts_or_frameworks():
    assert "fonts.googleapis" not in HTML, "blocking web font"
    assert "<script src=" not in HTML, "external script on a static page"

def test_honest_about_being_a_sample():
    low = HTML.lower()
    assert "sample" in low and "not affiliated" in low

def test_no_invented_prices():
    # Prices must never be fabricated for a business we do not know.
    assert not re.search(r"\$\d+\.\d{2}", HTML), "fabricated menu prices"


def test_generate_site_signature_unchanged():
    params = list(inspect.signature(generate_site).parameters)
    assert params == [
        "name", "address", "phone", "category", "rating", "city",
        "lead_id", "business_id", "watermark", "use_ai",
        "hours", "place_types", "fetch_place",
    ]


def test_every_category_has_its_own_theme():
    assert set(CATEGORY_THEMES) == set(BUSINESS_CATEGORIES)
    families = {theme_for(c)["family"] for c in BUSINESS_CATEGORIES}
    assert families >= {"supper", "cafe", "bakery", "chair", "practice"}


def test_categories_are_not_one_skin():
    assert 'data-family="supper"' in HTML
    assert 'data-family="cafe"' in CAFE
    assert 'data-family="bakery"' in BAKERY
    assert 'data-family="chair"' in BARBER
    assert 'data-family="practice"' in LAWYER
    assert 'class="mono"' in HTML
    assert 'class="ticket"' in CAFE
    assert 'class="case"' in BAKERY
    assert 'class="nums"' in BARBER
    assert 'class="rules"' in LAWYER
    assert HTML.split("<style>")[1].split("</style>")[0] != CAFE.split("<style>")[1].split("</style>")[0]


def test_hours_are_not_invented():
    """Theme hours (dinner 17:00, cafe 07:00) must not appear unless passed in."""
    for page in (HTML, CAFE, BAKERY, BARBER, LAWYER):
        assert "17:00" not in page
        assert "07:00 – 17:00" not in page
        assert ">Hours</h3>" not in page
        assert "placeholder hours" not in page.lower()


def test_real_hours_render_when_provided():
    html, _ = generate_site(
        "Yale Street Grill", "2100 Yale Street, Houston, TX",
        "(713) 861-3113", "restaurant", 4.4, "houston", use_ai=False,
        hours=[("Mon – Sat", "7:00 AM – 4:30 PM"), ("Sunday", "7:00 AM – 5:00 PM")],
    )
    assert ">Hours</h3>" in html
    assert "7:00 AM – 4:30 PM" in html
    assert "17:00" not in html
    assert "5:00 PM" in html


def test_no_operator_email_on_public_cta():
    for page in (HTML, CAFE, BAKERY, BARBER, LAWYER):
        assert "mailto:" not in page
        assert "onboarding@resend.dev" not in page
        assert "reply to the email that brought you here" in page.lower()


def test_preview_chrome_is_in_claim_and_footer_only():
    assert 'class="wm"' not in HTML
    assert 'class="claimbar"' not in HTML
    assert "free unpublished sample" in HTML.lower()
    assert "unpublished sample" in HTML.lower()
    assert "Preview " not in HTML
    assert "sample layout — your real items" not in HTML.lower()
    assert "placeholder hours" not in HTML.lower()
    assert "placeholder details" not in HTML.lower()
    assert "Sample image" not in HTML
    assert "your photos go here" not in HTML.lower()


def test_claim_shows_build_and_care_split():
    assert "$99" in HTML and "$29" in HTML and "$249" in HTML
    assert "<strong>$99</strong> one-time — we finish your menu, hours, and photos." in HTML
    assert "<strong>Care $29/mo</strong> (or <strong>$249/yr</strong>) —" in HTML
    assert "so it stays live" in HTML
    assert "$99 builds it. Care keeps it live. Reply to claim." in HTML
    assert "$299" not in HTML and "$79" not in HTML


def test_name_aware_menus_are_not_universal():
    pho, _ = generate_site("Simply Phở", "2929 Milam St, Houston, TX",
                           "(713) 555-0101", "restaurant", 4.6, "houston", use_ai=False)
    crepe, _ = generate_site("Melange Creperie", "1 Main St, Houston, TX",
                             "(713) 555-0102", "cafe", 4.5, "houston", use_ai=False)
    coffee, _ = generate_site("Revolucion Coffee", "2 Main St, Houston, TX",
                              "(713) 555-0103", "cafe", 4.7, "houston", use_ai=False)
    pizza, _ = generate_site("Via313", "3 Main St, Houston, TX",
                             "(713) 555-0104", "restaurant", 4.4, "houston", use_ai=False)
    cream, _ = generate_site("Cream Parlor", "4 Main St, Houston, TX",
                             "(713) 555-0105", "cafe", 4.8, "houston", use_ai=False)
    assert 'data-cuisine="pho"' in pho and "Phở" in pho
    assert "House Specialty" not in pho and "Daily Soup" not in pho
    assert 'data-family="supper"' in pho and 'data-family="supper"' in pizza
    assert 'data-cuisine="crepe"' in crepe and "crepe" in crepe.lower()
    assert "espresso" not in crepe.lower()
    assert "neighborhood cup" not in crepe.lower()
    assert "crêperie" in crepe.lower() or "creperie" in crepe.lower()
    assert 'data-family="supper"' in crepe and 'class="board"' not in crepe
    assert 'data-cuisine="coffee"' in coffee and "Espresso" in coffee
    assert 'data-family="cafe"' in coffee and 'class="board"' in coffee
    assert 'data-cuisine="pizza"' in pizza and "pie" in pizza.lower()
    assert "Family Platter" not in pizza and "Daily Soup" not in pizza
    assert 'data-cuisine="ice_cream"' in cream
    assert "Espresso" not in cream and "neighborhood cup" not in cream.lower()
    assert "quiet counter" not in cream.lower()
    assert "ice cream parlor" in cream.lower()
    assert 'data-family="bakery"' in cream and 'class="case"' in cream
    assert 'data-family="cafe"' not in cream
    assert "Sample image" not in pho
    assert "your photos go here" not in pho.lower()
    assert 'class="hero-visual"' not in pho
    assert 'aria-label="Sample image"' not in pho


def test_infer_cuisine_tokens():
    assert infer_cuisine("Yale Street Grill") == "breakfast"
    assert infer_cuisine("Thien An Sandwiches") == "banh_mi"
    assert infer_cuisine("Apothecary Cafe & Wine Bar", "cafe") == "wine_bar"
    assert infer_cuisine("Cream Parlor", "cafe") == "ice_cream"
    assert infer_cuisine("Joe's Sandwiches") == "sandwich"
    assert infer_cuisine("Joe's Bar & Grill") == "restaurant"
    assert infer_cuisine("Thien An", "restaurant", "vietnamese_restaurant") == "pho"
    assert infer_cuisine("Thien An Sandwiches", "restaurant",
                         "vietnamese_restaurant sandwich_shop") == "banh_mi"


def test_growth_accuracy_tokens():
    """The four live demos Growth scored — name/category must pick the right menu."""
    yale, _ = generate_site(
        "Yale Street Grill",
        "Yale Street Grill, 2100, Yale Street, Houston, TX",
        "(713) 861-3113", "restaurant", 4.4, "houston", use_ai=False)
    thien, _ = generate_site(
        "Thien An Sandwiches",
        "Thien An Sandwiches, 2611, San Jacinto Street, Houston, TX",
        "(713) 555-0108", "restaurant", 4.5, "houston", use_ai=False)
    apo, _ = generate_site(
        "Apothecary Cafe & Wine Bar",
        "Apothecary Cafe & Wine Bar, 4800, Burnet Road, Austin, TX",
        "(512) 555-0109", "cafe", 4.6, "austin", use_ai=False)
    cream, _ = generate_site(
        "Cream Parlor", "8216 Biscayne Boulevard, Miami, FL",
        "(305) 555-0110", "cafe", 4.8, "miami", use_ai=False)

    assert 'data-cuisine="breakfast"' in yale
    assert "Breakfast plate" in yale
    assert "Seasonal plates" not in yale
    assert "Tonight" not in yale
    assert "17:00" not in yale
    assert ">Hours</h3>" not in yale

    assert 'data-cuisine="banh_mi"' in thien
    assert "Bánh mì" in thien
    assert "Phở" in thien
    assert ">Grill</h3>" not in thien
    assert "Catch" not in thien
    assert "Pasta or grains" not in thien

    assert 'data-cuisine="wine_bar"' in apo
    assert "Wine by the glass" in apo
    assert "Espresso" in apo
    assert "Pour over" not in apo
    assert 'data-family="cafe"' in apo

    assert 'data-cuisine="ice_cream"' in cream
    assert "House scoop" in cream
    assert "Espresso" not in cream
    assert "quiet counter" not in cream.lower()
    assert 'data-family="bakery"' in cream


def test_generate_site_is_deterministic_per_name():
    a, _ = generate_site("Simply Phở", "2929 Milam St", "(713) 555-0101",
                         "restaurant", 4.6, "houston", use_ai=False)
    b, _ = generate_site("Simply Phở", "2929 Milam St", "(713) 555-0101",
                         "restaurant", 4.6, "houston", use_ai=False)
    c, _ = generate_site("Via313", "3 Main St", "(713) 555-0104",
                         "restaurant", 4.4, "houston", use_ai=False)
    titles = lambda h: re.findall(r"<h3>(.*?)</h3>", h)
    assert titles(a) == titles(b)
    assert titles(a) != titles(c)
    assert 'data-cuisine="pho"' in a and 'data-cuisine="pizza"' in c


def test_food_and_trade_ctas():
    assert 'href="#visit">Reserve</a>' in HTML
    assert 'href="#menu">Order</a>' in HTML
    assert 'href="#claim">Get a quote</a>' in BARBER
    assert 'href="#visit">Book</a>' in BARBER
    salon, _ = generate_site("Rose Atelier", "10 Main St", "(713) 555-0120",
                             "salon", 4.8, "houston", use_ai=False)
    plumber, _ = generate_site("Ace Plumbing", "11 Main St", "(713) 555-0121",
                               "plumber", 4.7, "houston", use_ai=False)
    assert 'href="#claim">Get a quote</a>' in salon
    assert 'href="#visit">Book</a>' in salon
    assert 'href="#claim">Get a quote</a>' in plumber
    assert "House Specialty" not in plumber and "Daily Soup" not in plumber


def test_human_address_drops_county_and_country():
    verbose = (
        "Yale Street Grill, 2100, Yale Street, Houston Heights, Houston, "
        "Harris County, Texas, 77008, United States"
    )
    assert human_address(verbose, name="Yale Street Grill", city="houston") == (
        "2100 Yale Street, Houston, TX 77008"
    )
    assert human_address(
        "2100 Yale St, Houston, TX 77008, USA", city="houston"
    ) == "2100 Yale St, Houston, TX 77008"
    # Already short — leave it alone.
    assert human_address("1234 Navigation Blvd, Houston, TX") == (
        "1234 Navigation Blvd, Houston, TX"
    )
    assert human_address("") == ""


def test_verbose_address_is_trimmed_on_the_page():
    raw = (
        "Cream Parlor, 8216, Biscayne Boulevard, Miami, Miami-Dade County, "
        "Florida, 33138, United States"
    )
    html, _ = generate_site(
        "Cream Parlor", raw, "(305) 555-0110", "cafe", 4.8, "miami", use_ai=False)
    shown = "8216 Biscayne Boulevard, Miami, FL 33138"
    assert shown in html
    where = re.search(r"<h3[^>]*>Where</h3>\s*<p>(.*?)</p>", html, re.S).group(1)
    assert where == shown
    assert "County" not in where and "United States" not in where
    facts = re.search(r"<dt>Find us</dt><dd>(.*?)</dd>", html).group(1)
    assert facts == shown
    # Map still geocodes the original OSM string.
    assert "Miami-Dade County" in html and "maps.google.com/maps?q=" in html


def test_cta_reserve_follows_vibe():
    """Counters: Order + Call. Sit-down / wine bar: keep Reserve."""
    cream, _ = generate_site("Cream Parlor", "4 Main St, Miami, FL",
                             "(305) 555-0110", "cafe", 4.8, "miami", use_ai=False)
    thien, _ = generate_site("Thien An Sandwiches", "2611 San Jacinto St, Houston, TX",
                             "(713) 555-0108", "restaurant", 4.5, "houston", use_ai=False)
    deli, _ = generate_site("Joe's Sandwiches", "5 Main St, Houston, TX",
                            "(713) 555-0111", "restaurant", 4.3, "houston", use_ai=False)
    yale, _ = generate_site("Yale Street Grill", "2100 Yale Street, Houston, TX",
                            "(713) 861-3113", "restaurant", 4.4, "houston", use_ai=False)
    apo, _ = generate_site("Apothecary Cafe & Wine Bar", "4800 Burnet Road, Austin, TX",
                           "(512) 555-0109", "cafe", 4.6, "austin", use_ai=False)
    for page in (cream, thien, deli):
        assert "Reserve" not in page
        assert 'href="#menu">Order</a>' in page
        assert ">Call</a>" in page
    assert 'href="#visit">Reserve</a>' in yale
    assert 'href="#visit">Reserve</a>' in apo
    assert 'href="#visit">Reserve</a>' in HTML


def test_every_local_category_has_its_own_sample():
    assert set(SAMPLE) == set(BUSINESS_CATEGORIES)
    for cat in BUSINESS_CATEGORIES:
        html, _ = generate_site(f"Sample {cat.title()}", "1 Main St",
                                "(713) 555-0100", cat, 4.5, "houston",
                                use_ai=False)
        assert f'data-category="{cat}"' in html
        if cat not in {"restaurant", "cafe", "bakery"}:
            assert "Daily Soup" not in html
            assert "House specialty" not in html

if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            try:
                f(); print(f"  ok  {n}")
            except AssertionError as e:
                fails += 1; print(f"  FAIL {n}: {e}")
    print("quality:", "ALL PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
