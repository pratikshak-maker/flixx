from __future__ import annotations

import io

from flask import Flask, jsonify, render_template, request, send_file

import config
import db
from services import matching

app = Flask(__name__)

VALID_MOODS = {"light_fun", "intense_gripping", "scary", "romantic", "other"}
VALID_LANGUAGES = {"hindi", "english", "tamil", "telugu", "kannada", "any"}
VALID_CONTENT_TYPES = {"movies_only", "include_series"}
VALID_MIN_RATINGS = {6, 7, 8, 9}
VALID_ERAS = {"any", "classic", "2000_2020", "recent"}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/session/<session_id>")
def session_page(session_id):
    return render_template("session.html", session_id=session_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_profile(body: dict) -> str | None:
    mood = body.get("mood") or []
    languages = body.get("languages") or []
    eras = body.get("eras") or []
    if not isinstance(mood, list) or not mood or not set(mood).issubset(VALID_MOODS):
        return "Pick at least one mood."
    if not isinstance(languages, list) or not languages or not set(languages).issubset(VALID_LANGUAGES):
        return "Pick at least one language."
    if body.get("content_type") not in VALID_CONTENT_TYPES:
        return "Choose a content type."
    if body.get("min_rating") not in VALID_MIN_RATINGS:
        return "Choose a minimum rating."
    if not isinstance(eras, list) or not eras or not set(eras).issubset(VALID_ERAS):
        return "Pick at least one era."
    return None


def _profile_from_body(body: dict) -> dict:
    languages = body.get("languages") or []
    if "any" in languages:
        languages = ["any"]
    eras = body.get("eras") or []
    if "any" in eras:
        eras = ["any"]
    return {
        "mood": body.get("mood") or [],
        "mood_text": (body.get("mood_text") or "").strip()[:500],
        "languages": languages,
        "content_type": body.get("content_type"),
        "min_rating": body.get("min_rating"),
        "eras": eras,
    }


def _public_session_state(session_row: dict, prefs: dict) -> dict:
    couple = db.get_couple(session_row.get("couple_id"))
    return {
        "session_id": session_row["id"],
        "status": session_row["status"],
        "round": session_row["round"],
        "a_submitted": prefs["A"] is not None,
        "b_submitted": prefs["B"] is not None,
        "matched_tmdb_id": session_row.get("matched_tmdb_id"),
        "final_choice_tmdb_id": session_row.get("final_choice_tmdb_id"),
        "couple_code": couple["code"] if couple else None,
    }


def _generate_and_store_round1(session_row: dict, prefs: dict) -> None:
    history = None
    if session_row.get("couple_id"):
        history = db.get_couple_history(session_row["couple_id"])
    titles, brief = matching.build_round1_pool(prefs["A"], prefs["B"], history)
    db.save_titles(session_row["id"], 1, titles)
    db.update_session(session_row["id"], {"status": "swiping", "round": 1, "brief_summary": brief.get("vibe_summary", "")})


def _generate_and_store_round2(session_row: dict, prefs: dict) -> None:
    round1_titles = db.get_titles(session_row["id"], 1)
    round1_swipes = db.get_swipes(session_row["id"], 1)
    prior_brief = {"vibe_summary": session_row.get("brief_summary", "")}
    titles, brief = matching.build_round2_pool(prefs["A"], prefs["B"], prior_brief, round1_titles, round1_swipes)
    db.save_titles(session_row["id"], 2, titles)
    db.update_session(session_row["id"], {"status": "swiping", "round": 2})


# ---------------------------------------------------------------------------
# API: session lifecycle
# ---------------------------------------------------------------------------

@app.post("/api/session")
def api_create_session():
    body = request.get_json(force=True, silent=True) or {}
    error = _validate_profile(body)
    if error:
        return jsonify({"error": error}), 400

    couple = None
    couple_code = (body.get("couple_code") or "").strip()
    if couple_code:
        couple = db.get_couple_by_code(couple_code)
    if not couple:
        couple = db.create_couple()

    session_row = db.create_session(couple_id=couple["id"])
    db.upsert_preferences(session_row["id"], "A", _profile_from_body(body))
    db.update_session(session_row["id"], {"status": "awaiting_b"})

    return jsonify({
        "session_id": session_row["id"],
        "couple_code": couple["code"],
        "join_path": f"/session/{session_row['id']}?role=B",
    })


@app.get("/api/session/<session_id>/state")
def api_session_state(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404
    prefs = db.get_preferences(session_id)
    return jsonify(_public_session_state(session_row, prefs))


@app.post("/api/session/<session_id>/preferences")
def api_submit_preferences(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404

    body = request.get_json(force=True, silent=True) or {}
    role = body.get("role")
    if role not in ("A", "B"):
        return jsonify({"error": "Invalid role."}), 400
    error = _validate_profile(body)
    if error:
        return jsonify({"error": error}), 400

    db.upsert_preferences(session_id, role, _profile_from_body(body))
    prefs = db.get_preferences(session_id)

    if prefs["A"] and prefs["B"] and session_row["status"] in ("awaiting_a", "awaiting_b"):
        db.update_session(session_id, {"status": "generating"})
        session_row = db.get_session(session_id)
        _generate_and_store_round1(session_row, prefs)
    elif not (prefs["A"] and prefs["B"]):
        db.update_session(session_id, {"status": "awaiting_b" if role == "A" else "awaiting_a"})

    session_row = db.get_session(session_id)
    return jsonify(_public_session_state(session_row, prefs))


# ---------------------------------------------------------------------------
# API: pool + swiping
# ---------------------------------------------------------------------------

def _seeded_order(session_id: str, role: str, round_no: int, titles: list[dict]) -> list[dict]:
    import random
    rnd = random.Random(f"{session_id}:{role}:{round_no}")
    shuffled = list(titles)
    rnd.shuffle(shuffled)
    return shuffled


@app.get("/api/session/<session_id>/pool")
def api_get_pool(session_id):
    role = request.args.get("role")
    if role not in ("A", "B"):
        return jsonify({"error": "Invalid role."}), 400
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404

    round_no = session_row["round"]
    titles = db.get_titles(session_id, round_no)
    already_swiped = {s["tmdb_id"] for s in db.get_swipes(session_id, round_no) if s["partner"] == role}
    ordered = _seeded_order(session_id, role, round_no, titles)
    remaining = [t for t in ordered if t["tmdb_id"] not in already_swiped]

    return jsonify({
        "round": round_no,
        "titles": remaining,
        "total_in_round": len(titles),
        "remaining_count": len(remaining),
    })


@app.post("/api/session/<session_id>/swipe")
def api_swipe(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404

    body = request.get_json(force=True, silent=True) or {}
    role = body.get("role")
    tmdb_id = body.get("tmdb_id")
    direction = body.get("direction")
    if role not in ("A", "B") or direction not in ("like", "pass") or not isinstance(tmdb_id, int):
        return jsonify({"error": "Invalid swipe payload."}), 400

    round_no = session_row["round"]
    db.record_swipe(session_id, round_no, role, tmdb_id, direction)

    titles = db.get_titles(session_id, round_no)
    swipes = db.get_swipes(session_id, round_no)

    if matching.both_partners_done(titles, swipes):
        match = matching.find_round_match(titles, swipes)
        if match:
            db.update_session(session_id, {"status": "matched", "matched_tmdb_id": match["tmdb_id"]})
        elif round_no == 1:
            prefs = db.get_preferences(session_id)
            db.update_session(session_id, {"status": "generating"})
            session_row = db.get_session(session_id)
            _generate_and_store_round2(session_row, prefs)
        else:
            db.update_session(session_id, {"status": "final_choice"})

    session_row = db.get_session(session_id)
    prefs = db.get_preferences(session_id)
    return jsonify(_public_session_state(session_row, prefs))


@app.get("/api/session/<session_id>/match")
def api_get_match(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404
    tmdb_id = session_row.get("final_choice_tmdb_id") or session_row.get("matched_tmdb_id")
    if not tmdb_id:
        return jsonify({"error": "No match yet."}), 404
    all_titles = db.get_all_titles(session_id)
    title = next((t for t in all_titles if t["tmdb_id"] == tmdb_id), None)
    return jsonify({"title": title})


@app.get("/api/session/<session_id>/top5")
def api_top5(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404
    all_titles = db.get_all_titles(session_id)
    all_swipes = db.get_swipes(session_id)
    top5 = matching.compute_top5(all_titles, all_swipes)
    return jsonify({"titles": top5})


@app.post("/api/session/<session_id>/finalize")
def api_finalize(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404
    body = request.get_json(force=True, silent=True) or {}
    tmdb_id = body.get("tmdb_id")
    if not isinstance(tmdb_id, int):
        return jsonify({"error": "Invalid title."}), 400
    db.update_session(session_id, {"status": "matched", "final_choice_tmdb_id": tmdb_id, "matched_tmdb_id": tmdb_id})
    return jsonify({"ok": True})


@app.post("/api/session/<session_id>/rate")
def api_rate(session_id):
    session_row = db.get_session(session_id)
    if not session_row:
        return jsonify({"error": "Session not found."}), 404
    body = request.get_json(force=True, silent=True) or {}
    tmdb_id = body.get("tmdb_id")
    rating = body.get("rating")
    note = (body.get("note") or "").strip()[:500]
    if not isinstance(tmdb_id, int) or rating not in (1, 2, 3, 4, 5):
        return jsonify({"error": "Invalid rating payload."}), 400
    db.save_rating(session_id, tmdb_id, rating, note)
    db.update_session(session_id, {"status": "finalized"})
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# QR code
# ---------------------------------------------------------------------------

@app.get("/api/session/<session_id>/qr.png")
def api_qr(session_id):
    import qrcode

    join_url = request.args.get("url") or request.host_url.rstrip("/") + f"/session/{session_id}?role=B"
    img = qrcode.make(join_url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=True, threaded=True)
