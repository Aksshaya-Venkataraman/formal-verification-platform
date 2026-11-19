from __future__ import annotations

import secrets
import shutil

import pytest

from fvp import create_app
from fvp.config import Settings
from fvp.extensions import limiter
from fvp.models import Base

PASSWORD = "correct-horse-battery-staple"
ALL_PROVERS_INSTALLED = all(shutil.which(b) for b in ("SPASS", "vampire", "otter"))
needs_provers = pytest.mark.skipif(not ALL_PROVERS_INSTALLED, reason="SPASS, Vampire and Otter must be installed")


def make_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "secret_key": secrets.token_urlsafe(48),
        "database_url": "sqlite://",
        "allowed_origins": "http://localhost",
        "login_rate_limit": "100/minute",
        "register_rate_limit": "100/minute",
        "verify_rate_limit": "100/minute",
        "max_time_limit": 10,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def make_app():
    def factory(**overrides):
        app = create_app(make_settings(**overrides))
        Base.metadata.create_all(app.extensions["fvp.engine"])
        limiter.reset()
        return app

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


class ApiClient:
    """Test client that behaves like the SPA: keeps the CSRF token current."""

    def __init__(self, app) -> None:
        self.http = app.test_client()
        self.csrf = self.http.get("/api/auth/csrf").get_json()["csrf_token"]

    def _send(self, method: str, url: str, **kwargs):
        headers = {"X-CSRF-Token": self.csrf, **kwargs.pop("headers", {})}
        response = getattr(self.http, method)(url, headers=headers, **kwargs)
        body = response.get_json(silent=True)
        if isinstance(body, dict) and "csrf_token" in body:
            self.csrf = body["csrf_token"]
        return response

    def get(self, url, **kw):
        return self.http.get(url, **kw)

    def post(self, url, **kw):
        return self._send("post", url, **kw)

    def put(self, url, **kw):
        return self._send("put", url, **kw)

    def delete(self, url, **kw):
        return self._send("delete", url, **kw)

    def register(self, email: str, password: str = PASSWORD):
        response = self.post("/api/auth/register", json={"email": email, "password": password})
        assert response.status_code == 201, response.get_json()
        return response


@pytest.fixture
def client(app) -> ApiClient:
    return ApiClient(app)


@pytest.fixture
def user(client) -> ApiClient:
    client.register("alice@example.com")
    return client


@pytest.fixture
def other(app) -> ApiClient:
    c = ApiClient(app)
    c.register("mallory@example.com")
    return c
