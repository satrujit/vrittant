"""Regression test for admin sub-router import order.

`api/app/routers/admin/__init__.py` imports `stories_search` BEFORE `stories`
so that `/admin/stories/semantic-search` and `/admin/stories/{story_id}/related`
register before the catch-all `GET /admin/stories/{story_id}`. FastAPI matches
routes in registration order, so swapping the import order would silently
shadow both endpoints (the literal segments would be parsed as `story_id`
values instead).

These assertions fail loudly if a future refactor re-orders the imports.
"""


def _path_index(paths, suffix):
    return next(i for i, p in enumerate(paths) if p.endswith(suffix))


def test_semantic_search_registers_before_story_catchall():
    from app.routers.admin import router

    paths = [r.path for r in router.routes]
    semantic_idx = _path_index(paths, "/stories/semantic-search")
    catchall_idx = _path_index(paths, "/stories/{story_id}")

    assert semantic_idx < catchall_idx, (
        "/admin/stories/semantic-search must register before "
        "/admin/stories/{story_id} or it will be shadowed by the catch-all."
    )


def test_related_registers_before_story_catchall():
    from app.routers.admin import router

    paths = [r.path for r in router.routes]
    related_idx = _path_index(paths, "/stories/{story_id}/related")
    catchall_idx = _path_index(paths, "/stories/{story_id}")

    assert related_idx < catchall_idx, (
        "/admin/stories/{story_id}/related must register before "
        "/admin/stories/{story_id} or it will be shadowed by the catch-all."
    )
