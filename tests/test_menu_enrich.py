"""Real-menu enrichment: parse structured sources, OCR when confident,
and never invent dishes as “real”.

Run: python3 -m tests.test_menu_enrich
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from menu_enrich import (
    MenuItem, MenuResult, _accept_page, _confident, _result_from_items,
    parse_html_menu, parse_jsonld_menu, parse_ocr_text, result_from_dict,
    source_for_url, strict_name_matches, url_names_business,
)
from profiles import infer_cuisine

YELP_LD = """
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Menu","name":"Thien-An Sandwiches Menu",
 "hasMenuSection":[{"@type":"MenuSection","name":"Banh Mi",
  "hasMenuItem":[
    {"@type":"MenuItem","name":"Banh Mi Ga","description":"shredded chicken",
     "offers":{"@type":"Offer","price":"7.50"}},
    {"@type":"MenuItem","name":"Banh Mi Dac Biet","description":"the special",
     "offers":{"@type":"Offer","price":"7.75"}},
    {"@type":"MenuItem","name":"Goi Cuon","description":"spring rolls",
     "offers":{"@type":"Offer","price":"6.50"}}
  ]}]}
</script>
"""

ROOST_HTML = """
<html><title>Yale Street Grill Menu - Houston, TX</title>
<table>
<tr><td><span class="cus-menu-text-name">Plain Omelette</span></td><td>$5.95</td></tr>
<tr><td><span class="cus-menu-text-name">Cheese Omelette</span></td><td>$6.95</td></tr>
<tr><td><span class="cus-menu-text-name">Mega Yale Cheeseburger</span><br />
<span>Two patties, American and Swiss</span></td><td>$10.95</td></tr>
<tr><td><span class="cus-menu-text-name">Malts &amp; Shakes</span></td><td>$4.95</td></tr>
</table>
</html>
"""

OCR_GOOD = """
YALE STREET GRILL
Plain Omelette ................ $5.95
Cheese Omelette ............... $6.95
Mega Yale Cheeseburger ........ $10.95
Malts & Shakes ................ $4.95
"""

OCR_GARBAGE = """
SWEET POTATO
GAs?
60
HAPPY
mt
9
"""


def test_jsonld_yelp_menu():
    items = parse_jsonld_menu(YELP_LD)
    names = [i.name for i in items]
    assert "Banh Mi Ga" in names
    assert items[0].price == 7.50
    assert _confident(items)


def test_html_roost_table():
    items = parse_html_menu(ROOST_HTML)
    by_name = {i.name: i for i in items}
    assert by_name["Plain Omelette"].price == 5.95
    assert by_name["Mega Yale Cheeseburger"].price == 10.95
    assert "Two patties" in by_name["Mega Yale Cheeseburger"].description
    assert _confident(items)


def test_ocr_requires_name_and_price():
    good = parse_ocr_text(OCR_GOOD)
    assert _confident(good)
    assert {i.name for i in good} >= {"Plain Omelette", "Mega Yale Cheeseburger"}
    bad = parse_ocr_text(OCR_GARBAGE)
    assert not _confident(bad)
    assert _result_from_items(bad, "https://example.com/menu.jpg", source="photo") is None


def test_source_labels_are_honest():
    assert source_for_url("https://www.yelp.com/menu/thien-an-sandwiches-houston") == "yelp"
    assert source_for_url("https://order.toasttab.com/online/shop") == "toast"
    assert source_for_url("https://place.square.site/menu") == "square"
    assert source_for_url("https://www.doordash.com/store/x") == "doordash"
    assert source_for_url("https://www.ubereats.com/store/x") == "ubereats"
    assert source_for_url("https://www.roostcafeandbistro.com/yale-street-grill-77008/") == "listing"
    assert source_for_url("https://yale-street-grill.res-pick.com/menu") == "listing"
    assert source_for_url("https://joes.example/menu") == "website"


def test_cream_parlor_is_not_hanks():
    assert not strict_name_matches("Cream Parlor", "Hank's Ice Cream Parlor Menu")
    assert not url_names_business(
        "Cream Parlor", "https://www.yelp.com/menu/hanks-ice-cream-parlor-houston")
    assert url_names_business(
        "Thien An Sandwiches",
        "https://www.yelp.com/menu/thien-an-sandwiches-houston")
    html = "<html><title>Hank's Ice Cream Parlor Menu</title><body>Banana Splits</body></html>"
    assert not _accept_page(
        "Cream Parlor", "https://www.yelp.com/menu/hanks-ice-cream-parlor-houston", html)
    assert _accept_page(
        "Yale Street Grill", "https://yale-street-grill.res-pick.com/menu", ROOST_HTML)


def test_hours_table_is_not_a_menu():
    html = """
    <title>Yale Street Grill</title>
    <table>
      <tr><td>Monday</td><td>7:00 AM – 4:30 PM</td></tr>
      <tr><td>Tuesday</td><td>7AM - 4:30PM</td></tr>
      <tr><td>Wednesday</td><td>7AM - 4:30PM</td></tr>
    </table>
    """
    items = parse_html_menu(html)
    assert not _confident(items)
    assert not any(i.name.lower() in {"monday", "tuesday"} for i in items)


def test_too_few_items_is_not_a_real_menu():
    items = [MenuItem("One dish", "x", 5), MenuItem("Two dish", "y", 6)]
    assert _result_from_items(items, "https://example.com", source="yelp") is None


def test_result_roundtrip():
    raw = {
        "source": "yelp",
        "source_url": "https://www.yelp.com/menu/x",
        "items": [
            {"name": "Banh Mi Ga", "description": "chicken", "price": 7.5},
            {"name": "Banh Mi Tofu", "description": "tofu", "price": 7.5},
            {"name": "Cha Gio", "description": "egg rolls", "price": 4.5},
        ],
    }
    got = result_from_dict(raw)
    assert isinstance(got, MenuResult)
    assert got.source_label == "from Yelp"
    assert len(got.items) == 3


def test_cuisine_fallbacks_for_prototypes():
    assert infer_cuisine("Thien An Sandwiches") == "banh_mi"
    assert infer_cuisine("Yale Street Grill") == "breakfast"
    assert infer_cuisine("Cream Parlor") == "ice_cream"
    assert infer_cuisine("Simply Phở") == "pho"


if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            try:
                f(); print(f"  ok  {n}")
            except AssertionError as e:
                fails += 1; print(f"  FAIL {n}: {e}")
    print("menu_enrich:", "ALL PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
