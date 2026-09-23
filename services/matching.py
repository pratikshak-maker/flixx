"""Orchestrates brief -> pool building, and swipe/match scoring."""
from __future__ import annotations

import random

import config
from services import claude_brief, sample_data, streaming, tmdb

_MOOD_TAG = {
    "light_fun": "fun", "intense_gripping": "intense", "scary": "scary", "romantic": "romantic",
}
_LANG_KEY_TO_ISO = {"hindi": "hi", "english": "en", "tamil": "ta", "telugu": "te", "kannada": "kn"}


def resolve_content_type(profile_a: dict, profile_b: dict) -> str:
    if (profile_a or {}).get("content_type") == "movies_only" or (profile_b or {}).get("content_type") == "movies_only":
        return "movies_only"
    return "include_series"


def resolve_min_rating(profile_a: dict, profile_b: dict) -> int:
    return max((profile_a or {}).get("min_rating") or 6, (profile_b or {}).get("min_rating") or 6)


def _demo_titles(profile_a: dict, profile_b: dict, exclude_ids: set[int], target: int,
                  lean_liked_ids: set[int] | None = None) -> list[dict]:
    catalog = sample_data.full_catalog()
    content_type = resolve_content_type(profile_a, profile_b)
    min_rating = resolve_min_rating(profile_a, profile_b)

    moods_raw = set((profile_a or {}).get("mood", [])) | set((profile_b or {}).get("mood", []))
    mood_tags = {_MOOD_TAG[m] for m in moods_raw if m in _MOOD_TAG}

    def lang_set(profile):
        langs = (profile or {}).get("languages", [])
        if not langs or "any" in langs:
            return set()
        return {_LANG_KEY_TO_ISO[l] for l in langs if l in _LANG_KEY_TO_ISO}

    lang_a, lang_b = lang_set(profile_a), lang_set(profile_b)
    languages = (lang_a or lang_b) if (not lang_a or not lang_b) else (lang_a & lang_b or lang_a | lang_b)

    def era_set(profile):
        eras = (profile or {}).get("eras", [])
        if not eras or "any" in eras:
            return set()
        return set(eras)

    era_a, era_b = era_set(profile_a), era_set(profile_b)
    eras = (era_a or era_b) if (not era_a or not era_b) else (era_a | era_b)

    def matches(item, strict_mood=True, strict_lang=True):
        if item["tmdb_id"] in exclude_ids:
            return False
        if content_type == "movies_only" and item["media_type"] != "movie":
            return False
        if item["imdb_rating"] < min_rating:
            return False
        if strict_lang and languages and item["language"] not in languages:
            return False
        if eras and item["era"] not in eras:
            return False
        if strict_mood and mood_tags and not (item["moods"] & mood_tags):
            return False
        return True

    pool = [item for item in catalog if matches(item, strict_mood=True, strict_lang=True)]
    if len(pool) < target:
        pool = [item for item in catalog if matches(item, strict_mood=False, strict_lang=True)]
    if len(pool) < target:
        pool = [item for item in catalog if matches(item, strict_mood=False, strict_lang=False)]

    if lean_liked_ids:
        liked_tags = {
            tag for item in catalog if item["tmdb_id"] in lean_liked_ids for tag in item["moods"]
        }
        if liked_tags:
            pool.sort(key=lambda it: len(it["moods"] & liked_tags), reverse=True)
        else:
            random.shuffle(pool)
    else:
        random.shuffle(pool)

    return [
        {k: v for k, v in item.items() if k not in ("moods", "language", "era")}
        for item in pool[:target]
    ]


def _live_titles(brief: dict, profile_a: dict, profile_b: dict, exclude_ids: set[int], target: int) -> list[dict]:
    content_type = resolve_content_type(profile_a, profile_b)
    min_rating = max(resolve_min_rating(profile_a, profile_b), brief.get("min_vote_average") or 0)
    genre_ids_movie = [tmdb.MOVIE_GENRES[g] for g in brief.get("genres_movie", []) if g in tmdb.MOVIE_GENRES]
    genre_ids_tv = [tmdb.TV_GENRES[g] for g in brief.get("genres_tv", []) if g in tmdb.TV_GENRES]
    languages = [_LANG_KEY_TO_ISO[l] for l in brief.get("languages", []) if l in _LANG_KEY_TO_ISO]
    eras = brief.get("eras", [])

    candidates = tmdb.find_candidates(
        genre_ids_movie, genre_ids_tv, languages, eras,
        min_vote_average=min_rating, content_type=content_type,
        exclude_ids=exclude_ids, target_count=target,
    )

    enrichment = streaming.enrich_many(candidates)
    final = []
    for c in candidates:
        extra = enrichment.get(c["tmdb_id"])
        imdb_rating = (extra or {}).get("imdb_rating")
        if imdb_rating is None:
            imdb_rating = round(c.get("tmdb_vote_average") or 0, 1)
        if imdb_rating < min_rating:
            continue
        final.append({
            "tmdb_id": c["tmdb_id"],
            "media_type": c["media_type"],
            "title": c["title"],
            "year": c["year"],
            "poster_url": c["poster_url"],
            "imdb_rating": imdb_rating,
            "runtime": (extra or {}).get("runtime"),
            "synopsis": (extra or {}).get("synopsis") or c["synopsis"],
            "ott_platforms": (extra or {}).get("ott_platforms") or [],
        })
        if len(final) >= target:
            break
    return final


def build_round1_pool(profile_a: dict, profile_b: dict, history: dict | None,
                       target: int = 30) -> tuple[list[dict], dict]:
    brief = claude_brief.generate_brief(profile_a, profile_b, history)
    if config.DEMO_MODE:
        titles = _demo_titles(profile_a, profile_b, exclude_ids=set(), target=target)
    else:
        titles = _live_titles(brief, profile_a, profile_b, exclude_ids=set(), target=target)
    return titles, brief


def build_round2_pool(profile_a: dict, profile_b: dict, prior_brief: dict,
                       round1_titles: list[dict], round1_swipes: list[dict],
                       target: int = 30) -> tuple[list[dict], dict]:
    titles_by_id = {t["tmdb_id"]: t for t in round1_titles}
    likes_by_title: dict[int, set[str]] = {}
    for sw in round1_swipes:
        if sw["direction"] == "like":
            likes_by_title.setdefault(sw["tmdb_id"], set()).add(sw["partner"])

    both_liked = [titles_by_id[tid]["title"] for tid, p in likes_by_title.items() if len(p) == 2 and tid in titles_by_id]
    single_liked = [titles_by_id[tid]["title"] for tid, p in likes_by_title.items() if len(p) == 1 and tid in titles_by_id]
    both_liked_ids = {tid for tid, p in likes_by_title.items() if len(p) == 2}

    pass_counts: dict[int, int] = {}
    for sw in round1_swipes:
        if sw["direction"] == "pass":
            pass_counts[sw["tmdb_id"]] = pass_counts.get(sw["tmdb_id"], 0) + 1
    both_passed = [titles_by_id[tid]["title"] for tid, n in pass_counts.items() if n >= 2 and tid in titles_by_id]

    brief = claude_brief.refine_brief_round2(prior_brief, profile_a, profile_b, both_liked, both_passed, single_liked)
    exclude_ids = set(titles_by_id.keys())

    if config.DEMO_MODE:
        titles = _demo_titles(profile_a, profile_b, exclude_ids=exclude_ids, target=target, lean_liked_ids=both_liked_ids)
    else:
        titles = _live_titles(brief, profile_a, profile_b, exclude_ids=exclude_ids, target=target)
    return titles, brief


def find_round_match(titles: list[dict], swipes: list[dict]) -> dict | None:
    """A partner-likes-set-intersection match, preferring the highest-rated overlap."""
    likes_by_title: dict[int, set[str]] = {}
    for sw in swipes:
        if sw["direction"] == "like":
            likes_by_title.setdefault(sw["tmdb_id"], set()).add(sw["partner"])
    mutual_ids = [tid for tid, partners in likes_by_title.items() if len(partners) == 2]
    if not mutual_ids:
        return None
    titles_by_id = {t["tmdb_id"]: t for t in titles}
    mutual = [titles_by_id[tid] for tid in mutual_ids if tid in titles_by_id]
    if not mutual:
        return None
    mutual.sort(key=lambda t: t.get("imdb_rating") or 0, reverse=True)
    return mutual[0]


def both_partners_done(titles: list[dict], swipes: list[dict]) -> bool:
    tmdb_ids = {t["tmdb_id"] for t in titles}
    if not tmdb_ids:
        return False
    for partner in ("A", "B"):
        swiped_ids = {sw["tmdb_id"] for sw in swipes if sw["partner"] == partner}
        if not tmdb_ids.issubset(swiped_ids):
            return False
    return True


def compute_top5(all_titles: list[dict], all_swipes: list[dict]) -> list[dict]:
    titles_by_id = {t["tmdb_id"]: t for t in all_titles}
    score: dict[int, int] = {}
    for sw in all_swipes:
        if sw["direction"] != "like":
            continue
        score[sw["tmdb_id"]] = score.get(sw["tmdb_id"], 0) + 1
    ranked = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
    result = []
    for tmdb_id, s in ranked[:5]:
        t = titles_by_id.get(tmdb_id)
        if t:
            result.append({**t, "combined_score": s})
    return result
