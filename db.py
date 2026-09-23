"""Storage layer.

Talks to Supabase's PostgREST API when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
are configured. Falls back to an in-process store when they are not, so the
app is fully clickable during local UI development without a Supabase
project. The in-memory store is process-local and lost on restart — it is a
dev convenience only, not a replacement for the real thing.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

import requests

import config

_lock = threading.Lock()
_memory = {
    "sessions": {},
    "preferences": [],
    "titles": [],
    "swipes": [],
    "ratings": [],
    "couples": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


class SupabaseError(RuntimeError):
    pass


def _headers():
    return {
        "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest(method: str, path: str, params: dict | None = None, json_body=None):
    url = f"{config.SUPABASE_URL}/rest/v1/{path}"
    resp = requests.request(method, url, headers=_headers(), params=params, json=json_body, timeout=15)
    if resp.status_code >= 400:
        raise SupabaseError(f"{method} {path} -> {resp.status_code}: {resp.text}")
    if not resp.text:
        return []
    return resp.json()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def create_session(couple_id: str | None = None) -> dict:
    row = {
        "id": new_id(),
        "status": "awaiting_a",
        "round": 1,
        "couple_id": couple_id,
        "matched_tmdb_id": None,
        "final_choice_tmdb_id": None,
        "created_at": _now(),
    }
    if config.HAS_SUPABASE:
        created = _rest("POST", "sessions", json_body=row)
        return created[0] if isinstance(created, list) else created
    with _lock:
        _memory["sessions"][row["id"]] = row
        return dict(row)


def get_session(session_id: str) -> dict | None:
    if config.HAS_SUPABASE:
        rows = _rest("GET", "sessions", params={"id": f"eq.{session_id}", "select": "*"})
        return rows[0] if rows else None
    with _lock:
        row = _memory["sessions"].get(session_id)
        return dict(row) if row else None


def update_session(session_id: str, patch: dict) -> dict | None:
    if config.HAS_SUPABASE:
        rows = _rest("PATCH", "sessions", params={"id": f"eq.{session_id}"}, json_body=patch)
        return rows[0] if rows else None
    with _lock:
        row = _memory["sessions"].get(session_id)
        if not row:
            return None
        row.update(patch)
        return dict(row)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def upsert_preferences(session_id: str, partner: str, profile: dict) -> dict:
    row = {
        "id": new_id(),
        "session_id": session_id,
        "partner": partner,
        "mood": profile.get("mood", []),
        "mood_text": profile.get("mood_text", ""),
        "languages": profile.get("languages", []),
        "content_type": profile.get("content_type"),
        "min_rating": profile.get("min_rating"),
        "eras": profile.get("eras", []),
        "submitted_at": _now(),
    }
    if config.HAS_SUPABASE:
        existing = _rest(
            "GET", "preferences",
            params={"session_id": f"eq.{session_id}", "partner": f"eq.{partner}", "select": "id"},
        )
        if existing:
            rows = _rest(
                "PATCH", "preferences",
                params={"id": f"eq.{existing[0]['id']}"},
                json_body=row,
            )
        else:
            rows = _rest("POST", "preferences", json_body=row)
        return rows[0] if rows else row
    with _lock:
        _memory["preferences"] = [
            p for p in _memory["preferences"]
            if not (p["session_id"] == session_id and p["partner"] == partner)
        ]
        _memory["preferences"].append(row)
        return dict(row)


def get_preferences(session_id: str) -> dict:
    """Returns {'A': profile|None, 'B': profile|None}."""
    if config.HAS_SUPABASE:
        rows = _rest("GET", "preferences", params={"session_id": f"eq.{session_id}", "select": "*"})
    else:
        with _lock:
            rows = [dict(p) for p in _memory["preferences"] if p["session_id"] == session_id]
    result = {"A": None, "B": None}
    for row in rows:
        result[row["partner"]] = row
    return result


# ---------------------------------------------------------------------------
# Titles (the pool shown to both partners for a given round)
# ---------------------------------------------------------------------------

def save_titles(session_id: str, round_no: int, titles: list[dict]) -> list[dict]:
    rows = []
    for t in titles:
        rows.append({
            "id": new_id(),
            "session_id": session_id,
            "round": round_no,
            "tmdb_id": t["tmdb_id"],
            "media_type": t["media_type"],
            "title": t["title"],
            "year": t.get("year"),
            "poster_url": t.get("poster_url"),
            "imdb_rating": t.get("imdb_rating"),
            "runtime": t.get("runtime"),
            "synopsis": t.get("synopsis", ""),
            "ott_platforms": t.get("ott_platforms", []),
            "created_at": _now(),
        })
    if config.HAS_SUPABASE:
        if rows:
            _rest("POST", "titles", json_body=rows)
    else:
        with _lock:
            _memory["titles"].extend(rows)
    return rows


def get_titles(session_id: str, round_no: int) -> list[dict]:
    if config.HAS_SUPABASE:
        return _rest(
            "GET", "titles",
            params={"session_id": f"eq.{session_id}", "round": f"eq.{round_no}", "select": "*"},
        )
    with _lock:
        return [dict(t) for t in _memory["titles"] if t["session_id"] == session_id and t["round"] == round_no]


def get_all_titles(session_id: str) -> list[dict]:
    if config.HAS_SUPABASE:
        return _rest("GET", "titles", params={"session_id": f"eq.{session_id}", "select": "*"})
    with _lock:
        return [dict(t) for t in _memory["titles"] if t["session_id"] == session_id]


# ---------------------------------------------------------------------------
# Swipes
# ---------------------------------------------------------------------------

def record_swipe(session_id: str, round_no: int, partner: str, tmdb_id: int, direction: str) -> None:
    row = {
        "id": new_id(),
        "session_id": session_id,
        "round": round_no,
        "partner": partner,
        "tmdb_id": tmdb_id,
        "direction": direction,
        "created_at": _now(),
    }
    if config.HAS_SUPABASE:
        existing = _rest(
            "GET", "swipes",
            params={
                "session_id": f"eq.{session_id}", "round": f"eq.{round_no}",
                "partner": f"eq.{partner}", "tmdb_id": f"eq.{tmdb_id}", "select": "id",
            },
        )
        if existing:
            _rest("PATCH", "swipes", params={"id": f"eq.{existing[0]['id']}"}, json_body={"direction": direction})
        else:
            _rest("POST", "swipes", json_body=row)
        return
    with _lock:
        _memory["swipes"] = [
            s for s in _memory["swipes"]
            if not (s["session_id"] == session_id and s["round"] == round_no
                    and s["partner"] == partner and s["tmdb_id"] == tmdb_id)
        ]
        _memory["swipes"].append(row)


def get_swipes(session_id: str, round_no: int | None = None) -> list[dict]:
    if config.HAS_SUPABASE:
        params = {"session_id": f"eq.{session_id}", "select": "*"}
        if round_no is not None:
            params["round"] = f"eq.{round_no}"
        return _rest("GET", "swipes", params=params)
    with _lock:
        return [
            dict(s) for s in _memory["swipes"]
            if s["session_id"] == session_id and (round_no is None or s["round"] == round_no)
        ]


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

def save_rating(session_id: str, tmdb_id: int, rating: int, note: str) -> dict:
    row = {
        "id": new_id(),
        "session_id": session_id,
        "tmdb_id": tmdb_id,
        "rating": rating,
        "note": note,
        "created_at": _now(),
    }
    if config.HAS_SUPABASE:
        rows = _rest("POST", "ratings", json_body=row)
        return rows[0] if rows else row
    with _lock:
        _memory["ratings"].append(row)
        return dict(row)


# ---------------------------------------------------------------------------
# Couples (returning-user history)
# ---------------------------------------------------------------------------

def _random_code() -> str:
    import random
    import string
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_couple() -> dict:
    row = {"id": new_id(), "code": _random_code(), "created_at": _now()}
    if config.HAS_SUPABASE:
        rows = _rest("POST", "couples", json_body=row)
        return rows[0] if rows else row
    with _lock:
        _memory["couples"][row["code"]] = row
        return dict(row)


def get_couple(couple_id: str | None) -> dict | None:
    if not couple_id:
        return None
    if config.HAS_SUPABASE:
        rows = _rest("GET", "couples", params={"id": f"eq.{couple_id}", "select": "*"})
        return rows[0] if rows else None
    with _lock:
        for row in _memory["couples"].values():
            if row["id"] == couple_id:
                return dict(row)
    return None


def get_couple_by_code(code: str) -> dict | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    if config.HAS_SUPABASE:
        rows = _rest("GET", "couples", params={"code": f"eq.{code}", "select": "*"})
        return rows[0] if rows else None
    with _lock:
        row = _memory["couples"].get(code)
        return dict(row) if row else None


def get_couple_history(couple_id: str) -> dict:
    """Aggregates past sessions for a couple: liked/disliked titles + ratings."""
    if config.HAS_SUPABASE:
        sessions = _rest("GET", "sessions", params={"couple_id": f"eq.{couple_id}", "select": "id"})
        session_ids = [s["id"] for s in sessions]
    else:
        with _lock:
            session_ids = [sid for sid, s in _memory["sessions"].items() if s.get("couple_id") == couple_id]

    liked, disliked, ratings = [], [], []
    for sid in session_ids:
        swipes = get_swipes(sid)
        titles_by_id = {t["tmdb_id"]: t for t in get_all_titles(sid)}
        both_liked = {}
        for sw in swipes:
            t = titles_by_id.get(sw["tmdb_id"])
            if not t:
                continue
            both_liked.setdefault(sw["tmdb_id"], {"title": t["title"], "likes": 0, "passes": 0})
            if sw["direction"] == "like":
                both_liked[sw["tmdb_id"]]["likes"] += 1
            else:
                both_liked[sw["tmdb_id"]]["passes"] += 1
        for tmdb_id, info in both_liked.items():
            if info["likes"] >= 2:
                liked.append(info["title"])
            elif info["passes"] >= 2:
                disliked.append(info["title"])
        if config.HAS_SUPABASE:
            ratings.extend(_rest("GET", "ratings", params={"session_id": f"eq.{sid}", "select": "*"}))
        else:
            with _lock:
                ratings.extend([r for r in _memory["ratings"] if r["session_id"] == sid])

    return {"liked": liked, "disliked": disliked, "ratings": ratings}
