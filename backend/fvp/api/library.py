"""Saved problems and run history. Every query is restricted to the current user."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from fvp.models import Problem, Run, db
from fvp.schemas import ProblemIn, parse_body
from fvp.security import current_user, error, login_required
from fvp.tptp import TPTPSyntaxError, parse

bp = Blueprint("library", __name__, url_prefix="/api")


def _page() -> tuple[int, int]:
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
        offset = min(max(int(request.args.get("offset", 0)), 0), 100_000)
    except ValueError:
        limit, offset = 20, 0
    return limit, offset


def _owned[T: (Problem, Run)](model: type[T], object_id: int) -> T | None:
    return db().scalar(select(model).where(model.id == object_id, model.owner_id == current_user().id))


def _not_found(kind: str):
    return error(404, "not_found", f"{kind} not found.")


# ---------------------------------------------------------------- problems
@bp.get("/problems")
@login_required
def list_problems():
    rows = (
        db()
        .scalars(select(Problem).where(Problem.owner_id == current_user().id).order_by(Problem.updated_at.desc()))
        .all()
    )
    return jsonify({"problems": [p.to_dict() for p in rows]})


@bp.post("/problems")
@login_required
def create_problem():
    body = parse_body(ProblemIn)
    try:
        parse(body.source)
    except TPTPSyntaxError as exc:
        return error(400, "syntax_error", exc.message, line=exc.line, column=exc.column)
    problem = Problem(owner_id=current_user().id, **body.model_dump())
    session = db()
    session.add(problem)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return error(409, "duplicate_title", "You already have a problem with this title.")
    return jsonify(problem.to_dict()), 201


@bp.get("/problems/<int:problem_id>")
@login_required
def get_problem(problem_id: int):
    problem = _owned(Problem, problem_id)
    return jsonify(problem.to_dict()) if problem else _not_found("Problem")


@bp.put("/problems/<int:problem_id>")
@login_required
def update_problem(problem_id: int):
    problem = _owned(Problem, problem_id)
    if problem is None:
        return _not_found("Problem")
    body = parse_body(ProblemIn)
    try:
        parse(body.source)
    except TPTPSyntaxError as exc:
        return error(400, "syntax_error", exc.message, line=exc.line, column=exc.column)
    for field, value in body.model_dump().items():
        setattr(problem, field, value)
    session = db()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return error(409, "duplicate_title", "You already have a problem with this title.")
    return jsonify(problem.to_dict())


@bp.delete("/problems/<int:problem_id>")
@login_required
def delete_problem(problem_id: int):
    problem = _owned(Problem, problem_id)
    if problem is None:
        return _not_found("Problem")
    session = db()
    session.delete(problem)
    session.commit()
    return "", 204


# -------------------------------------------------------------------- runs
@bp.get("/runs")
@login_required
def list_runs():
    limit, offset = _page()
    owner = Run.owner_id == current_user().id
    session = db()
    rows = session.scalars(
        select(Run).where(owner).order_by(Run.created_at.desc(), Run.id.desc()).limit(limit).offset(offset)
    ).all()
    total = session.scalar(select(func.count()).select_from(Run).where(owner)) or 0
    return jsonify({"runs": [r.summary() for r in rows], "total": total, "limit": limit, "offset": offset})


@bp.get("/runs/<int:run_id>")
@login_required
def get_run(run_id: int):
    run = _owned(Run, run_id)
    return jsonify(run.to_dict()) if run else _not_found("Run")


@bp.delete("/runs/<int:run_id>")
@login_required
def delete_run(run_id: int):
    run = _owned(Run, run_id)
    if run is None:
        return _not_found("Run")
    session = db()
    session.delete(run)
    session.commit()
    return "", 204
