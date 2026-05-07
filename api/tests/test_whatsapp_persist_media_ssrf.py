"""SSRF + resource-exhaustion guards on _persist_media."""
import asyncio
from unittest.mock import patch


def _run(coro):
    return asyncio.run(coro)


# ── _is_url_safe_to_fetch ──────────────────────────────────────


def test_safe_url_gupshup_https():
    """Bypass DNS resolution by patching socket.getaddrinfo so the test
    doesn't depend on the network."""
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("13.226.10.10", 0))]):
        assert _is_url_safe_to_fetch("https://media.gupshup.io/whatever") is True


def test_unsafe_url_non_gupshup_host():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    assert _is_url_safe_to_fetch("https://evil.example.com/x") is False


def test_unsafe_url_http_scheme_to_internal_host():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    # GCP metadata service — classic SSRF target. Even if the host
    # somehow matched the allowlist, the IP-resolution check would
    # block it.
    assert _is_url_safe_to_fetch("http://169.254.169.254/computeMetadata/v1/") is False


def test_unsafe_url_gupshup_host_resolving_to_private_ip():
    """DNS-rebinding-style: an attacker controls a Gupshup-allowlisted
    hostname that resolves to 10.0.0.1 — must still be rejected."""
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 0))]):
        assert _is_url_safe_to_fetch("https://media.gupshup.io/x") is False


def test_unsafe_url_loopback_resolution():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        assert _is_url_safe_to_fetch("https://media.gupshup.io/x") is False


def test_unsafe_url_link_local_resolution():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("169.254.0.5", 0))]):
        assert _is_url_safe_to_fetch("https://media.gupshup.io/x") is False


def test_unsafe_url_with_no_scheme():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    assert _is_url_safe_to_fetch("media.gupshup.io/x") is False


def test_unsafe_url_with_file_scheme():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    assert _is_url_safe_to_fetch("file:///etc/passwd") is False


def test_unsafe_url_when_dns_fails():
    from app.routers.webhooks_whatsapp import _is_url_safe_to_fetch
    import socket
    with patch("socket.getaddrinfo", side_effect=socket.gaierror):
        assert _is_url_safe_to_fetch("https://media.gupshup.io/x") is False


# ── _persist_media early-exit on unsafe URL ────────────────────


def test_persist_media_rejects_unsafe_url_without_fetching():
    """A non-Gupshup URL must NOT trigger an HTTP fetch — return None
    immediately and don't probe the attacker's server."""
    from app.routers import webhooks_whatsapp
    from unittest.mock import MagicMock, AsyncMock

    fake_client_cls = MagicMock()
    with patch.object(webhooks_whatsapp.httpx, "AsyncClient", fake_client_cls):
        result = _run(webhooks_whatsapp._persist_media("https://evil.example.com/x"))
    assert result == (None, None, None, None)
    fake_client_cls.assert_not_called()  # no client was constructed
