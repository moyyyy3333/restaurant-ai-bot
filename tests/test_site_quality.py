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
from generator import generate_site

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


def test_hours_are_category_aware():
    assert "17:00" in HTML
    assert "07:00" in CAFE and "07:00" in BAKERY
    assert "Closed" in BAKERY and "Closed" in BARBER
    assert "By appointment" in LAWYER


def test_no_operator_email_on_public_cta():
    for page in (HTML, CAFE, BAKERY, BARBER, LAWYER):
        assert "mailto:" not in page
        assert "onboarding@resend.dev" not in page
        assert "reply to the email that brought you here" in page.lower()


def test_preview_chrome_is_in_claim_and_footer_only():
    assert 'class="wm"' not in HTML
    assert 'class="claimbar"' not in HTML
    assert "free unpublished sample" in HTML.lower()
    assert "sample layout — your real items" not in HTML.lower()
    assert "placeholder hours" not in HTML.lower()
    assert "placeholder details" not in HTML.lower()


def test_claim_shows_build_and_care_split():
    assert "$99" in HTML and "$29" in HTML and "$249" in HTML
    assert "builds the site" in HTML.lower() and "keeps it live" in HTML.lower()
    assert "$299" not in HTML and "$79" not in HTML
    # Build and Care must not share a single sentence/line.
    assert not re.search(r"\$99[^<.]{0,80}Care", HTML)
    assert not re.search(r"Care[^<.]{0,80}\$99", HTML)


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
    assert "Sample image" in pho and "hero-visual" in pho and 'class="photo"' in pho


def test_food_and_trade_ctas():
    assert 'href="#visit">Reserve</a>' in HTML
    assert 'href="#menu">Order</a>' in HTML
    assert 'href="#claim">Get a quote</a>' in BARBER
    assert 'href="#visit">Book</a>' in BARBER

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
