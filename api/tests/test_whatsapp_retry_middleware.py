"""Tests for the transient-DB-error retry middleware.

The middleware wraps webhook routes and catches a small allowlist of
transient SQLAlchemy/psycopg2 errors, invalidates the pool, retries
once. Logical errors (IntegrityError, etc.) are NOT retried because a
retry can never resolve them.
"""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, IntegrityError

from app.services.whatsapp.reliability import (
    retry_on_transient_db_errors,
    is_transient_db_error,
)


# ── is_transient_db_error ──────────────────────────────────────────


def test_is_transient_recognises_server_closed():
    e = OperationalError("stmt", {}, Exception("server closed the connection unexpectedly"))
    assert is_transient_db_error(e) is True


def test_is_transient_recognises_pgres_tuples_ok_no_message():
    """The exact error string from the 2026-05-05 incident."""
    e = OperationalError(
        "stmt", {}, Exception("error with status PGRES_TUPLES_OK and no message from the libpq"),
    )
    assert is_transient_db_error(e) is True


def test_is_transient_recognises_connection_reset():
    e = OperationalError("stmt", {}, Exception("connection reset by peer"))
    assert is_transient_db_error(e) is True


def test_is_transient_recognises_ssl_syscall_error():
    e = OperationalError("stmt", {}, Exception("SSL SYSCALL error: EOF detected"))
    assert is_transient_db_error(e) is True


def test_is_transient_skips_unique_violation():
    e = IntegrityError("stmt", {}, Exception("duplicate key value violates unique constraint"))
    assert is_transient_db_error(e) is False


def test_is_transient_skips_random_runtime_error():
    assert is_transient_db_error(RuntimeError("not a db error")) is False


# ── middleware behavior ────────────────────────────────────────────


def _build_app_with_middleware(handler):
    app = FastAPI()
    app.middleware("http")(retry_on_transient_db_errors)
    app.post("/webhook")(handler)
    return TestClient(app, raise_server_exceptions=False)


def test_middleware_passes_through_when_no_error():
    def handler():
        return {"ok": True}
    client = _build_app_with_middleware(handler)
    r = client.post("/webhook")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_middleware_retries_once_then_succeeds():
    """First call raises a transient error; second call succeeds."""
    call_count = {"n": 0}

    def handler():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OperationalError("x", {}, Exception("server closed"))
        return {"ok": True}

    client = _build_app_with_middleware(handler)
    r = client.post("/webhook")
    assert r.status_code == 200
    assert call_count["n"] == 2


def test_middleware_returns_503_after_retry_also_fails():
    def handler():
        raise OperationalError("x", {}, Exception("server closed"))

    client = _build_app_with_middleware(handler)
    r = client.post("/webhook")
    assert r.status_code == 503


def test_middleware_does_not_retry_logical_errors():
    """IntegrityError must NOT be retried — it's a code/logic bug."""
    call_count = {"n": 0}

    def handler():
        call_count["n"] += 1
        raise IntegrityError("x", {}, Exception("duplicate key"))

    client = _build_app_with_middleware(handler)
    r = client.post("/webhook")
    # Middleware re-raises; FastAPI default error handling returns 500
    assert r.status_code == 500
    assert call_count["n"] == 1  # exactly one call, no retry
