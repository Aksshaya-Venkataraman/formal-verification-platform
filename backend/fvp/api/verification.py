from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from fvp.examples import EXAMPLES
from fvp.extensions import limiter
from fvp.models import Run, db
from fvp.provers import ProverBusyError, ProverRegistry, verdict
from fvp.schemas import ValidateRequest, VerifyRequest, parse_body
from fvp.security import current_user, error, login_required
from fvp.tptp import TPTPSyntaxError, parse

bp = Blueprint("verification", __name__, url_prefix="/api")


def registry() -> ProverRegistry:
    return current_app.extensions["fvp.provers"]


def _syntax_error(exc: TPTPSyntaxError):
    return error(400, "syntax_error", exc.message, line=exc.line, column=exc.column)


@bp.get("/provers")
def provers():
    return jsonify(
        {"provers": registry().describe(), "max_time_limit": current_app.config["FVP_SETTINGS"].max_time_limit}
    )


@bp.get("/examples")
def examples():
    return jsonify({"examples": EXAMPLES})


@bp.post("/validate")
@login_required
def validate():
    body = parse_body(ValidateRequest)
    try:
        problem = parse(body.source)
    except TPTPSyntaxError as exc:
        return _syntax_error(exc)
    symbols = problem.symbols()
    return jsonify(
        {
            "valid": True,
            "formulas": len(problem.statements),
            "has_conjecture": problem.conjecture is not None,
            "languages": sorted({s.language for s in problem.statements}),
            "predicates": sorted(f"{n}/{a}" for n, a in symbols["predicates"]),
            "functions": sorted(f"{n}/{a}" for n, a in symbols["functions"]),
        }
    )


@bp.post("/verify")
@login_required
@limiter.limit(lambda: current_app.config["FVP_SETTINGS"].verify_rate_limit)
def verify():
    body = parse_body(VerifyRequest)
    settings = current_app.config["FVP_SETTINGS"]
    if body.time_limit > settings.max_time_limit:
        return error(422, "validation_error", f"time_limit cannot exceed {settings.max_time_limit} seconds.")
    try:
        problem = parse(body.source)
    except TPTPSyntaxError as exc:
        return _syntax_error(exc)
    try:
        results = registry().run(problem, body.provers, body.time_limit)
    except ProverBusyError:
        return error(503, "busy", "All provers are busy. Please try again in a moment.")

    run = Run(
        owner_id=current_user().id,
        title=body.title or "Untitled problem",
        source=body.source,
        provers=body.provers,
        time_limit=body.time_limit,
        results=[r.to_dict() for r in results],
        verdict=verdict(results),
    )
    session = db()
    session.add(run)
    session.commit()
    return jsonify(run.to_dict()), 201
