"""Force-update gate: /version/min-supported.

The mobile app fetches this on cold start and blocks if its version is below
`min`. The contract this test locks in:
  - public (no auth)
  - returns both ios and android blocks
  - each block has min, latest, store_url fields
  - empty defaults are returned when env vars are unset (gate disabled)
"""

from unittest.mock import patch


def test_min_supported_is_public(client):
    resp = client.get("/version/min-supported")
    assert resp.status_code == 200, resp.text


def test_min_supported_returns_both_platforms(client):
    body = client.get("/version/min-supported").json()
    assert "ios" in body
    assert "android" in body
    for platform in (body["ios"], body["android"]):
        assert "min" in platform
        assert "latest" in platform
        assert "store_url" in platform


def test_min_supported_reflects_settings(client):
    with patch("app.routers.version.settings") as mock_settings:
        mock_settings.MIN_VERSION_IOS = "1.2.0"
        mock_settings.LATEST_VERSION_IOS = "1.5.0"
        mock_settings.APP_STORE_URL_IOS = "https://apps.apple.com/app/id123"
        mock_settings.MIN_VERSION_ANDROID = "1.1.0"
        mock_settings.LATEST_VERSION_ANDROID = "1.5.0"
        mock_settings.APP_STORE_URL_ANDROID = "https://play.google.com/x"

        body = client.get("/version/min-supported").json()

    assert body["ios"]["min"] == "1.2.0"
    assert body["ios"]["latest"] == "1.5.0"
    assert body["ios"]["store_url"] == "https://apps.apple.com/app/id123"
    assert body["android"]["min"] == "1.1.0"
    assert body["android"]["store_url"] == "https://play.google.com/x"


def test_min_supported_defaults_disable_gate(client):
    """Empty MIN_VERSION_* must mean 'no gate' — never accidentally lock out
    every install just because env vars weren't set in a new environment."""
    with patch("app.routers.version.settings") as mock_settings:
        mock_settings.MIN_VERSION_IOS = ""
        mock_settings.LATEST_VERSION_IOS = ""
        mock_settings.APP_STORE_URL_IOS = ""
        mock_settings.MIN_VERSION_ANDROID = ""
        mock_settings.LATEST_VERSION_ANDROID = ""
        mock_settings.APP_STORE_URL_ANDROID = ""

        body = client.get("/version/min-supported").json()

    assert body["ios"]["min"] == ""
    assert body["android"]["min"] == ""
