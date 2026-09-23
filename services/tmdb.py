"""TMDB discovery — turns a search brief into candidate titles."""
from __future__ import annotations

import requests

import config

BASE = "https://api.themoviedb.org/3"

MOVIE_GENRES = {
    "action": 28, "adventure": 12, "animation": 16, "comedy": 35, "crime": 80,
    "documentary": 99, "drama": 18, "family": 10751, "fantasy": 14, "history": 36,
    "horror": 27, "music": 10402, "mystery": 9648, "romance": 10749,
    "science_fiction": 878, "thriller": 53, "war": 10752, "western": 37,
}

TV_GENRES = {
    "action_adventure": 10759, "animation": 16, "comedy": 35, "crime": 80,
    "documentary": 99, "drama": 18, "family": 10751, "kids": 10762,
    "mystery": 9648, "reality": 10764, "sci_fi_fantasy": 10765, "soap": 10766,
    "war_politics": 10768, "western": 37,
}

LANGUAGE_ISO = {"hindi": "hi", "english": "en", "tamil": "ta", "telugu": "te", "kannada": "kn"}

ERA_RANGES = {
    "classic": (None, "1999-12-31"),
    "2000_2020": ("2000-01-01", "2020-12-31"),
    "recent": ("2021-01-01", "2026-12-31"),
}


def _get(path: str, params: dict) -> dict:
    params = {**params, "api_key": config.TMDB_API_KEY}
    resp = requests.get(f"{BASE}{path}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def discover(media_type: str, genre_ids: list[int], languages: list[str],
             eras: list[str], min_vote_average: float, page: int = 1) -> list[dict]:
    date_field = "primary_release_date" if media_type == "movie" else "first_air_date"
    params = {
        "sort_by": "popularity.desc",
        "vote_count.gte": 20,
        "page": page,
        "include_adult": "false",
    }
    if genre_ids:
        params["with_genres"] = "|".join(str(g) for g in genre_ids)
    if languages:
        params["with_original_language"] = "|".join(languages)

    results = []
    ranges = [ERA_RANGES[e] for e in eras if e in ERA_RANGES] or [(None, None)]
    for gte, lte in ranges:
        p = dict(params)
        if gte:
            p[f"{date_field}.gte"] = gte
        if lte:
            p[f"{date_field}.lte"] = lte
        try:
            data = _get(f"/discover/{media_type}", p)
        except requests.RequestException:
            continue
        results.extend(data.get("results", []))
    return results


def to_candidate(raw: dict, media_type: str) -> dict:
    date_field = "release_date" if media_type == "movie" else "first_air_date"
    date_val = raw.get(date_field) or ""
    year = int(date_val[:4]) if date_val[:4].isdigit() else None
    poster_path = raw.get("poster_path")
    return {
        "tmdb_id": raw["id"],
        "media_type": media_type,
        "title": raw.get("title") or raw.get("name") or "Untitled",
        "year": year,
        "poster_url": f"{config.TMDB_IMAGE_BASE}{poster_path}" if poster_path else None,
        "synopsis": raw.get("overview", ""),
        "tmdb_vote_average": raw.get("vote_average"),
        "popularity": raw.get("popularity", 0),
    }


def find_candidates(genre_ids_movie: list[int], genre_ids_tv: list[int], languages: list[str],
                     eras: list[str], min_vote_average: float, content_type: str,
                     exclude_ids: set[int], target_count: int, max_pages: int = 4) -> list[dict]:
    """Pulls candidates across pages/media types until we have enough unseen ones."""
    media_types = ["movie"] if content_type == "movies_only" else ["movie", "tv"]
    seen_ids: set[int] = set()
    candidates: list[dict] = []

    for media_type in media_types:
        genre_ids = genre_ids_movie if media_type == "movie" else genre_ids_tv
        for page in range(1, max_pages + 1):
            raw_results = discover(media_type, genre_ids, languages, eras, min_vote_average, page=page)
            if not raw_results:
                break
            for raw in raw_results:
                if raw["id"] in exclude_ids or raw["id"] in seen_ids:
                    continue
                seen_ids.add(raw["id"])
                candidates.append(to_candidate(raw, media_type))
            if len(candidates) >= target_count * 4:
                break
        if len(candidates) >= target_count * 4:
            break

    candidates.sort(key=lambda c: c.get("popularity", 0), reverse=True)
    return candidates
