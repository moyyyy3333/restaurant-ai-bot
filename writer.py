"""
AI copywriting for demo sites, so each generated site gets copy written for
that specific business instead of the same three generic lines every business
in a category currently gets from generator.SAMPLE.

Tries providers in order and uses whichever is configured: direct Anthropic /
OpenAI / DeepSeek API call (just needs a key in .env, no install), then a
local Hermes CLI if none of those keys are set but Hermes happens to be on
this machine. Falls back to None on any failure — caller falls back to the
static SAMPLE content, so /generate never breaks because a provider is down
or unconfigured.
"""

import json
import re
import subprocess
import urllib.error
import urllib.request

from config import ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, OPENAI_API_KEY

TIMEOUT_S = 25

MOODS = ["classic", "minimal", "warm", "bold"]

PROMPT = """You are doing copy and light art direction for a one-page demo site for a
local {label} called "{name}"{city_clause}. You only know the name, category, and city —
nothing else about them, so go on what the name and category suggest about their vibe.

Reply with ONLY a JSON object, no markdown fences, no commentary:
{{"tagline": "...", "items": [{{"title": "...", "desc": "..."}}, {{"title": "...", "desc": "..."}}, {{"title": "...", "desc": "..."}}], "accent": "#rrggbb", "mood": "..."}}

Rules:
- tagline: one short line capturing the vibe of this kind of {label}, under 8 words.
- items: exactly 3 plausible service/menu highlights for a {label} — generic enough
  to not be a factual claim about this specific business (no invented prices, hours,
  or specific dish names presented as fact). Category of offering, not menu item.
- accent: one hex color that fits the name/vibe (not necessarily the obvious category
  default — a place called "Nightjar" reads differently than one called "Sunny Side").
- mood: exactly one of {moods} — pick whichever fits the name best.
- No emoji, no exclamation points. Plain, confident, human copy — not ad-speak.
"""


def _build_prompt(name: str, label: str, city: str) -> str:
    return PROMPT.format(
        label=label, name=name, moods=", ".join(MOODS),
        city_clause=f" in {city.title()}" if city else "")


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url, json.dumps(payload).encode(),
        {**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r)


def _call_anthropic(prompt: str) -> str | None:
    try:
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"model": "claude-haiku-4-5-20251001", "max_tokens": 500,
             "messages": [{"role": "user", "content": prompt}]},
            {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"})
        return data["content"][0]["text"]
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError):
        return None


def _call_openai_compatible(url: str, api_key: str, model: str, prompt: str) -> str | None:
    try:
        data = _post_json(
            url, {"model": model, "messages": [{"role": "user", "content": prompt}]},
            {"Authorization": f"Bearer {api_key}"})
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError):
        return None


def _call_hermes(prompt: str) -> str | None:
    try:
        result = subprocess.run(
            ["hermes", "-z", prompt, "--provider", "deepseek", "-m", "deepseek-chat"],
            capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    return result.stdout if result.returncode == 0 else None


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def write_copy(name: str, label: str, city: str = "") -> dict | None:
    """Returns {"tagline": str, "items": [(title, desc), ...] (3),
    "accent": "#rrggbb" or None, "mood": one of MOODS or None} or None."""
    prompt = _build_prompt(name, label, city)

    if ANTHROPIC_API_KEY:
        raw = _call_anthropic(prompt)
    elif OPENAI_API_KEY:
        raw = _call_openai_compatible(
            "https://api.openai.com/v1/chat/completions", OPENAI_API_KEY, "gpt-4o-mini", prompt)
    elif DEEPSEEK_API_KEY:
        raw = _call_openai_compatible(
            "https://api.deepseek.com/chat/completions", DEEPSEEK_API_KEY, "deepseek-chat", prompt)
    else:
        raw = _call_hermes(prompt)

    if not raw:
        return None

    data = _extract_json(raw)
    if not data or not isinstance(data.get("items"), list):
        return None
    items = [(str(i.get("title", "")).strip(), str(i.get("desc", "")).strip())
             for i in data["items"] if i.get("title") and i.get("desc")]
    if len(items) < 3:
        return None

    accent = data.get("accent")
    accent = accent if isinstance(accent, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else None
    mood = data.get("mood")
    mood = mood if mood in MOODS else None

    return {"tagline": str(data.get("tagline", "")).strip(), "items": items[:3],
            "accent": accent, "mood": mood}


if __name__ == "__main__":
    print(write_copy("Taqueria La Esquina", "restaurant", "houston"))
