#!/usr/bin/env bash
# Advise Workbench: check the environment, then run bridge + backend + frontend together.
#
#   ./scripts/run_agent.sh           prechecks, then start everything (Ctrl+C stops it all)
#   ./scripts/run_agent.sh --check   prechecks only
#   ./scripts/run_agent.sh --fix     prechecks, repairing what is safe to repair, then start
#   ./scripts/run_agent.sh --check --fix   repair, report, and exit
#
# Before the other checks it makes sure Postgres, Redis and RabbitMQ answer (starting local ones with
# scripts/infra.sh) and that the shared-service links in .env (Qdrant, S3, embeddings, ...) are reachable.
#
# Windows: run it from Git Bash, or use scripts\run_agent.cmd (cmd or PowerShell), which finds Git Bash for you.
#
# Works with macOS's stock bash 3.2. Ports can be overridden: BRIDGE_PORT, BACKEND_PORT, FRONTEND_PORT.
# With OPENOBSERVE_ENABLED=true in .env, OpenObserve (monitoring) is started as well: ./scripts/openobserve.sh setup

set -u
# If SHELLOPTS is exported (some Windows setups set SHELLOPTS=igncr), bash would pass our options on to
# every child shell, and `set -u` would then break scripts such as npm's wrapper ("IS_WSL: unbound variable").
export -n SHELLOPTS 2>/dev/null

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
ENV_FILE="$ROOT/.env"
ENV_EXAMPLE="$ROOT/.env.example"
VENV="$ROOT/.venv"
VPY="$VENV/bin/python"
[ -x "$VENV/Scripts/python.exe" ] && VPY="$VENV/Scripts/python.exe"   # Windows layout
BRIDGE="$ROOT/scripts/claude_cli_bridge.py"
RUN_DIR="$ROOT/.run"
BRIDGE_PORT="${BRIDGE_PORT:-8787}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

IS_WIN=0; case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) IS_WIN=1 ;; esac
# Python on Windows otherwise writes the console code page (cp1252) and crashes on non-ASCII log output.
[ "$IS_WIN" = 1 ] && export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
CHECK_ONLY=0
FIX=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --fix) FIX=1 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
  # tr -d '\r': a .env saved by Notepad has Windows line endings, which would end every value with a CR.
  grep -E "^$1=" "$ENV_FILE" | tr -d '\r' | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}
env_append() {
  [ -n "$(tail -c1 "$ENV_FILE" 2>/dev/null)" ] && echo >> "$ENV_FILE"
  printf '%s\n' "$1" >> "$ENV_FILE"
}
# hint NAME -> the install command for this platform
hint() {
  if [ "$IS_WIN" = 1 ]; then
    case "$1" in
      python) echo "winget install --exact Python.Python.3.12   (then reopen the terminal)" ;;
      node) echo "winget install --exact OpenJS.NodeJS.LTS   (then reopen the terminal)" ;;
      git) echo "winget install --exact Git.Git" ;;
      libreoffice) echo "winget install --exact TheDocumentFoundation.LibreOffice" ;;
      tesseract) echo "winget install --exact UB-Mannheim.TesseractOCR   (poppler: scoop install poppler)" ;;
    esac
  elif [ "$(uname -s)" = Darwin ]; then
    case "$1" in
      python) echo "brew install python@3.11" ;; node) echo "brew install node" ;; git) echo "xcode-select --install" ;;
      libreoffice) echo "brew install --cask libreoffice" ;; tesseract) echo "brew install tesseract poppler" ;;
    esac
  else
    case "$1" in
      python) echo "sudo apt install python3.11 python3.11-venv" ;; node) echo "sudo apt install nodejs npm" ;; git) echo "sudo apt install git" ;;
      libreoffice) echo "sudo apt install libreoffice" ;; tesseract) echo "sudo apt install tesseract-ocr poppler-utils" ;;
    esac
  fi
}
# with_timeout SECONDS command... : perl's alarm where available, else coreutils timeout, else no limit
with_timeout() {
  secs="$1"; shift
  if command -v perl >/dev/null 2>&1; then perl -e 'alarm shift; exec @ARGV' "$secs" "$@"
  elif command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"
  else "$@"; fi
}
http_ok() { curl -s -m 3 -o /dev/null "$1" 2>/dev/null; }
port_owner() { # name and pid of whatever listens on TCP port $1
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1 " (pid " $2 ")"}'
  elif [ "$IS_WIN" = 1 ]; then
    wpid="$(netstat -ano 2>/dev/null | tr -d '\r' | awk -v p=":$1" '$1 == "TCP" && $4 == "LISTENING" && substr($2, length($2) - length(p) + 1) == p {print $5; exit}')"
    [ -n "$wpid" ] || return 0
    wname="$(tasklist //FI "PID eq $wpid" //FO CSV //NH 2>/dev/null | tr -d '\r"' | head -n 1 | cut -d, -f1)"
    echo "${wname:-process} (pid $wpid)"
  fi
}

# ------------------------------------------------------------------------------- infrastructure
INFRA_SH="$ROOT/scripts/infra.sh"
INFRA_STARTED=""   # services this run started; stopped again when the script exits
infra_stop_started() {
  for s in $INFRA_STARTED; do bash "$INFRA_SH" stop "$s" >/dev/null 2>&1; done
  INFRA_STARTED=""
}
abort_prechecks() { infra_stop_started; exit "${1:-1}"; }
trap 'infra_stop_started; exit 130' INT TERM HUP
trap 'infra_stop_started; exit 141' PIPE
trap 'infra_stop_started' EXIT   # any other way out of the prechecks

section "Infrastructure (Postgres, Redis, RabbitMQ)"
INFRA_AUTOSTART="$(env_get INFRA_AUTOSTART)"; INFRA_AUTOSTART="${INFRA_AUTOSTART:-true}"
INFRA_SERVICES="$(env_get INFRA_SERVICES)"; INFRA_SERVICES="${INFRA_SERVICES:-postgres redis rabbitmq}"
INFRA_STARTED_NOW=""
if [ ! -f "$INFRA_SH" ]; then
  fail "scripts/infra.sh is missing"
else
  for svc in $INFRA_SERVICES; do
    ep=($(bash "$INFRA_SH" endpoint "$svc" 2>/dev/null)); ihost="${ep[0]:-}"; iport="${ep[1]:-}"; ikind="${ep[2]:-local}"
    if [ -z "$ihost" ]; then fail "$svc: unknown service in INFRA_SERVICES"; continue; fi
    eval "IPORT_$svc=$iport"
    if bash "$INFRA_SH" check "$svc"; then
      pass "$svc already running on $ihost:$iport"
    elif [ "$ikind" = remote ]; then
      fail "$svc: $ihost:$iport does not answer (remote endpoint from .env)" "start it, or fix DATABASE_URL / REDIS_URL / CELERY_BROKER_URL in .env"
    elif [ "$CHECK_ONLY" = 1 ]; then
      warn "$svc is not running on $ihost:$iport" "it is started automatically by ./scripts/run_agent.sh (or: ./scripts/infra.sh start $svc)"
    elif [ "$INFRA_AUTOSTART" != true ]; then
      warn "$svc is not running on $ihost:$iport and INFRA_AUTOSTART is $INFRA_AUTOSTART" "./scripts/infra.sh start $svc"
    else
      printf '  ....  %s is not running: starting it (the first run downloads and installs the programs)\n' "$svc"
      bash "$INFRA_SH" start "$svc" 2>&1 | sed 's/^/        /'
      if [ "${PIPESTATUS[0]}" = 0 ]; then
        INFRA_STARTED="$INFRA_STARTED $svc"; INFRA_STARTED_NOW="$INFRA_STARTED_NOW $svc"
        pass "$svc started on $ihost:$iport (stopped again when this script exits)"
      else
        fail "$svc could not be started on $ihost:$iport" "see .run/infra/$svc.log; or install it yourself, or set INFRA_AUTOSTART=false"
      fi
    fi
  done

  # Point the application at instances this run started (only when the setting is not already chosen).
  wire_env() { # KEY VALUE what
    if [ -n "$(env_get "$1")" ]; then return 0; fi
    if [ "$FIX" = 1 ] && [ -f "$ENV_FILE" ]; then env_append "$1=$2"; fixed "set $1 in .env so the app uses the local $3"
    else warn "local $3 is running but $1 is not set in .env, so the app does not use it" "run with --fix, or add $1=$2"; fi
  }
  for svc in $INFRA_STARTED_NOW; do
    case "$svc" in
      postgres)
        if [ -f "$ROOT/advise_workbench.db" ]; then
          warn "an existing SQLite database (advise_workbench.db) is in use, so DATABASE_URL was not pointed at the new Postgres" "set DATABASE_URL yourself to switch; existing data is not migrated"
        else wire_env DATABASE_URL "postgresql+psycopg://advise_workbench:advise_workbench@127.0.0.1:${IPORT_postgres:-5432}/advise_workbench" "Postgres"; fi ;;
      redis) wire_env REDIS_URL "redis://127.0.0.1:${IPORT_redis:-6379}/0" "Redis" ;;
      rabbitmq) wire_env CELERY_BROKER_URL "amqp://guest:guest@127.0.0.1:${IPORT_rabbitmq:-5672}//" "RabbitMQ" ;;
    esac
  done
fi

section "Shared services (public links in .env)"
# link_state HTTP-code -> up | down. 000 = no connection; 502/504/52x = a dead tunnel or unreachable origin.
link_state() { case "$1" in 000|502|504|52[0-9]) echo down ;; *) echo up ;; esac; }
# Team settings that travel with `git pull`: when .env.example carries an active "team-shared-services" block,
# its managed keys are brought into .env (with --fix) or reported (without). The personal settings (collection prefix,
# telemetry stream and tag) are never touched. Opt out with TEAM_SYNC=false in .env.
example_get() { [ -f "$ENV_EXAMPLE" ] || return 0; grep -E "^$1=" "$ENV_EXAMPLE" | tr -d '\r' | tail -n 1 | cut -d= -f2-; }
TEAM_KEYS="QDRANT_URL QDRANT_API_KEY S3_ENDPOINT_URL S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_BUCKET EMBEDDING_BASE_URL EMBEDDING_API_KEY EMBEDDING_MODEL OPENOBSERVE_ENABLED OPENOBSERVE_URL OPENOBSERVE_ORG OPENOBSERVE_USER OPENOBSERVE_PASSWORD OTEL_EXPORTER_OTLP_ENDPOINT OTEL_EXPORTER_OTLP_HEADERS SSL_CA_FILE OTEL_EXPORTER_OTLP_CERTIFICATE"
if [ "$(env_get TEAM_SYNC)" != false ] && [ -f "$ENV_FILE" ] && grep -q '^# >>> team-shared-services' "$ENV_EXAMPLE" 2>/dev/null; then
  TEAM_DIFF=""
  for k in $TEAM_KEYS; do
    want="$(example_get "$k")"
    [ -n "$want" ] && [ "$want" != "$(env_get "$k")" ] && TEAM_DIFF="$TEAM_DIFF $k"
  done
  if [ -n "$TEAM_DIFF" ]; then
    n=$(echo $TEAM_DIFF | wc -w | tr -d ' ')
    if [ "$FIX" = 1 ]; then
      for k in $TEAM_DIFF; do
        grep -v -E "^$k=" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
        env_append "$k=$(example_get "$k")"
      done
      fixed "updated $n shared-service setting(s) in .env from the team block in .env.example:$TEAM_DIFF"
    else
      warn "$n shared-service setting(s) in .env differ from the team's current values in .env.example:$TEAM_DIFF" "run with --fix to update .env (personal settings are kept; TEAM_SYNC=false opts out)"
    fi
  fi
fi
SHARED_REQUIRED="$(env_get SHARED_SERVICES_REQUIRED)"
SHARED_SEEN=0
check_link() { # label ENV_VAR path need200(1|0)
  url="$(env_get "$2")"
  [ -n "$url" ] || return 0
  case "$2:$url" in OPENOBSERVE_URL:*://localhost*|OPENOBSERVE_URL:*://127.0.0.1*) return 0 ;; esac
  SHARED_SEEN=$((SHARED_SEEN + 1))
  code="$(curl -sk -m 8 -o /dev/null -w '%{http_code}' "${url%/}$3" 2>/dev/null)"
  state="$(link_state "$code")"
  if [ "$state" = up ] && { [ "$4" = 0 ] || [ "$code" = 200 ]; }; then pass "$1 answers (HTTP $code) at ${url%/}"
  else
    hint="check the link and its key in .env"
    case "$url" in *trycloudflare.com*) hint="quick-tunnel links change when the tunnels restart: ask the service owner for the current advise-workbench-team.env" ;; esac
    if [ "$SHARED_REQUIRED" = true ]; then fail "$1 link does not answer (HTTP $code): ${url%/}" "$hint"
    else warn "$1 link does not answer (HTTP $code): ${url%/}" "$hint"; fi
  fi
}
check_link "Qdrant" QDRANT_URL /healthz 1
check_link "S3 (SeaweedFS)" S3_ENDPOINT_URL / 0
check_link "Embeddings" EMBEDDING_BASE_URL /health 1
check_link "OpenObserve" OPENOBSERVE_URL /healthz 1
check_link "OTLP collector" OTEL_EXPORTER_OTLP_ENDPOINT / 0
if [ "$SHARED_SEEN" = 0 ]; then
  warn "no shared-service links in .env (QDRANT_URL, S3_ENDPOINT_URL, EMBEDDING_BASE_URL, OPENOBSERVE_URL, OTEL_EXPORTER_OTLP_ENDPOINT)" \
       "paste advise-workbench-team.env (from the shared-services owner) into .env, see docs/06-deployment-operations/SHARED_SERVICES.md"
fi

# ------------------------------------------------------------------------------- prechecks
section "Tools"
PY=""
for cand in python3.11 python3.12 python3.13 python3 python py; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$(command -v "$cand")"; break
  fi
done
if [ -n "$PY" ]; then pass "Python $("$PY" -c 'import platform; print(platform.python_version())') ($PY)"
else fail "Python 3.11 or newer not found" "$(hint python)"; fi

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
  if [ "$NODE_MAJOR" -ge 18 ]; then pass "Node $(node --version)"; else fail "Node $(node --version) is older than 18" "$(hint node)"; fi
else fail "Node not found" "$(hint node)"; fi
command -v npm >/dev/null 2>&1 && pass "npm $(npm --version)" || fail "npm not found" "$(hint node)"
command -v git >/dev/null 2>&1 && pass "git present" || fail "git not found" "$(hint git)"

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
    REPLY="$(cd "$CLI_WORK" && echo 'Reply with exactly: OK' | with_timeout 90 claude -p --model claude-haiku-4-5 \
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
    "$PY" -m venv "$VENV"
    [ -x "$VENV/Scripts/python.exe" ] && VPY="$VENV/Scripts/python.exe" || VPY="$VENV/bin/python"
    if [ -x "$VPY" ] && "$VPY" -m pip install -q -r "$ROOT/requirements-dev.txt"; then
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
OO_HOSTPART="${OO_URL#*://}"; OO_HOSTPART="${OO_HOSTPART%%[:/]*}"
case "$OO_HOSTPART" in localhost|127.0.0.1|"") OO_REMOTE=0 ;; *) OO_REMOTE=1 ;; esac
if [ "$OO_ENABLED" = "true" ] && [ "$OO_REMOTE" = 1 ]; then
  # A shared OpenObserve (for example a public link): never started locally. Whether it answers is
  # already reported under "Shared services" above.
  OO_UP=1
elif [ "$OO_ENABLED" = "true" ]; then
  S="$(check_port openobserve "$OO_PORT" "$OO_URL/healthz")"
  case "$S" in up) OO_UP=1; pass "OpenObserve already running on $OO_PORT" ;;
    free) if [ -x "$ROOT/.tools/openobserve/openobserve" ]; then pass "port $OO_PORT is free for OpenObserve"
          else fail "OPENOBSERVE_ENABLED=true but OpenObserve is not installed" "./scripts/openobserve.sh setup"; fi ;;
    *) fail "port $OO_PORT is used by ${S#busy:}" "stop that process or change OPENOBSERVE_URL" ;; esac
fi

section "Optional tools"
[ "$OO_ENABLED" = "true" ] || warn "OpenObserve monitoring is off: no traces, metrics or logs are collected" "./scripts/openobserve.sh setup"
if command -v soffice >/dev/null 2>&1 || [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ] \
   || [ -f "/c/Program Files/LibreOffice/program/soffice.exe" ] || [ -f "/c/Program Files (x86)/LibreOffice/program/soffice.exe" ]; then pass "LibreOffice present"
else warn "LibreOffice not installed: visual QA works on a degraded render of decks and documents" "$(hint libreoffice)"; fi
if bash "$INFRA_SH" check redis >/dev/null 2>&1; then pass "Redis is running"
else warn "Redis not running: in-process cache and queue are used (fine for one machine)" "./scripts/infra.sh start redis"; fi
if command -v tesseract >/dev/null 2>&1 || [ -f "/c/Program Files/Tesseract-OCR/tesseract.exe" ]; then pass "Tesseract present"
else warn "Tesseract not installed: scanned PDFs cannot be read" "$(hint tesseract)"; fi

printf '\nPrechecks: %d passed, %d warnings, %d failed\n' "$PASS_N" "$WARN_N" "$FAIL_N"
if [ "$FAIL_N" -gt 0 ]; then
  echo "Fix the FAIL items above and run again (--fix repairs the ones marked 'run with --fix')."
  abort_prechecks 1
fi
[ "$CHECK_ONLY" = 1 ] && exit 0

# --------------------------------------------------------------------------------- start
mkdir -p "$RUN_DIR"
STARTED_PIDS=""
TAIL_PIDS=""

kill_tree() { # stop a process and everything it started
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*)
    # Git Bash cannot see native Windows grandchildren (uvicorn's reloader, node's workers): end the whole tree.
    winpid="$(ps 2>/dev/null | awk -v p="$1" '$1 == p {print $4}')"
    [ -n "$winpid" ] && taskkill //PID "$winpid" //T //F >/dev/null 2>&1 ;;
  esac
  if command -v pgrep >/dev/null 2>&1; then kids="$(pgrep -P "$1" 2>/dev/null)"
  else kids="$(ps -A -o pid=,ppid= 2>/dev/null | awk -v p="$1" '$2 == p {print $1}')"
       [ -n "$kids" ] || kids="$(ps 2>/dev/null | awk -v p="$1" '$2 == p {print $1}')"; fi   # Git Bash: plain ps
  for child in $kids; do kill_tree "$child"; done
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) kill -f "$1" 2>/dev/null ;; *) kill "$1" 2>/dev/null ;; esac
}
cleanup() {
  trap - INT TERM EXIT
  printf '\nStopping...\n'
  exec 2>/dev/null  # hide the shell's "Terminated" notices for the processes stopped below
  for pid in $STARTED_PIDS; do kill_tree "$pid"; done
  for pid in $TAIL_PIDS; do kill "$pid"; done
  command -v pkill >/dev/null 2>&1 && pkill -f "tail -n \+1 -F $RUN_DIR/"
  infra_stop_started
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
  start_service backend "$ROOT" "$VPY" -m uvicorn src.app.main:app --reload --reload-dir src --host 0.0.0.0 --port "$BACKEND_PORT"
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
  if [ -n "$INFRA_STARTED" ]; then
    echo "The application was already running; this script only started:$INFRA_STARTED (left running; stop with ./scripts/infra.sh stop)."
    INFRA_STARTED=""
  else echo "Everything was already running; nothing was started by this script."; fi
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
