from __future__ import annotations

from src.core.db.session import init_db
from src.workflows.orchestrator import prepare_checkpoint_store, run_redis_worker_loop


def main() -> None:
    init_db()
    prepare_checkpoint_store()
    run_redis_worker_loop()


if __name__ == "__main__":
    main()
