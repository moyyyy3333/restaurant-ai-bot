"""The bot may only claim 'no website' when a lookup actually said so.

Run: ./venv/bin/python -m tests.test_website_accuracy
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanner.scanner import classify_website, name_matches


def test_empty_url_is_unknown_when_nothing_answered():
    assert classify_website("", source_answered=False) == "unknown", \
        "no data source answered -> must NOT claim the business has no website"


def test_empty_url_is_none_only_when_a_source_answered():
    assert classify_website("", source_answered=True) == "none"


def test_social_is_not_a_website():
    assert classify_website("https://facebook.com/joes") == "social_only"


def test_real_site():
    assert classify_website("https://joescafe.com") == "has_site"


def test_name_match_accepts_same_business():
    assert name_matches("Sam's BBQ", "Sams BBQ")
    assert name_matches("The Original New Orleans Po-Boy", "Original New Orleans Po Boy Shop")


def test_name_match_rejects_a_different_business():
    assert not name_matches("Sam's BBQ", "Torchy's Tacos")
    assert not name_matches("Koko Cafe", "Starbucks")


def test_generic_words_alone_do_not_match():
    # "Cafe" vs "Cafe" must not be enough to accept a wrong result
    assert not name_matches("Koko Cafe", "Bluebird Cafe")


if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            try:
                f(); print(f"  ok  {n}")
            except AssertionError as e:
                fails += 1; print(f"  FAIL {n}: {e}")
    print("accuracy:", "ALL PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
