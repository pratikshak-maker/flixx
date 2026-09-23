"""Claude-powered search brief generation and refinement.

Claude never calls TMDB itself. It reads both partners' structured choices
plus their free-text mood descriptions (and, for round 2, what they actually
swiped on) and returns a compact JSON "brief" — genre buckets, language/era
filters and a rating floor — that services/tmdb.py turns into a real query.
"""
from __future__ import annotations

import json
import re

import config
from services.tmdb import MOVIE_GENRES, TV_GENRES

_MOVIE_GENRE_KEYS = list(MOVIE_GENRES.keys())
_TV_GENRE_KEYS = list(TV_GENRES.keys())
_LANGUAGE_KEYS = ["hindi", "english", "tamil", "telugu", "kannada"]
_ERA_KEYS = ["classic", "2000_2020", "recent"]

_SCHEMA_HINT = f"""
Respond with ONLY a JSON object (no prose, no markdown fences) shaped exactly like:
{{
  "genres_movie": [subset of {_MOVIE_GENRE_KEYS}],
  "genres_tv": [subset of {_TV_GENRE_KEYS}],
  "languages": [subset of {_LANGUAGE_KEYS}] or [] for no constraint,
  "eras": [subset of {_ERA_KEYS}] or [] for no constraint,
  "min_vote_average": number between 0 and 10,
  "vibe_summary": "one or two sentences describing the shared vibe you're aiming for"
}}
""".strip()


def _client():
    from anthropic import Anthropic
    return Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _parse_json(text: str) -> dict:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


def _call(system: str, user: str) -> dict | None:
    if not config.HAS_CLAUDE:
        return None
    try:
        response = _client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return _parse_json(text)
    except Exception:
        return None


def _profile_blurb(label: str, profile: dict | None) -> str:
    if not profile:
        return f"{label}: (no preferences submitted)"
    return (
        f"{label}: mood={profile.get('mood')}, free_text=\"{profile.get('mood_text', '')}\", "
        f"languages={profile.get('languages')}, content_type={profile.get('content_type')}, "
        f"min_rating={profile.get('min_rating')}, eras={profile.get('eras')}"
    )


def generate_brief(profile_a: dict, profile_b: dict, history: dict | None = None) -> dict:
    history_blurb = ""
    if history and (history.get("liked") or history.get("disliked")):
        history_blurb = (
            f"\nThis couple's past history together: they both enjoyed {history.get('liked') or 'nothing yet'} "
            f"and both passed on {history.get('disliked') or 'nothing notable'}. Lean toward what they've "
            f"actually enjoyed together over what they merely said they'd like."
        )

    user = (
        "Two partners are picking something to watch together tonight. Synthesize their preferences into "
        "ONE shared search brief that would satisfy both of them — do not just average blindly, use judgment "
        "about what a couple with these two mood profiles would both genuinely enjoy.\n\n"
        f"{_profile_blurb('Partner A', profile_a)}\n{_profile_blurb('Partner B', profile_b)}"
        f"{history_blurb}\n\n{_SCHEMA_HINT}"
    )
    result = _call(
        "You are a movie/TV recommendation strategist. You output only strict JSON, nothing else.",
        user,
    )
    return result or heuristic_brief(profile_a, profile_b, history)


def refine_brief_round2(prior_brief: dict, profile_a: dict, profile_b: dict,
                         both_liked: list[str], both_passed: list[str],
                         single_liked: list[str]) -> dict:
    user = (
        "Round 1 of swiping just finished with no shared match. Refine the search brief to lean harder into "
        "what actually landed with both partners, and steer away from what both of them passed on.\n\n"
        f"Previous brief: {json.dumps(prior_brief)}\n"
        f"Titles BOTH partners liked: {both_liked or 'none'}\n"
        f"Titles only one partner liked: {single_liked or 'none'}\n"
        f"Titles BOTH partners passed on: {both_passed or 'none'}\n\n"
        f"{_profile_blurb('Partner A', profile_a)}\n{_profile_blurb('Partner B', profile_b)}\n\n"
        f"{_SCHEMA_HINT}"
    )
    result = _call(
        "You are a movie/TV recommendation strategist refining a search based on real swipe behavior. "
        "You output only strict JSON, nothing else.",
        user,
    )
    return result or prior_brief


_MOOD_TO_MOVIE_GENRES = {
    "light_fun": ["comedy", "family", "animation"],
    "intense_gripping": ["thriller", "drama", "action", "crime"],
    "scary": ["horror", "mystery"],
    "romantic": ["romance"],
}
_MOOD_TO_TV_GENRES = {
    "light_fun": ["comedy", "family", "animation"],
    "intense_gripping": ["drama", "crime", "action_adventure"],
    "scary": ["mystery"],
    "romantic": ["soap", "drama"],
}
_LANG_NAME_TO_KEY = {"hindi": "hindi", "english": "english", "tamil": "tamil", "telugu": "telugu", "kannada": "kannada"}


def heuristic_brief(profile_a: dict, profile_b: dict, history: dict | None = None) -> dict:
    """Pure-python fallback used when Claude isn't configured or errors out."""
    moods = set((profile_a or {}).get("mood", [])) | set((profile_b or {}).get("mood", []))
    genres_movie: set[str] = set()
    genres_tv: set[str] = set()
    for mood in moods:
        genres_movie.update(_MOOD_TO_MOVIE_GENRES.get(mood, []))
        genres_tv.update(_MOOD_TO_TV_GENRES.get(mood, []))

    def lang_constraint(profile):
        langs = (profile or {}).get("languages", [])
        if not langs or "any" in langs:
            return set()
        return {_LANG_NAME_TO_KEY[l] for l in langs if l in _LANG_NAME_TO_KEY}

    lang_a, lang_b = lang_constraint(profile_a), lang_constraint(profile_b)
    if not lang_a or not lang_b:
        languages = lang_a or lang_b
    else:
        languages = lang_a | lang_b

    def era_constraint(profile):
        eras = (profile or {}).get("eras", [])
        if not eras or "any" in eras:
            return set()
        return set(eras)

    era_a, era_b = era_constraint(profile_a), era_constraint(profile_b)
    eras = (era_a or era_b) if (not era_a or not era_b) else (era_a | era_b)

    min_rating = max(
        (profile_a or {}).get("min_rating") or 6,
        (profile_b or {}).get("min_rating") or 6,
    )

    return {
        "genres_movie": sorted(genres_movie),
        "genres_tv": sorted(genres_tv),
        "languages": sorted(languages),
        "eras": sorted(eras),
        "min_vote_average": float(min_rating),
        "vibe_summary": "Matched on shared mood categories (Claude unavailable, used rule-based fallback).",
    }
