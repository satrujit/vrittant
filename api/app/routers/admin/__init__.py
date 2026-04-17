"""Admin endpoints, split by resource group.

Re-exports ``router`` and ``config_router`` for ``main.py``."""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
config_router = APIRouter(prefix="/config", tags=["config"])

# Import sub-modules so their @router.<verb> decorators register endpoints
# on the shared router objects above.  Order doesn't matter functionally;
# kept alphabetical for readability.
# Import order matters for path-prefix collisions.  `stories_search` must
# register `/stories/semantic-search` and `/stories/{story_id}/related`
# *before* `stories` registers the catch-all `/stories/{story_id}`, otherwise
# FastAPI would route `semantic-search` as a story_id.
from . import dashboard, leaderboard, stories_search, stories, reporters, users, org, config  # noqa: E402,F401
