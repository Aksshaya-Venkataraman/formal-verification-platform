"""Formal Verification Platform: Flask API that runs SPASS, Vampire and Otter."""

from __future__ import annotations

import json
import logging
import sys
from datetime import timedelta

from flask import Flask, jsonify
from flask_limiter.errors import RateLimitExceeded
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from fvp.config import Settings
from fvp.extensions import limiter
from fvp.models import close_db, make_engine, make_session_factory
from fvp.provers import ProverRegistry
from fvp.schemas import RequestValidationError
from fvp.security import add_security_headers, csrf_protect

__version__ = "1.0.0"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()  # type: ignore[call-arg]
    _configure_logging(settings.log_level)

    app = Flask(__name__)
    production = settings.environment == "production"
    app.config.update(
        FVP_SETTINGS=settings,
        SECRET_KEY=settings.secret_key.get_secret_value(),
        DEBUG=False,
        TESTING=settings.environment == "test",
        PROPAGATE_EXCEPTIONS=False,
        MAX_CONTENT_LENGTH=settings.max_request_bytes,
        TRUSTED_HOSTS=settings.allowed_hosts,
        # __Host- cookies must be Secure, host-only and Path=/ (no subdomain can set or read them).
        SESSION_COOKIE_NAME="__Host-fvp_session" if production else "fvp_session",
        SESSION_COOKIE_SECURE=settings.secure_cookies,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_PATH="/",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=settings.session_hours),
        RATELIMIT_STORAGE_URI=settings.rate_limit_storage_uri.get_secret_value(),
        RATELIMIT_HEADERS_ENABLED=True,
    )
    if settings.trust_proxy:
        # Exactly one proxy (Caddy) sits in front; trust only its headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]

    engine = make_engine(settings.database_url.get_secret_value())
    app.extensions["fvp.engine"] = engine
    app.extensions["fvp.session_factory"] = make_session_factory(engine)
    app.extensions["fvp.provers"] = ProverRegistry(
        {"spass": settings.spass_path, "vampire": settings.vampire_path, "otter": settings.otter_path},
        max_concurrent=settings.max_concurrent_provers,
    )
    limiter.init_app(app)

    app.before_request(csrf_protect)
    app.after_request(add_security_headers)
    app.teardown_appcontext(close_db)

    from fvp.api import auth, library, ops, verification

    for blueprint in (auth.bp, verification.bp, library.bp, ops.bp):
        app.register_blueprint(blueprint)

    @app.errorhandler(RequestValidationError)
    def _validation(exc: RequestValidationError):
        return jsonify({"error": "validation_error", "message": "Invalid request.", "details": exc.errors}), 422

    @app.errorhandler(RateLimitExceeded)
    def _rate_limited(exc: RateLimitExceeded):
        return jsonify({"error": "rate_limited", "message": "Too many requests. Please slow down."}), 429

    @app.errorhandler(HTTPException)
    def _http(exc: HTTPException):
        return jsonify({"error": (exc.name or "error").lower().replace(" ", "_"), "message": exc.description}), (
            exc.code or 500
        )

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        app.logger.exception("unhandled error", exc_info=exc)
        return jsonify({"error": "internal_error", "message": "Internal server error."}), 500

    return app
