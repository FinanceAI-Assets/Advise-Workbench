"""Check the configured model provider from the command line.

    python -m src.llm check            # config + readiness, spends no tokens
    python -m src.llm check --ping     # also sends one tiny request to prove credentials work
    python -m src.llm providers        # list every LLM_PROVIDER value

Exit code 0 when healthy, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from src.llm import gateway
from src.llm.config import SUPPORTED_NAMES
from src.llm.errors import LLMError


def _check(ping: bool, as_json: bool) -> int:
    report = gateway.health()
    if ping and report.get("ok"):
        started = time.perf_counter()
        try:
            msg = gateway.create_message(
                model=gateway.model_for("default"),
                max_tokens=16,
                system="Reply tersely.",
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            text = "".join(
                str(b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "") or "")
                for b in getattr(msg, "content", []) or []
            ).strip()
            report["ping"] = {"ok": bool(text), "reply": text[:80], "latency_ms": round((time.perf_counter() - started) * 1000)}
        except LLMError as exc:
            report["ping"] = {"ok": False, "error": str(exc)[:500]}
        report["ok"] = report["ok"] and report["ping"]["ok"]
    if as_json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"provider:     {report.get('provider')}")
        if report.get("models"):
            print(f"models:       {report['models']}")
        if report.get("capabilities"):
            enabled = [k for k, v in report["capabilities"].items() if v]
            print(f"capabilities: {', '.join(enabled) or 'none'}")
        if report.get("fallback"):
            print(f"fallback:     {report['fallback']}")
        for key, value in (report.get("info") or {}).items():
            print(f"{key + ':':<14}{value}")
        print(f"status:       {'OK' if report.get('ok') else 'NOT READY'} - {report.get('detail', '')}")
        if "ping" in report:
            p = report["ping"]
            print(f"ping:         {'OK' if p['ok'] else 'FAILED'} {p.get('reply') or p.get('error') or ''} {p.get('latency_ms', '')}ms")
    return 0 if report.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.llm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="validate the configured provider")
    check.add_argument("--ping", action="store_true", help="send one tiny request (spends a few tokens)")
    check.add_argument("--json", action="store_true", help="machine-readable output")
    sub.add_parser("providers", help="list supported LLM_PROVIDER values")
    args = parser.parse_args(argv)
    if args.command == "providers":
        print("\n".join(SUPPORTED_NAMES))
        return 0
    return _check(args.ping, args.json)


if __name__ == "__main__":
    sys.exit(main())
