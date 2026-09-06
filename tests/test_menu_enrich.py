"""Menu enrich must fail closed and never invent dishes as real.

Run: python3 -m tests.test_menu_enrich
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import generate_site
from menu_enrich import (enrich_menu, parse_menu_html, parse_menu_text,
                         _looks_like_menu_or_order, _page_names_business,
                         _partner_menu_urls, _rank_urls, _CACHE)

GOTOEAT = """
<section>
  <div class="menu-item">
    <div class="menu-item-details">
      <div class="menu-item-desc">Banh Mi Ga</div>
      <div class="menu-item-prices"><div class="menu-item-price">US$2.50</div></div>
    </div>
    <p> shredded chicken breast </p>
  </div>
  <div class="menu-item">
    <div class="menu-item-details">
      <div class="menu-item-desc">Banh Mi Dac Biet</div>
      <div class="menu-item-prices"><div class="menu-item-price">US$7.75</div></div>
    </div>
    <p> special sandwich </p>
  </div>
  <div class="menu-item">
    <div class="menu-item-details">
      <div class="menu-item-desc">Pho Tai</div>
      <div class="menu-item-prices"><div class="menu-item-price">US$9.50</div></div>
    </div>
    <p> rare steak </p>
  </div>
  <a href="/menu">Full Menu</a>
  <a href="https://www.ubereats.com/store/thien-an-sandwiches/abc">Order</a>
</section>
"""

SINGLEPLATFORM = """
<div class="items">
  <div class="item left">
    <div class="item-title-row">
      <h4 class="item-title">Yogurt with Dried Cranberries</h4>
      <span class="price">$6.50</span>
    </div>
  </div>
  <div class="item left">
    <div class="item-title-row">
      <h4 class="item-title">House Scoop</h4>
      <span class="price">$4.25</span>
    </div>
  </div>
  <div class="item left">
    <div class="item-title-row">
      <h4 class="item-title">Ice Cream Sandwich</h4>
      <span class="price">$7.00</span>
    </div>
  </div>
</div>
"""

JSON_LD = """
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Menu","hasMenuItem":[
  {"@type":"MenuItem","name":"Brisket plate","description":"By the half-pound","offers":{"@type":"Offer","price":"16.00"}},
  {"@type":"MenuItem","name":"Ribs","description":"Ask about the tray","offers":{"price":18}},
  {"@type":"MenuItem","name":"Banana pudding","offers":{"price":"6"}}
]}
</script>
"""

TOAST_NEXT = """
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"menu":{"items":[
  {"name":"Avocado Toast","description":"On sourdough","price":11.5},
  {"name":"Latte","price":4.75},
  {"name":"Seasonal scone","price":3.5}
]}}}
}
</script>
"""


def setup_function():
    _CACHE.clear()


def test_parse_gotoeat_items():
    items = parse_menu_html(GOTOEAT, "https://thienansandwiches.gotoeat.net/menu")
    titles = [t for t, *_ in items]
    assert "Banh Mi Ga" in titles
    assert "Pho Tai" in titles
    prices = {t: p for t, _, p in items}
    assert prices["Banh Mi Ga"] == 2.5
    assert prices["Banh Mi Dac Biet"] == 7.75


def test_parse_singleplatform_items():
    items = parse_menu_html(SINGLEPLATFORM, "https://places.singleplatform.com/cream-parlor/menu")
    titles = [t for t, *_ in items]
    assert "House Scoop" in titles
    assert "Ice Cream Sandwich" in titles
    assert any(p == 6.5 for _, _, p in items)


def test_parse_json_ld_items():
    items = parse_menu_html(JSON_LD, "https://example.com/menu")
    titles = [t for t, *_ in items]
    assert titles == ["Brisket plate", "Ribs", "Banana pudding"]


def test_parse_toast_next_data():
    items = parse_menu_html(TOAST_NEXT, "https://order.toasttab.com/shop")
    titles = [t for t, *_ in items]
    assert "Avocado Toast" in titles
    assert "Latte" in titles


def test_ocr_text_lines():
    text = "Country breakfast  $9.50\nPancakes  $8\nCoffee  $3.00\nNot a dish\n"
    items = parse_menu_text(text)
    titles = [t for t, *_ in items]
    assert "Country breakfast" in titles
    assert "Pancakes" in titles
    assert "Coffee" in titles


def test_fail_closed_on_empty_or_thin_html():
    assert parse_menu_html("", "https://x.com") is None
    assert parse_menu_html("<html><body>Welcome</body></html>", "https://x.com") is None
    assert parse_menu_html("<div class='menu-item-desc'>Only one</div>"
                           "<div class='menu-item-price'>$5</div>", "https://x.com") is None
    assert parse_menu_text("hello") is None


def test_skip_instagram_login_wall():
    html = "<html><body>Log in to Instagram to see this</body></html>"
    assert parse_menu_html(html, "https://www.instagram.com/accounts/login/?next=/creamparlor/") is None


def test_discover_order_and_menu_links():
    assert _looks_like_menu_or_order("https://order.toasttab.com/shop/x", "Order")
    assert _looks_like_menu_or_order("https://place.square.site/", "")
    assert _looks_like_menu_or_order("https://shop.example.com/menu", "Menu")
    assert not _looks_like_menu_or_order("https://shop.example.com/about", "About")
    # Search must not treat a scraper /menu as theirs.
    assert not _looks_like_menu_or_order(
        "https://yale-street-grill.res-pick.com/menu", "menu", from_search=True)
    assert _looks_like_menu_or_order(
        "https://places.singleplatform.com/cream-parlor/menu", "", from_search=True)
    ranked = _rank_urls([
        "https://facebook.com/joes",
        "https://joes.example.com/",
        "https://order.toasttab.com/joes",
        "https://joes.example.com/menu",
        "https://www.ubereats.com/store/joes",
        "https://places.singleplatform.com/joes/menu",
    ])
    assert "toasttab.com" in ranked[0] or "singleplatform.com" in ranked[0]
    # Same host: /menu beats the homepage so we don't stop on a teaser list.
    ranked = _rank_urls([
        "https://thienansandwiches.gotoeat.net/",
        "https://thienansandwiches.gotoeat.net/menu",
    ])
    assert ranked[0].rstrip("/").endswith("/menu")


def test_enrich_follows_seed_and_fails_closed(monkeypatch=None):
    _CACHE.clear()
    pages = {
        "https://thienansandwiches.example/": {
            "url": "https://thienansandwiches.example/",
            "html": '<a href="https://thienansandwiches.example/menu">Full Menu</a>',
            "links": [("https://thienansandwiches.example/menu", "Full Menu")],
            "images": [],
            "ctype": "text/html",
        },
        "https://thienansandwiches.example/menu": {
            "url": "https://thienansandwiches.example/menu",
            "html": GOTOEAT,
            "links": [],
            "images": [],
            "ctype": "text/html",
        },
    }

    def fake_fetch(url, deadline):
        return pages.get(url)

    with patch("menu_enrich._fetch", side_effect=fake_fetch):
        got = enrich_menu("Thien An Sandwiches",
                          website="https://thienansandwiches.example/")
    assert got is not None
    assert got["source"] == "menu_page"
    assert any(t == "Banh Mi Ga" for t, *_ in got["items"])

    _CACHE.clear()
    with patch("menu_enrich._fetch", return_value=None):
        assert enrich_menu("No Site Cafe", website="https://blocked.example/") is None


def test_enrich_skips_blocked_photo():
    _CACHE.clear()
    page = {
        "url": "https://www.instagram.com/creamparlor/",
        "html": '<img src="https://cdn.example/menu.jpg" alt="menu">',
        "links": [],
        "images": [{"url": "https://cdn.example/menu.jpg", "alt": "today's menu"}],
        "ctype": "text/html",
    }
    with patch("menu_enrich._fetch", return_value=page), \
         patch("menu_enrich._items_from_public_image", return_value=None):
        assert enrich_menu("Cream Parlor", website="https://www.instagram.com/creamparlor/") is None


def test_generate_site_uses_sourced_items_and_marks_them():
    html, _ = generate_site(
        "Thien An Sandwiches", "2611 San Jacinto St, Houston, TX",
        "(713) 522-7007", "restaurant", 4.5, "houston", use_ai=False,
        menu_items=[("Bánh Mì Thịt Nướng", "Grilled pork sandwich", 7.5),
                    ("Bánh Mì Đặc Biệt", "The loaded one", 7.75),
                    ("Phở Tai", "Rare steak", 9.5)],
        menu_source={"source": "order_page", "url": "https://www.ubereats.com/store/thien-an",
                     "label": "From their order page"},
    )
    assert "Bánh Mì Thịt Nướng" in html
    assert "$7.50" in html and "$7.75" in html
    assert "From their order page" in html
    assert "not sample prices" in html
    assert "Sample prices —" not in html
    assert 'data-menu-source="order_page"' in html
    assert "ubereats.com" in html
    # Name-aware frame stays; we only swapped the list.
    assert 'data-cuisine="banh_mi"' in html
    assert "Bánh mì, phở, and a counter" in html
    assert "$99" in html and "Care $29/mo" in html
    assert "Sample image" not in html
    assert ">Hours</h3>" not in html


def test_generate_site_keeps_sample_when_enrich_fails():
    with patch("generator._lookup_menu", return_value=None):
        html, _ = generate_site(
            "Thien An Sandwiches", "2611 San Jacinto St, Houston, TX",
            "(713) 555-0108", "restaurant", 4.5, "houston", use_ai=False,
            fetch_place=True)
    assert "Bánh mì" in html
    assert "Sample prices —" in html
    assert 'data-menu-source="sample"' in html
    assert "From their order page" not in html
    assert "From their menu" not in html
    assert not __import__("re").search(r"\$\d+\.\d{2}", html)


def test_page_must_name_the_business():
    assert _page_names_business("Thien An Sandwiches",
                                "<title>Thien An Sandwiches | Houston</title>")
    assert not _page_names_business("Thien An Sandwiches",
                                    "<title>Torchy's Tacos Austin</title>")


def test_search_discovers_order_host_when_no_website():
    _CACHE.clear()
    menu = {
        "url": "https://thienansandwiches.gotoeat.net/menu",
        "html": "<title>Thien An Sandwiches menu</title>" + GOTOEAT,
        "links": [],
        "images": [],
        "ctype": "text/html",
    }
    with patch("menu_enrich._search_menu_urls",
               return_value=["https://thienansandwiches.gotoeat.net/menu"]), \
         patch("menu_enrich._fetch", return_value=menu), \
         patch("menu_enrich._places_website", return_value=""):
        got = enrich_menu("Thien An Sandwiches", "2611 San Jacinto St, Houston, TX")
    assert got is not None
    assert any(t == "Banh Mi Ga" for t, *_ in got["items"])
    assert got["source"] == "menu_page"


def test_partner_slug_is_conventional_singleplatform():
    assert _partner_menu_urls("Thien An Sandwiches") == [
        "https://places.singleplatform.com/thien-an-sandwiches/menu"]
    assert _partner_menu_urls("X") == []


def test_search_rejects_a_different_restaurant():
    _CACHE.clear()
    wrong = {
        "url": "https://order.toasttab.com/torchys",
        "html": "<title>Torchy's Tacos</title>" + GOTOEAT,
        "links": [],
        "images": [],
        "ctype": "text/html",
    }
    with patch("menu_enrich._search_menu_urls",
               return_value=["https://order.toasttab.com/torchys"]), \
         patch("menu_enrich._fetch", return_value=wrong), \
         patch("menu_enrich._places_website", return_value=""):
        assert enrich_menu("Thien An Sandwiches") is None


def test_never_marks_sample_as_real():
    html, _ = generate_site("Yale Street Grill", "2100 Yale Street, Houston, TX",
                            "(713) 861-3113", "restaurant", 4.4, "houston",
                            use_ai=False)
    assert 'data-menu-source="sample"' in html
    assert "Breakfast plate" in html
    assert "not sample prices" not in html


if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            try:
                setup_function()
                f()
                print(f"  ok  {n}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL {n}: {e}")
    print("menu_enrich:", "ALL PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
