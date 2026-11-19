"""Passwords, cookie sessions, CSRF protection, access control and headers."""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable
from functools import wraps
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import Response, current_app, g, jsonify, request, session

from fvp.models import User, db

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


# --------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ---------------------------------------------------------------- sessions
def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def login_user(user: User) -> None:
    session.clear()  # new session on login: prevents session fixation
    session.permanent = True
    session["uid"] = user.id
    session["sv"] = user.session_version
    session["csrf"] = secrets.token_urlsafe(32)


def logout_user() -> None:
    session.clear()


def current_user() -> User | None:
    if "user" not in g:
        user = None
        uid = session.get("uid")
        if isinstance(uid, int):
            candidate = db().get(User, uid)
            # session_version lets a password change or "log out everywhere"
            # invalidate cookies that were issued earlier.
            if candidate and candidate.is_active and candidate.session_version == session.get("sv"):
                user = candidate
        g.user = user
    return g.user


def error(status: int, code: str, message: str, **extra: Any) -> tuple[Response, int]:
    return jsonify({"error": code, "message": message, **extra}), status


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if current_user() is None:
            return error(401, "unauthenticated", "Please log in.")
        return view(*args, **kwargs)

    return wrapper


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if user is None:
            return error(401, "unauthenticated", "Please log in.")
        if not user.is_admin:
            return error(403, "forbidden", "Administrator access required.")
        return view(*args, **kwargs)

    return wrapper


def rate_limit_key() -> str:
    user = current_user()
    return f"user:{user.id}" if user else f"ip:{request.remote_addr}"


# -------------------------------------------------------------------- CSRF
def csrf_protect() -> tuple[Response, int] | None:
    """Reject cross-site state-changing requests.

    Two independent checks: the Origin header (when the browser sends one)
    must be an allowed origin, and the X-CSRF-Token header must match the
    token stored in the (SameSite=Strict, HttpOnly) session cookie.
    """
    if request.method not in UNSAFE_METHODS or not request.path.startswith("/api/"):
        return None
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") not in current_app.config["FVP_SETTINGS"].allowed_origins:
        return error(403, "csrf_failed", "Cross-origin request rejected.")
    expected = session.get("csrf")
    supplied = request.headers.get("X-CSRF-Token", "")
    if not expected or not hmac.compare_digest(str(expected), supplied):
        return error(403, "csrf_failed", "Missing or invalid CSRF token. Reload the page and try again.")
    return None


# ----------------------------------------------------------------- headers
API_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def add_security_headers(response: Response) -> Response:
    for name, value in API_HEADERS.items():
        response.headers.setdefault(name, value)
    if current_app.config["FVP_SETTINGS"].environment == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response
