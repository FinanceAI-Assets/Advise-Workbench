#!/usr/bin/env python3
"""Repo-root launcher for scripts/check_shared_services.py.

Allows running:
  .venv/Scripts/python check_shared_services.py --env .env --ca system --only qdrant,s3,embeddings,telemetry
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "scripts" / "check_shared_services.py"
    if not script.is_file():
        print(f"Missing script: {script}", file=sys.stderr)
        raise SystemExit(2)
    runpy.run_path(str(script), run_name="__main__")
