from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from flask import current_app, g
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Bumped to sign the user out of every session (logout-all, password change).
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
        }


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (UniqueConstraint("owner_id", "title", name="uq_problems_owner_title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_owner_created", "owner_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(Text)
    provers: Mapped[list[str]] = mapped_column(JSONType)
    time_limit: Mapped[int] = mapped_column(Integer)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)
    verdict: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "verdict": self.verdict,
            "provers": self.provers,
            "time_limit": self.time_limit,
            "created_at": self.created_at.isoformat(),
            "statuses": {r["prover"]: r["status"] for r in self.results},
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.summary(), "source": self.source, "results": self.results}


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def db() -> Session:
    """The request's database session (created on first use, closed at teardown)."""
    if "db" not in g:
        g.db = current_app.extensions["fvp.session_factory"]()
    return g.db


def close_db(_: BaseException | None = None) -> None:
    session = g.pop("db", None)
    if session is not None:
        session.close()


def iter_models() -> Iterator[type[Base]]:
    yield from (User, Problem, Run)
