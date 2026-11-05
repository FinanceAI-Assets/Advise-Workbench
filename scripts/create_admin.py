"""Create the first administrator, or promote an existing account, from the server.

    python -m scripts.create_admin --email admin@example.com --name "Admin Name"

POST /api/admin/users needs a signed-in administrator, so the first one is created here. A new account's
password is read from ADMIN_PASSWORD or prompted for, never taken as an argument, so it stays out of shell
history. An existing account is promoted and keeps its password.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from fastapi import HTTPException
from sqlalchemy import func, select

from src.core.auth import provision_user
from src.core.db.models import User
from src.core.db.session import init_db, session_scope


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default=None, help="full name for a new account")
    args = parser.parse_args()
    email = args.email.strip().lower()
    init_db()
    with session_scope() as db:
        existing = db.scalar(select(User).where(func.lower(User.email) == email))
        if existing is not None:
            existing.role = "admin"
            existing.is_admin = True
            print(f"Promoted {existing.email} to administrator.")
            return 0
        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password for the new administrator: ")
        try:
            created = provision_user(db, email=email, password=password, role="admin", full_name=args.name)
        except HTTPException as exc:
            print(exc.detail, file=sys.stderr)
            return 2
        print(f"Created administrator {created.email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
