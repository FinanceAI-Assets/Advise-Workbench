#!/usr/bin/env bash
# OpenObserve for local monitoring: one binary, data under workspace/.openobserve.
#
#   ./scripts/openobserve.sh install   download the binary into .tools/openobserve (about 120 MB)
#   ./scripts/openobserve.sh setup     install if needed, then write the OPENOBSERVE_* settings into .env
#   ./scripts/openobserve.sh start     run in the foreground (Ctrl+C stops it)
#   ./scripts/openobserve.sh status    say whether it answers
#
# ./scripts/run_agent.sh starts it with the other services when OPENOBSERVE_ENABLED=true is in .env.

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
VERSION="${OPENOBSERVE_VERSION:-v1.0.4}"
BIN_DIR="$ROOT/.tools/openobserve"
BIN="$BIN_DIR/openobserve"
DATA_DIR="$ROOT/workspace/.openobserve"

env_get() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}
env_set_if_missing() {
  [ -n "$(env_get "$1")" ] && return 0
  [ -n "$(tail -c1 "$ENV_FILE" 2>/dev/null)" ] && echo >> "$ENV_FILE"
  printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
}
url() { u="$(env_get OPENOBSERVE_URL)"; echo "${u:-http://localhost:5080}"; }

install() {
  [ -x "$BIN" ] && { echo "OpenObserve already installed: $("$BIN" --version)"; return 0; }
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) PLATFORM=darwin-arm64 ;;
    Darwin-x86_64) PLATFORM=darwin-amd64 ;;
    Linux-x86_64) PLATFORM=linux-amd64 ;;
    Linux-aarch64) PLATFORM=linux-arm64 ;;
    *) echo "No OpenObserve build known for $(uname -s) $(uname -m)"; exit 1 ;;
  esac
  mkdir -p "$BIN_DIR"
  echo "Downloading OpenObserve $VERSION ($PLATFORM)..."
  curl -fL --progress-bar -o "$BIN_DIR/openobserve.tar.gz" \
    "https://downloads.openobserve.ai/releases/openobserve/$VERSION/openobserve-$VERSION-$PLATFORM.tar.gz"
  tar -xzf "$BIN_DIR/openobserve.tar.gz" -C "$BIN_DIR"
  rm "$BIN_DIR/openobserve.tar.gz"
  echo "Installed: $("$BIN" --version)"
}

setup() {
  install
  [ -f "$ENV_FILE" ] || { echo ".env is missing; run ./scripts/run_agent.sh --fix first"; exit 1; }
  env_set_if_missing OPENOBSERVE_ENABLED true
  env_set_if_missing OPENOBSERVE_URL http://localhost:5080
  env_set_if_missing OPENOBSERVE_USER admin@advise-workbench.local
  # OpenObserve requires a lowercase letter, an uppercase letter, a digit and a special character.
  env_set_if_missing OPENOBSERVE_PASSWORD "$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 20)!aA1"
  echo "OpenObserve settings are in .env. Sign in at $(url) as $(env_get OPENOBSERVE_USER); the password is OPENOBSERVE_PASSWORD in .env."
}

start() {
  [ -x "$BIN" ] || { echo "OpenObserve is not installed; run ./scripts/openobserve.sh setup"; exit 1; }
  USER_EMAIL="$(env_get OPENOBSERVE_USER)"; PASSWORD="$(env_get OPENOBSERVE_PASSWORD)"
  [ -n "$USER_EMAIL" ] && [ -n "$PASSWORD" ] || { echo "OPENOBSERVE_USER / OPENOBSERVE_PASSWORD are not in .env; run ./scripts/openobserve.sh setup"; exit 1; }
  PORT="$(url | sed -E 's#.*:([0-9]+)/?$#\1#')"
  mkdir -p "$DATA_DIR"
  # The sign-in is created from these two values the first time OpenObserve starts on an empty data folder.
  ZO_ROOT_USER_EMAIL="$USER_EMAIL" ZO_ROOT_USER_PASSWORD="$PASSWORD" ZO_DATA_DIR="$DATA_DIR/" \
    ZO_HTTP_PORT="$PORT" ZO_TELEMETRY=false exec "$BIN"
}

status() {
  if curl -s -m 3 -o /dev/null "$(url)/healthz"; then echo "OpenObserve is up at $(url)"; else echo "OpenObserve is not answering at $(url)"; exit 1; fi
}

case "${1:-}" in
  install) install ;;
  setup) setup ;;
  start) start ;;
  status) status ;;
  *) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
