"""RapidAPI "OTT Details" (ott-details.p.rapidapi.com, by GoX-ai) lookups.

That API keys everything off an IMDb id, not a TMDB id, so a candidate is
first resolved to its IMDb id via TMDB's own external_ids endpoint (free,
no extra key) before asking OTT Details for the real IMDb rating, runtime,
synopsis and which Indian OTT platforms currently carry it. Parsing is
defensive: any missing field falls back to what TMDB already gave us, and a
title with no "IN" entry in streamingAvailability just gets an empty list
rather than guessing from another country's availability.
"""
from __future__ import annotations

import concurrent.futures
import re

import requests

import config

HOST = "ott-details.p.rapidapi.com"
BASE = f"https://{HOST}"
COUNTRY = "IN"

TMDB_BASE = "https://api.themoviedb.org/3"

_PLATFORM_NAMES = {
    "netflix": "Netflix",
    "primevideo": "Prime Video",
    "amazonprime": "Prime Video",
    "amazonprimevideo": "Prime Video",
    "amazon": "Prime Video",
    "hotstar": "JioHotstar",
    "disneyplushotstar": "JioHotstar",
    "jiocinema": "JioCinema",
    "voot": "Voot",
    "zee5": "Zee5",
    "sonyliv": "SonyLIV",
    "sunnxt": "Sun NXT",
    "hoichoi": "Hoichoi",
    "altbalaji": "Alt Balaji",
    "erosnow": "Eros Now",
    "mxplayer": "MX Player",
    "itunes": "Apple TV",
    "appletv": "Apple TV",
    "play": "Google Play Movies & TV",
    "youtube": "YouTube",
    "mubi": "Mubi",
    "crunchyroll": "Crunchyroll",
    "tubitv": "Tubi",
}


def _headers():
    return {"X-RapidAPI-Key": config.RAPIDAPI_KEY, "X-RapidAPI-Host": HOST}


def _display_name(slug: str) -> str:
    if slug in _PLATFORM_NAMES:
        return _PLATFORM_NAMES[slug]
    return slug.replace("_", " ").replace("-", " ").title()


def _imdb_id(tmdb_id: int, media_type: str) -> str | None:
    path = "movie" if media_type == "movie" else "tv"
    try:
        resp = requests.get(
            f"{TMDB_BASE}/{path}/{tmdb_id}/external_ids",
            params={"api_key": config.TMDB_API_KEY},
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("imdb_id")
    except requests.RequestException:
        return None


def _extract_runtime(runtime_str) -> int | None:
    if not runtime_str:
        return None
    match = re.search(r"\d+", str(runtime_str))
    return int(match.group()) if match else None


def _extract_platforms(data: dict) -> list[dict]:
    country_options = ((data.get("streamingAvailability") or {}).get("country") or {}).get(COUNTRY) or []
    platforms, seen = [], set()
    for opt in country_options:
        slug = opt.get("platform")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        platforms.append({"name": _display_name(slug), "url": opt.get("url")})
    return platforms


def enrich_one(tmdb_id: int, media_type: str) -> dict | None:
    if not config.HAS_STREAMING:
        return None
    imdb_id = _imdb_id(tmdb_id, media_type)
    if not imdb_id:
        return None
    try:
        resp = requests.get(
            f"{BASE}/gettitleDetails",
            headers=_headers(),
            params={"imdbid": imdb_id},
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    return {
        "imdb_rating": data.get("imdbrating"),
        "runtime": _extract_runtime(data.get("runtime")),
        "synopsis": data.get("synopsis"),
        "ott_platforms": _extract_platforms(data),
    }


def enrich_many(candidates: list[dict], max_workers: int = 3) -> dict[int, dict]:
    """Returns {tmdb_id: enrichment} for candidates that resolved successfully.

    max_workers is kept low (rather than one-thread-per-candidate) because the
    OTT Details API's free tier enforces a tight per-second rate limit and
    returns 429s under heavy concurrency; enrich_one already fails soft on
    those, but a smaller pool means fewer titles hit the limit in the first
    place.
    """
    if not config.HAS_STREAMING or not candidates:
        return {}
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(enrich_one, c["tmdb_id"], c["media_type"]): c["tmdb_id"]
            for c in candidates
        }
        for future in concurrent.futures.as_completed(futures):
            tmdb_id = futures[future]
            try:
                data = future.result()
            except Exception:
                data = None
            if data:
                results[tmdb_id] = data
    return results
