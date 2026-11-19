from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import func, select, text

from fvp.models import Run, User, db
from fvp.security import admin_required

bp = Blueprint("ops", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/ready")
def ready():
    try:
        db().execute(text("SELECT 1"))
    except Exception:
        return jsonify({"status": "unavailable", "database": "unreachable"}), 503
    provers = current_app.extensions["fvp.provers"].describe()
    return jsonify({"status": "ready", "database": "ok", "provers": {p["name"]: p["available"] for p in provers}})


@bp.get("/admin/stats")
@admin_required
def admin_stats():
    session = db()
    by_verdict = dict(session.execute(select(Run.verdict, func.count()).group_by(Run.verdict)).all())
    return jsonify(
        {
            "users": session.scalar(select(func.count()).select_from(User)) or 0,
            "runs": sum(by_verdict.values()),
            "runs_by_verdict": by_verdict,
            "provers": current_app.extensions["fvp.provers"].describe(),
        }
    )
