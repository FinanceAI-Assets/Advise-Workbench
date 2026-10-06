"""Query OpenObserve with the OPENOBSERVE_* settings from .env.

  python scripts/openobserve_query.py streams
  python scripts/openobserve_query.py sql "SELECT operation_name, duration FROM advise_workbench ORDER BY _timestamp DESC LIMIT 20" --type traces

--type is logs (default), traces or metrics; --minutes sets how far back to look (default 60).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["streams", "sql"])
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--type", default="logs", choices=["logs", "traces", "metrics"])
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()

    base = f"{settings.openobserve_url.rstrip('/')}/api/{settings.openobserve_org}"
    auth = (settings.openobserve_user, settings.openobserve_password)
    if args.command == "streams":
        for kind in ("logs", "traces", "metrics"):
            rows = httpx.get(f"{base}/streams", params={"type": kind}, auth=auth, timeout=30).json().get("list", [])
            for row in rows:
                print(f"{kind:8} {row['name']}")
        return
    now = int(time.time() * 1_000_000)
    body = {"query": {"sql": args.query, "start_time": now - args.minutes * 60 * 1_000_000, "end_time": now, "from": 0, "size": 200}}
    reply = httpx.post(f"{base}/_search", params={"type": args.type}, json=body, auth=auth, timeout=60)
    if reply.status_code != 200:
        sys.exit(f"{reply.status_code}: {reply.text[:500]}")
    for hit in reply.json().get("hits", []):
        print(json.dumps(hit, default=str))


if __name__ == "__main__":
    main()
