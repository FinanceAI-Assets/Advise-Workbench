#!/usr/bin/env bash
#
# Advise Workbench: check the environment, then run bridge + backend + frontend together.
#
#   ./scripts/run_agent.sh           prechecks, then start everything (Ctrl+C stops it all)
#   ./scripts/run_agent.sh --check   prechecks only
#   ./scripts/run_agent.sh --fix     prechecks, repairing what is safe to repair, then start
#   ./scripts/run_agent.sh --check --fix   repair, report, and exit
#
# Works with macOS's stock bash 3.2. Ports can be overridden: BRIDGE_PORT, BACKEND_PORT, FRONTEND_PORT.
# With OPENOBSERVE_ENABLED=true in .env, OpenObserve (monitoring) is started as well: ./scripts/openobserve.sh setup

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
ENV_FILE="$ROOT/.env"
ENV_EXAMPLE="$ROOT/.env.example"
VENV="$ROOT/.venv"
VPY="$VENV/bin/python"
BRIDGE="$ROOT/scripts/claude_cli_bridge.py"
RUN_DIR="$ROOT/.run"
BRIDGE_PORT="${BRIDGE_PORT:-8787}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

CHECK_ONLY=0
FIX=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --fix) FIX=1 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (use --check, --fix or --help)"; exit 2 ;;
  esac
done

PASS_N=0; WARN_N=0; FAIL_N=0
pass() { PASS_N=$((PASS_N + 1)); printf '  PASS  %s\n' "$1"; }
warn() { WARN_N=$((WARN_N + 1)); printf '  WARN  %s\n' "$1"; [ -n "${2:-}" ] && printf '        -> %s\n' "$2"; }
fail() { FAIL_N=$((FAIL_N + 1)); printf '  FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '        -> %s\n' "$2"; }
fixed() { PASS_N=$((PASS_N + 1)); printf '  FIXED %s\n' "$1"; }
section() { printf '\n%s\n' "$1"; }

# Last uncommented KEY=value in .env, quotes stripped.
env_get() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}
env_append() {
  [ -n "$(tail -c1 "$ENV_FILE" 2>/dev/null)" ] && echo >> "$ENV_FILE"
  printf '%s\n' "$1" >> "$ENV_FILE"
}
http_ok() { curl -s -m 3 -o /dev/null "$1" 2>/dev/null; }
port_owner() { lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1 " (pid " $2 ")"}'; }

# ------------------------------------------------------------------------------- prechecks
section "Tools"
PY=""
for cand in python3.11 python3.12 python3.13 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$(command -v "$cand")"; break
  fi
done
if [ -n "$PY" ]; then pass "Python $("$PY" -c 'import platform; print(platform.python_version())') ($PY)"
else fail "Python 3.11 or newer not found" "brew install python@3.11"; fi

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
  if [ "$NODE_MAJOR" -ge 18 ]; then pass "Node $(node --version)"; else fail "Node $(node --version) is older than 18" "brew install node"; fi
else fail "Node not found" "brew install node"; fi
command -v npm >/dev/null 2>&1 && pass "npm $(npm --version)" || fail "npm not found" "brew install node"
command -v git >/dev/null 2>&1 && pass "git present" || fail "git not found" "xcode-select --install"

section "Environment file (.env)"
if [ ! -f "$ENV_FILE" ]; then
  if [ "$FIX" = 1 ] && [ -f "$ENV_EXAMPLE" ]; then cp "$ENV_EXAMPLE" "$ENV_FILE"; fixed "created .env from .env.example"
  else fail ".env is missing" "cp .env.example .env   (or run with --fix)"; fi
else pass ".env exists"; fi

if [ -f "$ENV_FILE" ]; then
  JWT="$(env_get JWT_SECRET)"
  if [ "${#JWT}" -ge 16 ] && [ "$JWT" != "change-me-to-a-long-random-string" ]; then pass "JWT_SECRET is set"
  elif [ "$FIX" = 1 ] && [ -n "$PY" ]; then
    NEW_SECRET="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(32))')"
    grep -v -E '^JWT_SECRET=' "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
    env_append "JWT_SECRET=$NEW_SECRET"; fixed "generated a JWT_SECRET"
  else fail "JWT_SECRET is missing, too short or still the placeholder" "run with --fix to generate one"; fi
fi

section "Model access"
# Provider: LLM_PROVIDER in .env, else `provider:` in config/model_config.yaml, else anthropic.
PROVIDER="$(env_get LLM_PROVIDER)"
[ -z "$PROVIDER" ] && PROVIDER="$(sed -n 's/^provider:[[:space:]]*\([a-z_]*\).*/\1/p' "$ROOT/config/model_config.yaml" 2>/dev/null | head -n 1)"
PROVIDER="${PROVIDER:-anthropic}"
BASE_URL="$(env_get ANTHROPIC_BASE_URL)"
API_KEY="$(env_get ANTHROPIC_API_KEY)"
BRIDGE_MODE=0
USES_CLI=0
if [ "$PROVIDER" = "anthropic" ]; then
  case "$BASE_URL" in *127.0.0.1:"$BRIDGE_PORT"*|*localhost:"$BRIDGE_PORT"*) BRIDGE_MODE=1 ;; esac
fi

check_claude_cli() {
  if command -v claude >/dev/null 2>&1; then
    CLI_WORK="${TMPDIR:-/tmp}/advise-cli-check"; mkdir -p "$CLI_WORK"
    REPLY="$(cd "$CLI_WORK" && echo 'Reply with exactly: OK' | perl -e 'alarm 90; exec @ARGV' claude -p --model claude-haiku-4-5 \
      --system-prompt 'Terse.' --tools '' --setting-sources '' --strict-mcp-config --no-session-persistence 2>&1 | tail -n 1)"
    case "$REPLY" in *OK*) pass "claude CLI $(claude --version 2>/dev/null | head -n 1) is signed in and answers" ;;
      *) fail "claude CLI did not answer a test prompt: ${REPLY:0:160}" "run 'claude' once and sign in; if the command is broken: npm install -g @anthropic-ai/claude-code" ;; esac
  else fail "claude CLI not found" "npm install -g @anthropic-ai/claude-code   then run 'claude' and sign in"; fi
}

case "$PROVIDER" in
  claude_cli)
    USES_CLI=1
    pass "provider claude_cli: the backend calls the Claude Code CLI directly (no bridge, no API key)"
    check_claude_cli ;;
  openai_compatible)
    LLM_MODEL_SET="$(env_get LLM_MODEL)"
    [ -z "$LLM_MODEL_SET" ] && LLM_MODEL_SET="$(awk '/^models:/{f=1;next} f&&/^[^ ]/{f=0} f&&/default:/{gsub(/.*default:[[:space:]]*|"|#.*/,""); print; exit}' "$ROOT/config/model_config.yaml" 2>/dev/null | tr -d '[:space:]')"
    if [ -n "$LLM_MODEL_SET" ]; then pass "provider openai_compatible, model $LLM_MODEL_SET"
    else fail "provider openai_compatible needs a model" "set LLM_MODEL in .env or models.default in config/model_config.yaml"; fi
    if [ -n "$(env_get LLM_API_KEY)" ] || [ -n "$(env_get LLM_BASE_URL)" ]; then pass "LLM_API_KEY or LLM_BASE_URL is set (not validated here)"
    else fail "provider openai_compatible needs LLM_API_KEY (or LLM_BASE_URL for a local server)" "add it to .env"; fi ;;
  anthropic)
    if [ "$BRIDGE_MODE" = 1 ]; then
      USES_CLI=1
      pass "bridge mode: backend sends model calls to $BASE_URL"
      [ -n "$API_KEY" ] && pass "placeholder ANTHROPIC_API_KEY present (the app needs it non-empty)" \
        || fail "ANTHROPIC_API_KEY is empty; the app then treats the model as not configured" "add ANTHROPIC_API_KEY=not-used-cli-bridge to .env"
      [ -f "$BRIDGE" ] && pass "bridge script present" || fail "scripts/claude_cli_bridge.py is missing"
      check_claude_cli
    elif [ -n "$API_KEY" ] && [ "$API_KEY" != "your_api_key_here" ]; then
      pass "API mode: ANTHROPIC_API_KEY is set (not validated here)"
    else
      fail "no model access configured" "set a real ANTHROPIC_API_KEY, or LLM_PROVIDER=claude_cli to use the signed-in Claude Code CLI, or see docs/04-development/model-providers.md"
    fi ;;
  *) fail "unknown LLM_PROVIDER '$PROVIDER'" "use anthropic, claude_cli or openai_compatible" ;;
esac

if [ "$USES_CLI" = 1 ]; then
  # Calls through the CLI are slow: give runs more time and no token cap.
  STUCK="$(env_get RUN_STUCK_TIMEOUT_SEC)"; STUCK="${STUCK:-600}"
  if [ "$STUCK" = 0 ] || [ "$STUCK" -ge 1800 ] 2>/dev/null; then pass "RUN_STUCK_TIMEOUT_SEC=$STUCK"
  elif [ "$FIX" = 1 ]; then env_append "RUN_STUCK_TIMEOUT_SEC=1800"; fixed "set RUN_STUCK_TIMEOUT_SEC=1800"
  else warn "RUN_STUCK_TIMEOUT_SEC is $STUCK; slow CLI runs are cut off after that many seconds without progress" "add RUN_STUCK_TIMEOUT_SEC=1800 (or run with --fix)"; fi
  CAP="$(env_get ANTHROPIC_MAX_TOKENS_PER_RUN)"; CAP="${CAP:-50000}"
  if [ "$CAP" = 0 ]; then pass "per-run token cap is off"
  elif [ "$FIX" = 1 ]; then env_append "ANTHROPIC_MAX_TOKENS_PER_RUN=0"; fixed "set ANTHROPIC_MAX_TOKENS_PER_RUN=0"
  else warn "per-run token cap is $CAP; a full deck run exceeds it and later model calls are rejected" "add ANTHROPIC_MAX_TOKENS_PER_RUN=0 (or run with --fix)"; fi
fi

pass "run orchestrator: LangGraph (runs resume from checkpoints after a restart)"

section "Backend packages"
if [ ! -x "$VPY" ]; then
  if [ "$FIX" = 1 ] && [ -n "$PY" ]; then
    echo "        creating virtual environment and installing packages (several minutes)..."
    if "$PY" -m venv "$VENV" && "$VPY" -m pip install -q -r "$ROOT/requirements-dev.txt"; then
      fixed "created .venv and installed packages"
    else fail "package installation failed" "$PY -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"; fi
  else fail ".venv is missing" "run with --fix, or: python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"; fi
fi
if [ -x "$VPY" ]; then
  MISSING="$("$VPY" - <<'PYEOF' 2>/dev/null
import importlib
names = ["fastapi", "uvicorn", "sqlalchemy", "alembic", "anthropic", "pptx", "docx", "openpyxl", "reportlab", "sentence_transformers", "faiss"]
print(" ".join(n for n in names if importlib.util.find_spec(n) is None))
PYEOF
)"
  if [ -z "$MISSING" ]; then pass "key Python packages are installed"
  elif [ "$FIX" = 1 ] && "$VPY" -m pip install -q -r "$ROOT/requirements-dev.txt"; then fixed "installed missing packages: $MISSING"
  else fail "missing Python packages: $MISSING" ".venv/bin/pip install -r requirements-dev.txt"; fi

  ANTHROPIC_V="$("$VPY" -c 'from importlib.metadata import version; print(version("anthropic"))' 2>/dev/null)"
  case "$ANTHROPIC_V" in
    0.*) pass "anthropic $ANTHROPIC_V (below 1.0, as this code needs)" ;;
    "") : ;;
    *) if [ "$FIX" = 1 ] && "$VPY" -m pip install -q -r "$ROOT/requirements.txt"; then fixed "reinstalled pinned packages (anthropic below 1.0)"
       else fail "anthropic $ANTHROPIC_V rejects the 'temperature' argument this code sends" ".venv/bin/pip install -r requirements.txt"; fi ;;
  esac
fi

section "Frontend packages"
if [ ! -x "$FRONTEND/node_modules/.bin/next" ]; then
  if [ "$FIX" = 1 ] && (cd "$FRONTEND" && npm install --no-fund --no-audit >/dev/null 2>&1); then fixed "ran npm install"
  else fail "frontend packages are not installed" "cd frontend && npm install   (or run with --fix)"; fi
elif [ "$FRONTEND/package-lock.json" -nt "$FRONTEND/node_modules/.package-lock.json" ]; then
  if [ "$FIX" = 1 ] && (cd "$FRONTEND" && npm install --no-fund --no-audit >/dev/null 2>&1); then fixed "refreshed frontend packages (npm install)"
  else warn "package-lock.json changed after the last npm install; packages may be out of date" "cd frontend && npm install   (or run with --fix)"; fi
else pass "frontend packages are installed"; fi

section "Database and folders"
WORKSPACE_ROOT="$(env_get WORKSPACE_ROOT)"; WORKSPACE_ROOT="${WORKSPACE_ROOT:-./workspace}"
case "$WORKSPACE_ROOT" in /*) WS="$WORKSPACE_ROOT" ;; *) WS="$ROOT/${WORKSPACE_ROOT#./}" ;; esac
mkdir -p "$WS/leading_practices/wiki" && pass "workspace folder ready ($WS)"
DB="$ROOT/advise_workbench.db"
if [ -n "$(env_get DATABASE_URL)" ]; then
  pass "DATABASE_URL is set (external database; local checks skipped)"
elif [ ! -f "$DB" ]; then
  pass "no database yet; it is created on first start"
  if [ "$(env_get AUTH_ALLOW_SELF_SIGNUP)" = "true" ]; then :
  elif [ "$FIX" = 1 ]; then env_append "AUTH_ALLOW_SELF_SIGNUP=true"; fixed "set AUTH_ALLOW_SELF_SIGNUP=true so the first sign-in can create a user"
  else warn "AUTH_ALLOW_SELF_SIGNUP is not true; the first sign-in cannot create a user" "add AUTH_ALLOW_SELF_SIGNUP=true to .env (or run with --fix)"; fi
elif [ -x "$VPY" ]; then
  DB_STATE="$("$VPY" - "$DB" <<'PYEOF' 2>&1
import sqlite3, sys
c = sqlite3.connect(sys.argv[1], timeout=5)
tables = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
users = c.execute("select count(*) from users").fetchone()[0] if "users" in tables else 0
key = sorted(r[1] for r in c.execute("pragma table_info(run_tasks)") if r[5])
print(f"ok users={users} key={'+'.join(key) or 'none'}")
PYEOF
)"
  case "$DB_STATE" in
    ok*) pass "database opens"
      case "$DB_STATE" in *users=0*)
        if [ "$(env_get AUTH_ALLOW_SELF_SIGNUP)" = "true" ]; then :
        elif [ "$FIX" = 1 ]; then env_append "AUTH_ALLOW_SELF_SIGNUP=true"; fixed "set AUTH_ALLOW_SELF_SIGNUP=true so the first sign-in can create a user"
        else warn "no users yet and AUTH_ALLOW_SELF_SIGNUP is not true; sign-in will be rejected" "add AUTH_ALLOW_SELF_SIGNUP=true to .env (or run with --fix)"; fi ;;
      esac
      case "$DB_STATE" in
        *key=id+run_id*|*key=none*) : ;;
        *) pass "run checklist table has the old key; the backend rebuilds it on start-up" ;;
      esac ;;
    *) fail "database could not be read: ${DB_STATE:0:160}" ;;
  esac
fi

section "Ports"
BRIDGE_UP=0; BACKEND_UP=0; FRONTEND_UP=0
check_port() { # name port health-url ; echoes up | free | busy:<owner>
  if http_ok "$3"; then echo up; return; fi
  owner="$(port_owner "$2")"
  if [ -n "$owner" ]; then echo "busy:$owner"; else echo free; fi
}
if [ "$BRIDGE_MODE" = 1 ]; then
  S="$(check_port bridge "$BRIDGE_PORT" "http://127.0.0.1:$BRIDGE_PORT/")"
  case "$S" in up) BRIDGE_UP=1; pass "bridge already running on $BRIDGE_PORT" ;; free) pass "port $BRIDGE_PORT is free for the bridge" ;;
    *) fail "port $BRIDGE_PORT is used by ${S#busy:}" "stop that process or set BRIDGE_PORT" ;; esac
fi
S="$(check_port backend "$BACKEND_PORT" "http://127.0.0.1:$BACKEND_PORT/health")"
case "$S" in up) BACKEND_UP=1; pass "backend already running on $BACKEND_PORT" ;; free) pass "port $BACKEND_PORT is free for the backend" ;;
  *) fail "port $BACKEND_PORT is used by ${S#busy:}" "stop that process or set BACKEND_PORT" ;; esac
S="$(check_port frontend "$FRONTEND_PORT" "http://localhost:$FRONTEND_PORT/")"
case "$S" in up) FRONTEND_UP=1; pass "frontend already running on $FRONTEND_PORT" ;; free) pass "port $FRONTEND_PORT is free for the frontend" ;;
  *) fail "port $FRONTEND_PORT is used by ${S#busy:}" "stop that process or set FRONTEND_PORT" ;; esac

OO_ENABLED="$(env_get OPENOBSERVE_ENABLED)"
OO_URL="$(env_get OPENOBSERVE_URL)"; OO_URL="${OO_URL:-http://localhost:5080}"
OO_PORT="$(echo "$OO_URL" | sed -E 's#.*:([0-9]+)/?$#\1#')"
OO_UP=0
if [ "$OO_ENABLED" = "true" ]; then
  S="$(check_port openobserve "$OO_PORT" "$OO_URL/healthz")"
  case "$S" in up) OO_UP=1; pass "OpenObserve already running on $OO_PORT" ;;
    free) if [ -x "$ROOT/.tools/openobserve/openobserve" ]; then pass "port $OO_PORT is free for OpenObserve"
          else fail "OPENOBSERVE_ENABLED=true but OpenObserve is not installed" "./scripts/openobserve.sh setup"; fi ;;
    *) fail "port $OO_PORT is used by ${S#busy:}" "stop that process or change OPENOBSERVE_URL" ;; esac
fi

section "Optional tools"
[ "$OO_ENABLED" = "true" ] || warn "OpenObserve monitoring is off: no traces, metrics or logs are collected" "./scripts/openobserve.sh setup"
if command -v soffice >/dev/null 2>&1 || [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then pass "LibreOffice present"
else warn "LibreOffice not installed: visual QA works on a degraded render of decks and documents" "brew install --cask libreoffice"; fi
if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then pass "Redis is running"
else warn "Redis not running: in-process cache and queue are used (fine for one machine)" "brew install redis && brew services start redis"; fi
command -v tesseract >/dev/null 2>&1 && pass "Tesseract present" || warn "Tesseract not installed: scanned PDFs cannot be read" "brew install tesseract poppler"

printf '\nPrechecks: %d passed, %d warnings, %d failed\n' "$PASS_N" "$WARN_N" "$FAIL_N"
if [ "$FAIL_N" -gt 0 ]; then
  echo "Fix the FAIL items above and run again (--fix repairs the ones marked 'run with --fix')."
  exit 1
fi
[ "$CHECK_ONLY" = 1 ] && exit 0

# --------------------------------------------------------------------------------- start
mkdir -p "$RUN_DIR"
STARTED_PIDS=""
TAIL_PIDS=""

kill_tree() { # stop a process and everything it started
  for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
  kill "$1" 2>/dev/null
}
cleanup() {
  trap - INT TERM EXIT
  printf '\nStopping...\n'
  exec 2>/dev/null  # hide the shell's "Terminated" notices for the processes stopped below
  for pid in $STARTED_PIDS; do kill_tree "$pid"; done
  for pid in $TAIL_PIDS; do kill "$pid"; done
  pkill -f "tail -n \+1 -F $RUN_DIR/" || true
  wait
  rm -f "$RUN_DIR"/*.pid
  exit "${1:-0}"
}
trap 'cleanup 0' INT TERM

start_service() { # name workdir command...
  name="$1"; workdir="$2"; shift 2
  log="$RUN_DIR/$name.log"; : > "$log"
  (cd "$workdir" && exec "$@" >> "$log" 2>&1) &
  pid=$!
  echo "$pid" > "$RUN_DIR/$name.pid"
  STARTED_PIDS="$STARTED_PIDS $pid"
  tail -n +1 -F "$log" 2>/dev/null | awk -v p="[$name] " '{ print p $0; fflush() }' &
  TAIL_PIDS="$TAIL_PIDS $!"
  eval "PID_$name=$pid"
}
wait_http() { # name url seconds pid
  started=$SECONDS
  while [ $((SECONDS - started)) -lt "$3" ]; do
    http_ok "$2" && return 0
    kill -0 "$4" 2>/dev/null || { echo "[$1] exited during start-up; see $RUN_DIR/$1.log"; return 1; }
    # uvicorn's reloader stays alive when the app itself fails to start, so check its log as well
    if grep -q "Application startup failed" "$RUN_DIR/$1.log" 2>/dev/null; then
      echo "[$1] failed to start; see the error above or in $RUN_DIR/$1.log"; return 1
    fi
    sleep 1
  done
  echo "[$1] did not answer at $2 within $3 seconds; see $RUN_DIR/$1.log"; return 1
}

printf '\nStarting services (logs in %s)\n' "$RUN_DIR"
if [ "$BRIDGE_MODE" = 1 ] && [ "$BRIDGE_UP" = 0 ]; then
  start_service bridge "$ROOT" "$PY" "$BRIDGE" --port "$BRIDGE_PORT" --claude "$(command -v claude)"
  wait_http bridge "http://127.0.0.1:$BRIDGE_PORT/" 20 "$PID_bridge" || cleanup 1
fi
if [ "$OO_ENABLED" = "true" ] && [ "$OO_UP" = 0 ]; then
  start_service openobserve "$ROOT" "$ROOT/scripts/openobserve.sh" start
  wait_http openobserve "$OO_URL/healthz" 60 "$PID_openobserve" || cleanup 1
fi
if [ "$BACKEND_UP" = 0 ]; then
  start_service backend "$ROOT" "$VENV/bin/uvicorn" src.app.main:app --reload --reload-dir src --host 0.0.0.0 --port "$BACKEND_PORT"
  wait_http backend "http://127.0.0.1:$BACKEND_PORT/health" 120 "$PID_backend" || cleanup 1
fi
if [ "$FRONTEND_UP" = 0 ]; then
  export API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT"
  start_service frontend "$FRONTEND" npm run dev -- -p "$FRONTEND_PORT"
  wait_http frontend "http://localhost:$FRONTEND_PORT/" 120 "$PID_frontend" || cleanup 1
fi

printf '\nReady.\n'
[ "$BRIDGE_MODE" = 1 ] && printf '  Bridge    http://127.0.0.1:%s\n' "$BRIDGE_PORT"
printf '  Backend   http://127.0.0.1:%s   (API docs at /docs)\n' "$BACKEND_PORT"
printf '  Frontend  http://localhost:%s\n' "$FRONTEND_PORT"
[ "$OO_ENABLED" = "true" ] && printf '  Monitoring %s   (sign in with OPENOBSERVE_USER / OPENOBSERVE_PASSWORD from .env)\n' "$OO_URL"
if [ -z "$STARTED_PIDS" ]; then
  echo "Everything was already running; nothing was started by this script."
  exit 0
fi
printf 'Press Ctrl+C to stop what this script started.\n\n'

while true; do
  for pid in $STARTED_PIDS; do
    if ! kill -0 "$pid" 2>/dev/null; then
      svc="$(grep -l "^$pid\$" "$RUN_DIR"/*.pid 2>/dev/null | head -n 1)"
      [ -n "$svc" ] && svc="$(basename "$svc" .pid)"
      echo "The ${svc:-process $pid} service stopped unexpectedly (see $RUN_DIR/${svc:-*}.log); stopping the rest."
      cleanup 1
    fi
  done
  sleep 2
done
