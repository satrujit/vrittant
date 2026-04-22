"""Mobile version-gate endpoint.

The mobile app calls `GET /version/min-supported` on every cold start. If its
current version is below the configured minimum for its platform, the app
blocks with a non-dismissable "Update required" screen pointing at the store.

Why this exists:
  When we ship a breaking API change (rename a field, drop an endpoint,
  change auth shape), every installed client below that version becomes
  silently broken. Without a gate, users see vague errors for weeks until
  they happen to update. With a gate, we bump `MIN_VERSION_*` env vars in
  Cloud Run, redeploy in 60 seconds, and every old client is forced to
  upgrade on next launch. No app rebuild needed.

Public endpoint — no auth. The whole point is the user might not be logged
in yet (or might be on an old client whose login flow no longer works), and
they still need to be told to update.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings

router = APIRouter()


class PlatformVersion(BaseModel):
    # Lowest version we still accept. Below this → force update screen.
    # Empty string disables the gate (treat all client versions as supported).
    min: str
    # Latest published version (informational; for soft "update available"
    # prompts later — not required for force-update logic).
    latest: str
    # Deep link to the store listing for the platform. Used by the
    # "Update Now" button. Empty string = button hidden.
    store_url: str


class MinSupportedResponse(BaseModel):
    ios: PlatformVersion
    android: PlatformVersion


@router.get("/version/min-supported", response_model=MinSupportedResponse)
def min_supported() -> MinSupportedResponse:
    return MinSupportedResponse(
        ios=PlatformVersion(
            min=settings.MIN_VERSION_IOS,
            latest=settings.LATEST_VERSION_IOS,
            store_url=settings.APP_STORE_URL_IOS,
        ),
        android=PlatformVersion(
            min=settings.MIN_VERSION_ANDROID,
            latest=settings.LATEST_VERSION_ANDROID,
            store_url=settings.APP_STORE_URL_ANDROID,
        ),
    )
