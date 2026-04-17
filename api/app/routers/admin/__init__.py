"""Admin endpoints, split by resource group.

Re-exports ``router`` and ``config_router`` for ``main.py``."""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
config_router = APIRouter(prefix="/config", tags=["config"])

# Import sub-modules so their @router.<verb> decorators register endpoints
# on the shared router objects above.
#
# stories_search must register `/stories/semantic-search` and
# `/stories/{story_id}/related` BEFORE stories registers the catch-all
# `/stories/{story_id}` — FastAPI matches in registration order.
# Re-ordering this import will silently break two endpoints; the regression
# is pinned by tests/test_admin_route_order.py.
from . import dashboard, leaderboard, stories_search, stories, reporters, users, org, config  # noqa: E402,F401
