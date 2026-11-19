"""Operator commands.

python cli.py create-admin --email you@example.com   (password from ADMIN_PASSWORD or a prompt)
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy import select

from fvp.config import Settings
from fvp.models import User, make_engine, make_session_factory
from fvp.schemas import Registration
from fvp.security import hash_password


def create_admin(email: str, password: str) -> str:
    try:
        data = Registration(email=email, password=password)
    except ValidationError as exc:
        raise SystemExit(f"invalid email or password: {exc.errors()[0]['msg']}") from None
    engine = make_engine(Settings().database_url.get_secret_value())  # type: ignore[call-arg]
    with make_session_factory(engine)() as db:
        user = db.scalar(select(User).where(User.email == data.email))
        action = "promoted"
        if user is None:
            user = User(email=data.email, password_hash=hash_password(data.password))
            db.add(user)
            action = "created"
        user.is_admin, user.is_active = True, True
        user.password_hash = hash_password(data.password)
        user.session_version = (user.session_version or 1) + 1
        db.commit()
    engine.dispose()
    return action


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cli.py")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create-admin").add_argument("--email", required=True)
    args = parser.parse_args(argv)
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password (min 12 chars): ")
    print(f"admin {args.email} {create_admin(args.email, password)}", file=sys.stderr)


if __name__ == "__main__":
    main()
