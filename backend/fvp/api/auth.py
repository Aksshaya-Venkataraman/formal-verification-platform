from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fvp.extensions import limiter
from fvp.models import User, db
from fvp.schemas import Credentials, PasswordChange, Registration, parse_body
from fvp.security import (
    csrf_token,
    current_user,
    error,
    hash_password,
    login_required,
    login_user,
    logout_user,
    needs_rehash,
    verify_password,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
log = logging.getLogger(__name__)


def _limit(name: str):
    return lambda: getattr(current_app.config["FVP_SETTINGS"], name)


@bp.get("/csrf")
def get_csrf():
    """The SPA calls this once; the token must accompany every POST/PUT/DELETE."""
    return jsonify({"csrf_token": csrf_token()})


@bp.post("/register")
@limiter.limit(_limit("register_rate_limit"), key_func=lambda: "register")
def register():
    body = parse_body(Registration)
    user = User(email=body.email, password_hash=hash_password(body.password))
    session = db()
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return error(400, "registration_failed", "Registration failed.")  # do not reveal existing accounts
    login_user(user)
    return jsonify({"user": user.to_dict(), "csrf_token": csrf_token()}), 201


@bp.post("/login")
@limiter.limit(_limit("login_rate_limit"))
def login():
    body = parse_body(Credentials)
    session = db()
    user = session.scalar(select(User).where(User.email == body.email))
    valid = verify_password(body.password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        log.info("failed login")
        return error(401, "invalid_credentials", "Invalid email or password.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        session.commit()
    login_user(user)
    return jsonify({"user": user.to_dict(), "csrf_token": csrf_token()})


@bp.post("/logout")
def logout():
    logout_user()
    return jsonify({"csrf_token": csrf_token()})


@bp.post("/logout-all")
@login_required
def logout_all():
    user = current_user()
    user.session_version += 1
    db().commit()
    logout_user()
    return jsonify({"csrf_token": csrf_token()})


@bp.get("/me")
def me():
    user = current_user()
    return jsonify({"user": user.to_dict() if user else None, "csrf_token": csrf_token()})


@bp.post("/change-password")
@login_required
@limiter.limit(_limit("login_rate_limit"))
def change_password():
    body = parse_body(PasswordChange)
    user = current_user()
    if not verify_password(body.current_password, user.password_hash):
        return error(400, "invalid_password", "Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    user.session_version += 1  # sign out every other session
    db().commit()
    login_user(user)
    return jsonify({"message": "Password changed.", "csrf_token": csrf_token()})
