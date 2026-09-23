import os

from dotenv import load_dotenv

load_dotenv()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

PORT = int(os.environ.get("PORT", "5001"))
FORCE_DEMO_MODE = _truthy(os.environ.get("DEMO_MODE"))

HAS_CLAUDE = bool(ANTHROPIC_API_KEY) and not FORCE_DEMO_MODE
HAS_TMDB = bool(TMDB_API_KEY) and not FORCE_DEMO_MODE
HAS_STREAMING = bool(RAPIDAPI_KEY) and not FORCE_DEMO_MODE
HAS_SUPABASE = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY) and not FORCE_DEMO_MODE

# The pool is considered "live" only once we can actually discover titles.
# Without TMDB there is nothing real to discover, so we fall back to the
# bundled sample catalog for local development.
DEMO_MODE = FORCE_DEMO_MODE or not HAS_TMDB

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
CLAUDE_MODEL = "claude-sonnet-5"
