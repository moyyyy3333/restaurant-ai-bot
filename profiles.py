"""Name-aware sample copy for generated demos.

Bulk regen uses use_ai=False, so taglines and menus must come from the
business name — not one House Specialty list for every restaurant.
"""

import re
import zlib

# (title, desc, sample_price_int). Prices are labeled sample in the page;
# never emit $x.xx (that reads as a real menu).
PROFILES = {
    "pho": {
        "tagline": "A bowl that tastes like home.",
        "label": "phở restaurant",
        "atmosphere": "Broth, herbs, and a table that turns over.",
        "theme_cat": "restaurant", "family": "supper",
        "offer_kicker": "The bowls",
        "items": [
            ("Phở đặc biệt", "Ask about today's broth", 14),
            ("Phở gà", "Chicken, when you want it lighter", 13),
            ("Bún", "Noodles beyond the bowl", 13),
            ("Spring rolls", "Fresh or fried", 8),
            ("Cà phê sữa", "If we have it on", 5),
        ],
    },
    "crepe": {
        "tagline": "Batter, butter, and whatever's in season.",
        "label": "crêperie",
        "atmosphere": "Folded to order — savory or sweet.",
        "theme_cat": "restaurant", "family": "supper",
        "offer_kicker": "On the griddle",
        "items": [
            ("Savory crepe", "Ham, cheese, or the day's mix", 13),
            ("Sweet crepe", "Sugar, fruit, or chocolate", 11),
            ("Galette", "Buckwheat, when we have it", 14),
            ("Cidre or coffee", "With the crepe", 4),
            ("Seasonal special", "Ask the counter", 12),
        ],
    },
    "pizza": {
        "tagline": "A pie worth crossing town for.",
        "label": "pizzeria",
        "atmosphere": "A square pie, a cold drink, a booth.",
        "theme_cat": "restaurant", "family": "supper",
        "offer_kicker": "The pies",
        "items": [
            ("House pie", "Ask what's on tonight", 18),
            ("Pepperoni", "The one people reorder", 17),
            ("White pie", "No red sauce", 18),
            ("Salad", "A plate that isn't pizza", 9),
            ("By the slice", "When we have it", 5),
        ],
    },
    "taco": {
        "tagline": "Tortillas, salsa, and a line out the door.",
        "label": "taquería",
        "atmosphere": "Tortillas on the plancha, salsa to taste.",
        "theme_cat": "restaurant", "family": "supper",
        "offer_kicker": "From the plancha",
        "items": [
            ("Street tacos", "Ask about today's meats", 4),
            ("Family platter", "Made for sharing", 22),
            ("Salsa bar", "Heat to taste", 0),
            ("Agua fresca", "When we have it", 4),
            ("Beans & rice", "On the side", 5),
        ],
    },
    "ice_cream": {
        "tagline": "Scoops, sundaes, and a reason to linger.",
        "label": "ice cream parlor",
        "atmosphere": "A cold case, a long counter, a little ceremony.",
        "theme_cat": "bakery", "family": "bakery",
        "reserve": False,
        "offer_kicker": "In the case",
        "items": [
            ("House scoop", "Rotating flavors", 6),
            ("Sundae", "Built to share", 9),
            ("Shake", "Ask about the blender", 8),
            ("Cone or cup", "Your call", 5),
            ("Seasonal", "When the case says so", 7),
        ],
    },
    "coffee": {
        "tagline": "Coffee, and a place to sit.",
        "label": "cafe",
        "atmosphere": "A quiet counter, a good cup, a place to sit.",
        "theme_cat": "cafe", "family": "cafe",
        "offer_kicker": "On the board",
        "items": [
            ("Espresso", "Single or double", 4),
            ("Pour over", "Rotating beans", 5),
            ("House drip", "All day", 3),
            ("Fresh pastry", "Baked each morning", 4),
            ("Seasonal drink", "Changes with the weather", 6),
        ],
    },
    "bbq": {
        "tagline": "Smoke, sauce, and brown paper.",
        "label": "barbecue",
        "atmosphere": "Smoke, sauce, and brown paper.",
        "theme_cat": "restaurant", "family": "supper",
        "offer_kicker": "On the pit",
        "items": [
            ("Brisket", "By the half-pound", 16),
            ("Ribs", "Ask about the tray", 18),
            ("Sausage", "On the plate or the sandwich", 8),
            ("Sides", "Whatever came off first", 5),
            ("Banana pudding", "If it's left", 6),
        ],
    },
    "bakery": {
        "tagline": "Warm from the oven.",
        "label": "bakery",
        "atmosphere": "Warm from the oven, gone by afternoon.",
        "theme_cat": "bakery", "family": "bakery",
        "offer_kicker": "In the case",
        "items": [
            ("Morning breads", "Out of the oven by 7", 7),
            ("Pastry case", "Changes daily", 5),
            ("Custom cakes", "Order ahead", 0),
            ("Cookies & slices", "By the piece", 3),
            ("Sandwich loaves", "Ask what's left", 8),
        ],
    },
    "banh_mi": {
        "tagline": "Bánh mì, phở, and a counter that moves.",
        "label": "bánh mì shop",
        "atmosphere": "A sandwich counter — bánh mì, a bowl if the pot is on.",
        "theme_cat": "restaurant", "family": "supper",
        "reserve": False,
        "offer_kicker": "From the counter",
        "items": [
            ("Bánh mì", "Ask what's on today", 8),
            ("Bánh mì đặc biệt", "The loaded one", 10),
            ("Phở", "When the pot is on", 12),
            ("Spring rolls", "Fresh or fried", 7),
            ("Cà phê sữa", "If we have it on", 4),
        ],
    },
    "wine_bar": {
        "tagline": "A glass, a cup, a place to stay.",
        "label": "cafe and wine bar",
        "atmosphere": "Wine by the glass, coffee when you want it.",
        "theme_cat": "cafe", "family": "cafe",
        "offer_kicker": "On the board",
        "items": [
            ("Wine by the glass", "Ask what's open", 12),
            ("Bottle list", "We can walk you through it", 0),
            ("Espresso", "If you want coffee", 4),
            ("Small plate", "Something to share", 14),
            ("Pastry", "When the case has it", 5),
        ],
    },
    "breakfast": {
        "tagline": "Breakfast plates until the afternoon.",
        "label": "breakfast diner",
        "atmosphere": "Eggs, coffee, and a plate before the dinner hour.",
        "theme_cat": "restaurant", "family": "supper",
        "offer_kicker": "On the plate",
        "items": [
            ("Breakfast plate", "Eggs and the usual sides", 12),
            ("Pancakes or french toast", "When you want sweet", 11),
            ("Breakfast taco or sandwich", "On the go", 8),
            ("Lunch plate", "Until we close", 13),
            ("Coffee", "All morning", 3),
        ],
    },
    "sandwich": {
        "tagline": "A sandwich worth the stop.",
        "label": "sandwich shop",
        "atmosphere": "Built to order — bread, a filling, out the door.",
        "theme_cat": "restaurant", "family": "supper",
        "reserve": False,
        "offer_kicker": "On the board",
        "items": [
            ("House sandwich", "Ask what's on", 10),
            ("Hot sandwich", "Off the press", 11),
            ("Cold cut", "The usual build", 9),
            ("Soup", "When the pot is on", 6),
            ("Chips or a side", "With the sandwich", 3),
        ],
    },
}

# Generic restaurant variants so two unnamed kitchens don't share a menu.
_RESTAURANT_VARIANTS = (
    {
        "tagline": "A table in the neighborhood.",
        "items": [
            ("Seasonal plates", "Changes with the market", 22),
            ("Tonight's roast", "Ask about the cut", 26),
            ("Garden plate", "When you want something lighter", 16),
            ("Daily soup", "The kitchen's call", 9),
            ("Something sweet", "Ask what's on", 10),
        ],
    },
    {
        "tagline": "Cooked like someone is waiting for you.",
        "items": [
            ("Grill", "From the fire", 24),
            ("Catch", "If the market had it", 28),
            ("Pasta or grains", "Ask the kitchen", 18),
            ("Share plate", "For the table", 14),
            ("House dessert", "When we have it", 11),
        ],
    },
    {
        "tagline": "Come hungry. Leave known.",
        "items": [
            ("Kitchen plate", "The cook's call", 21),
            ("Lunch service", "When the door is open", 15),
            ("Supper", "After dark", 24),
            ("Sides", "Ask what's up", 7),
            ("Coffee or tea", "To finish", 4),
        ],
    },
)

_RULES = (
    (re.compile(r"cream\s*parlor|ice\s*cream|gelato|frozen\s*custard|\bscoops?\b", re.I), "ice_cream"),
    (re.compile(r"crepe|crêpe|creperie|crêperie", re.I), "crepe"),
    (re.compile(r"via\s*313|via313|pizza|pizzeria|pizzería", re.I), "pizza"),
    (re.compile(r"taco|taqueria|taquería", re.I), "taco"),
    (re.compile(r"bbq|barbeque|barbecue", re.I), "bbq"),
    (re.compile(r"wine\s*bar|&\s*wine|winebar", re.I), "wine_bar"),
    (re.compile(r"coffee|espresso|roaster", re.I), "coffee"),
    (re.compile(r"bakery|bakehouse|patisserie|pâtisserie", re.I), "bakery"),
    (re.compile(r"\bdiner\b|\bbreakfast\b|\bbrunch\b", re.I), "breakfast"),
)

# Vietnamese name/type tokens — used with "sandwich" to pick bánh mì, not deli.
_VIET = re.compile(
    r"ph[oởóô]|vietnamese|bún|banh|\bviet\b|\bsaigon\b|\bhanoi\b|"
    r"\bthien\b|\bhuong\b|\bngon\b|\bphuong\b",
    re.I,
)
_SANDWICH = re.compile(r"sandwich", re.I)
_PHO = re.compile(r"ph[oởóô]|vietnamese|bún|banh\s*mi", re.I)
_GRILL = re.compile(r"\bgrill\b", re.I)
_BAR_AND_GRILL = re.compile(r"bar\s*(?:&|and)\s*grill", re.I)

_GENERIC_TITLES = {
    "house specialty", "family platter", "daily soup", "espresso", "pour over",
    "fresh pastry",
}


def _blob(name: str, extra: str = "") -> str:
    """Name plus Google types / display names, underscored types expanded."""
    bits = [name or "", (extra or "").replace("_", " ")]
    return " ".join(b for b in bits if b).strip()


def infer_cuisine(name: str, category: str = "restaurant", extra: str = "") -> str:
    """Cuisine from the business name, category, and optional Google type text.

    `extra` is primaryType / types / display names from Places — not invented.
    """
    text = _blob(name, extra)
    for rx, key in _RULES:
        if rx.search(text):
            return key
    if _SANDWICH.search(text) and _VIET.search(text):
        return "banh_mi"
    if _PHO.search(text):
        return "pho"
    if _SANDWICH.search(text):
        return "sandwich"
    if _GRILL.search(text) and not _BAR_AND_GRILL.search(text):
        return "breakfast"
    cat = (category or "restaurant").lower()
    if cat == "cafe":
        return "coffee"
    if cat == "bakery":
        return "bakery"
    if cat == "restaurant":
        return "restaurant"
    return cat


def profile_for(name: str, category: str = "restaurant", extra: str = "") -> dict:
    """Deterministic tagline + priced items for this business name."""
    cuisine = infer_cuisine(name, category, extra)
    if cuisine in PROFILES:
        out = dict(PROFILES[cuisine])
        out["cuisine"] = cuisine
        return out
    if (category or "") == "restaurant" or cuisine == "restaurant":
        idx = zlib.crc32((name or "").lower().encode()) % len(_RESTAURANT_VARIANTS)
        out = dict(_RESTAURANT_VARIANTS[idx])
        out["cuisine"] = "restaurant"
        return out
    return {"cuisine": cuisine, "tagline": "", "items": []}


def looks_generic(items) -> bool:
    titles = {str(t).strip().lower() for t, *_ in (items or [])}
    return len(titles & _GENERIC_TITLES) >= 2


FOOD_CATEGORIES = {"restaurant", "cafe", "bakery"}
TRADE_CATEGORIES = {
    "auto", "plumber", "electrician", "roofer", "locksmith",
    "barber", "salon", "gym", "dentist", "veterinary", "optician",
}
