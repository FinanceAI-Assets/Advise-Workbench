from __future__ import annotations

import time

from src.core.db.session import init_db
from src.guardrails.data_protection.service import process_due_breach_notifications


def main() -> None:
    init_db()
    while True:
        process_due_breach_notifications()
        time.sleep(30)


if __name__ == "__main__":
    main()
