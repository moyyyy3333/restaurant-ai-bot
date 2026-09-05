"""The generated site must meet the quality bar in SPEC_accuracy_and_quality.md.

Run: ./venv/bin/python -m tests.test_site_quality
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import generate_site

HTML, TOKEN = generate_site("Taqueria La Esquina", "1234 Navigation Blvd, Houston, TX",
                            "(713) 555-0142", "restaurant", 4.6, "houston", 1, 1,
                            use_ai=False)

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
