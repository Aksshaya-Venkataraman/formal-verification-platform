"""initial schema: users, problems, runs

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("domain", sa.String(60), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "title", name="uq_problems_owner_title"),
    )
    op.create_index("ix_problems_owner_id", "problems", ["owner_id"])

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("provers", json_type, nullable=False),
        sa.Column("time_limit", sa.Integer(), nullable=False),
        sa.Column("results", json_type, nullable=False),
        sa.Column("verdict", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runs_owner_id", "runs", ["owner_id"])
    op.create_index("ix_runs_verdict", "runs", ["verdict"])
    op.create_index("ix_runs_owner_created", "runs", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_table("runs")
    op.drop_table("problems")
    op.drop_table("users")
