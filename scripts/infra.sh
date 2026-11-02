#!/usr/bin/env bash
# Postgres, Redis and RabbitMQ for local development: find a running instance, or start one.
#
#   ./scripts/infra.sh status   [postgres redis rabbitmq]   what answers where
#   ./scripts/infra.sh start    [postgres redis rabbitmq]   start whichever does not answer yet
#   ./scripts/infra.sh stop     [postgres redis rabbitmq]   stop only what this script started
#   ./scripts/infra.sh install  [postgres redis rabbitmq]   fetch the programs, do not start
#   ./scripts/infra.sh endpoint <service>                   print "host port local|remote"
#   ./scripts/infra.sh check    <service>                   exit 0 when something answers there
#
# ./scripts/run_agent.sh calls this before its other checks. Endpoints come from .env
# (DATABASE_URL, REDIS_URL, CELERY_BROKER_URL), else the usual local ports 5432, 6379, 5672.
# An endpoint that already answers is used as it is and never stopped. A local endpoint that
# does not answer is started, in this order:
#   1. Docker, when `docker info` works         (containers aw-infra-<service>, volumes kept)
#   2. native programs                          (PATH, Homebrew, or downloaded into .tools/infra on Windows)
# Data lives in workspace/.infra (git-ignored). The local Postgres listens on 127.0.0.1 only, with
# user/password/database advise_workbench (the same as docker-compose.yml and .env.example).
#
# Settings (environment or .env): INFRA_BACKEND=auto|docker|native, INFRA_POSTGRES_PORT,
# INFRA_REDIS_PORT, INFRA_RABBITMQ_PORT, INFRA_REUSE_DIR (a folder with ready-made pgsql/, redis/,
# rabbitmq/, erlang/ programs, e.g. the shared-services runner's D:\aw-native\bin).

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
TOOLS="$ROOT/.tools/infra"
DATA="${INFRA_DATA_DIR:-$ROOT/workspace/.infra}"
STATE="$ROOT/.run/infra"
SERVICES="postgres redis rabbitmq"

PG_USER=advise_workbench; PG_PASSWORD=advise_workbench; PG_DB=advise_workbench
RMQ_NODE=aw_infra@localhost
PG_VERSION_DL="16.9-1"; REDIS_VERSION_DL="7.4.2"; RMQ_VERSION_DL="3.13.7"; ERLANG_VERSION_DL="26.2.5"

WIN=0; MAC=0
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) WIN=1 ;; Darwin) MAC=1 ;; esac

say() { printf '%s\n' "$*"; }
err() { printf '%s\n' "$*" >&2; }

env_get() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tr -d '\r' | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}
cfg() { # environment variable wins over .env
  eval "v=\${$1:-}"
  if [ -n "$v" ]; then printf '%s' "$v"; else env_get "$1"; fi
}
native_path() { if [ "$WIN" = 1 ]; then cygpath -w "$1"; else printf '%s' "$1"; fi }

# ------------------------------------------------------------------------------ endpoints
hostport_of() { # url default_host default_port -> "host port"
  u="$1"; rest="${u#*://}"; [ "$rest" = "$u" ] && rest="$u"
  rest="${rest%%/*}"; rest="${rest%%\?*}"; hp="${rest##*@}"
  host="${hp%%:*}"; port=""
  case "$hp" in *:*) port="${hp##*:}" ;; esac
  case "$port" in ''|*[!0-9]*) port="$3" ;; esac
  printf '%s %s' "${host:-$2}" "$port"
}
is_local() { case "$1" in localhost|127.*|::1|0.0.0.0|"") return 0 ;; *) return 1 ;; esac }

endpoint() { # service -> "host port"
  case "$1" in
    postgres) url="$(cfg DATABASE_URL)"; case "$url" in postgres*) ;; *) url="" ;; esac
              def="$(cfg INFRA_POSTGRES_PORT)"; hostport_of "$url" 127.0.0.1 "${def:-5432}" ;;
    redis)    url="$(cfg REDIS_URL)"; case "$url" in redis*) ;; *) url="" ;; esac
              def="$(cfg INFRA_REDIS_PORT)"; hostport_of "$url" 127.0.0.1 "${def:-6379}" ;;
    rabbitmq) url="$(cfg CELERY_BROKER_URL)"; case "$url" in amqp*) ;; *) url="" ;; esac
              def="$(cfg INFRA_RABBITMQ_PORT)"; hostport_of "$url" 127.0.0.1 "${def:-5672}" ;;
    *) err "unknown service: $1"; return 2 ;;
  esac
}

tcp_open() { # host port
  h="$1"; [ "$h" = localhost ] && h=127.0.0.1
  if command -v nc >/dev/null 2>&1; then nc -z -w 2 "$h" "$2" >/dev/null 2>&1
  elif command -v timeout >/dev/null 2>&1; then timeout 3 bash -c "exec 3<>/dev/tcp/$h/$2" >/dev/null 2>&1
  else perl -e 'use Socket; alarm 3; socket(S,PF_INET,SOCK_STREAM,0) or exit 1; exit(connect(S,sockaddr_in($ARGV[1],inet_aton($ARGV[0])))?0:1)' "$h" "$2" >/dev/null 2>&1
  fi
}
wait_port() { # host port seconds
  started=$SECONDS
  while [ $((SECONDS - started)) -lt "$3" ]; do tcp_open "$1" "$2" && return 0; sleep 1; done
  return 1
}

# ------------------------------------------------------------------------ program lookup
reuse_dirs() { # folders that may hold ready-made programs
  [ -n "$(cfg INFRA_REUSE_DIR)" ] && echo "$(cfg INFRA_REUSE_DIR)"
  [ -n "${AW_NATIVE_ROOT:-}" ] && echo "$AW_NATIVE_ROOT/bin"
  if [ "$WIN" = 1 ]; then cygpath -u 'D:\aw-native\bin' 2>/dev/null; fi
}
exe_in() { # dir name -> path of an executable, with or without .exe
  for f in "$1/$2.exe" "$1/$2" "$1/$2.bat"; do [ -f "$f" ] && { echo "$f"; return 0; }; done
  return 1
}
first_file() { # name pattern under dirs... -> first match
  pat="$1"; shift
  for d in "$@"; do
    [ -d "$d" ] || continue
    m="$(find "$d" -maxdepth 5 -iname "$pat" -type f 2>/dev/null | head -n 1)"
    [ -n "$m" ] && { echo "$m"; return 0; }
  done
  return 1
}
find_pg_bin() { # -> directory containing pg_ctl
  for d in "$TOOLS/pgsql/pgsql/bin" $(reuse_dirs | sed 's#$#/pgsql/pgsql/bin#') \
           /opt/homebrew/opt/postgresql@16/bin /usr/local/opt/postgresql@16/bin /opt/homebrew/opt/postgresql@17/bin \
           /usr/lib/postgresql/16/bin /usr/lib/postgresql/15/bin /usr/lib/postgresql/17/bin; do
    exe_in "$d" pg_ctl >/dev/null && { echo "$d"; return 0; }
  done
  p="$(command -v pg_ctl 2>/dev/null)" && { dirname "$p"; return 0; }
  return 1
}
find_redis() {
  first_file 'redis-server.exe' "$TOOLS/redis" $(reuse_dirs | sed 's#$#/redis#') && return 0
  first_file 'redis-server' /opt/homebrew/bin /usr/local/bin /usr/bin && return 0
  command -v redis-server 2>/dev/null
}
find_rabbit() { # -> sbin directory
  for pat in 'rabbitmq-server.bat' 'rabbitmq-server'; do
    m="$(first_file "$pat" "$TOOLS/rabbitmq" $(reuse_dirs | sed 's#$#/rabbitmq#') /opt/homebrew/opt/rabbitmq/sbin /usr/local/opt/rabbitmq/sbin /usr/lib/rabbitmq/bin /usr/sbin)" && { dirname "$m"; return 0; }
  done
  p="$(command -v rabbitmq-server 2>/dev/null)" && { dirname "$p"; return 0; }
  return 1
}
find_erlang_home() { # Windows only: folder that holds bin/erl.exe
  for d in "$TOOLS/erlang" $(reuse_dirs | sed 's#$#/erlang#'); do
    [ -f "$d/bin/erl.exe" ] && { echo "$d"; return 0; }
  done
  return 1
}

# -------------------------------------------------------------------------------- install
download() { # url file
  [ -s "$2" ] && return 0
  mkdir -p "$(dirname "$2")"
  say "  downloading $(basename "$2")"
  curl -fL --progress-bar -o "$2.part" "$1" && mv "$2.part" "$2"
}
install_service() {
  case "$1" in
    postgres)
      find_pg_bin >/dev/null && return 0
      if [ "$WIN" = 1 ]; then
        f="$TOOLS/downloads/postgresql-$PG_VERSION_DL-windows-x64-binaries.zip"
        download "https://get.enterprisedb.com/postgresql/postgresql-$PG_VERSION_DL-windows-x64-binaries.zip" "$f" || return 1
        mkdir -p "$TOOLS/pgsql" && unzip -q -o "$f" -d "$TOOLS/pgsql"
      elif [ "$MAC" = 1 ] && command -v brew >/dev/null 2>&1; then brew install postgresql@16
      else err "  install PostgreSQL 16 (apt install postgresql-16) or start Docker"; return 1; fi
      find_pg_bin >/dev/null ;;
    redis)
      find_redis >/dev/null && return 0
      if [ "$WIN" = 1 ]; then
        f="$TOOLS/downloads/Redis-$REDIS_VERSION_DL-Windows-x64-msys2.zip"
        download "https://github.com/redis-windows/redis-windows/releases/download/$REDIS_VERSION_DL/Redis-$REDIS_VERSION_DL-Windows-x64-msys2.zip" "$f" || return 1
        mkdir -p "$TOOLS/redis" && unzip -q -o "$f" -d "$TOOLS/redis"
      elif [ "$MAC" = 1 ] && command -v brew >/dev/null 2>&1; then brew install redis
      else err "  install Redis (apt install redis-server) or start Docker"; return 1; fi
      find_redis >/dev/null ;;
    rabbitmq)
      if [ "$WIN" = 1 ]; then
        if ! find_erlang_home >/dev/null; then
          f="$TOOLS/downloads/otp_win64_$ERLANG_VERSION_DL.exe"
          download "https://github.com/erlang/otp/releases/download/OTP-$ERLANG_VERSION_DL/otp_win64_$ERLANG_VERSION_DL.exe" "$f" || return 1
          say "  installing Erlang/OTP $ERLANG_VERSION_DL (needed by RabbitMQ)"
          mkdir -p "$TOOLS/erlang"
          # MSYS2_ARG_CONV_EXCL stops Git Bash from rewriting /S and /D= as paths.
          MSYS2_ARG_CONV_EXCL='*' "$f" /S "/D=$(native_path "$TOOLS/erlang")"
          find_erlang_home >/dev/null || { err "  Erlang did not install; run $f /S /D=<folder> from an elevated shell"; return 1; }
        fi
        if ! find_rabbit >/dev/null; then
          f="$TOOLS/downloads/rabbitmq-server-windows-$RMQ_VERSION_DL.zip"
          download "https://github.com/rabbitmq/rabbitmq-server/releases/download/v$RMQ_VERSION_DL/rabbitmq-server-windows-$RMQ_VERSION_DL.zip" "$f" || return 1
          mkdir -p "$TOOLS/rabbitmq" && unzip -q -o "$f" -d "$TOOLS/rabbitmq"
        fi
      else
        find_rabbit >/dev/null && return 0
        if [ "$MAC" = 1 ] && command -v brew >/dev/null 2>&1; then brew install rabbitmq
        else err "  install RabbitMQ (apt install rabbitmq-server) or start Docker"; return 1; fi
      fi
      find_rabbit >/dev/null ;;
  esac
}

# --------------------------------------------------------------------------------- backend
docker_ok() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }
backend() {
  case "$(cfg INFRA_BACKEND)" in
    docker) echo docker ;;
    native) echo native ;;
    *) if docker_ok; then echo docker; else echo native; fi ;;
  esac
}

mark_started() { mkdir -p "$STATE"; printf '%s\n' "$2" > "$STATE/$1.started"; }
marker() { [ -f "$STATE/$1.started" ] && cat "$STATE/$1.started"; }

# -------------------------------------------------------------------------------- docker
docker_start() { # service port
  name="aw-infra-$1"
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then docker start "$name" >/dev/null || return 1
  else
    case "$1" in
      postgres) docker run -d --name "$name" -p "127.0.0.1:$2:5432" -e POSTGRES_USER=$PG_USER -e POSTGRES_PASSWORD=$PG_PASSWORD \
                  -e POSTGRES_DB=$PG_DB -v "$name:/var/lib/postgresql/data" postgres:16 >/dev/null ;;
      redis)    docker run -d --name "$name" -p "127.0.0.1:$2:6379" -v "$name:/data" redis:7 redis-server --appendonly yes >/dev/null ;;
      rabbitmq) docker run -d --name "$name" -p "127.0.0.1:$2:5672" -v "$name:/var/lib/rabbitmq" rabbitmq:3.13-alpine >/dev/null ;;
    esac || return 1
  fi
  mark_started "$1" "docker $name"
}

# --------------------------------------------------------------------------------- native
pg_start() { # port
  bin="$(find_pg_bin)" || return 1
  dir="$DATA/postgres"; mkdir -p "$DATA" "$STATE"
  pgctl="$(exe_in "$bin" pg_ctl)"; initdb="$(exe_in "$bin" initdb)"; psql="$(exe_in "$bin" psql)"
  if [ ! -f "$dir/PG_VERSION" ]; then
    say "  initialising Postgres data in $dir"
    pw="$STATE/pgpw.tmp"; printf '%s' "$PG_PASSWORD" > "$pw"
    "$initdb" -D "$(native_path "$dir")" -U "$PG_USER" -A scram-sha-256 "--pwfile=$(native_path "$pw")" -E UTF8 --locale=C >"$STATE/postgres-init.log" 2>&1
    rc=$?; rm -f "$pw"
    [ $rc -eq 0 ] || { err "  initdb failed; see $STATE/postgres-init.log"; return 1; }
    {
      printf "\n# --- advise-workbench local instance ---\nlisten_addresses = '127.0.0.1'\nport = %s\nmax_connections = 100\n" "$1"
    } >> "$dir/postgresql.conf"
    printf 'host all all 127.0.0.1/32 scram-sha-256\nhost all all ::1/128 scram-sha-256\n' > "$dir/pg_hba.conf"
  fi
  "$pgctl" start -w -t 90 -D "$(native_path "$dir")" -l "$(native_path "$STATE/postgres.log")" -o "-p $1" >/dev/null 2>&1 \
    || { err "  pg_ctl could not start Postgres; see $STATE/postgres.log"; return 1; }
  # create the application database once
  exists="$(PGPASSWORD=$PG_PASSWORD "$psql" -h 127.0.0.1 -p "$1" -U "$PG_USER" -d postgres -Atc "select 1 from pg_database where datname='$PG_DB'" 2>/dev/null)"
  if [ "$exists" != 1 ]; then
    PGPASSWORD=$PG_PASSWORD "$psql" -h 127.0.0.1 -p "$1" -U "$PG_USER" -d postgres -qc "create database $PG_DB" >/dev/null 2>&1 \
      || { err "  could not create database $PG_DB"; return 1; }
  fi
  mark_started postgres "native postgres"
}
pg_stop() {
  bin="$(find_pg_bin)" || return 0
  "$(exe_in "$bin" pg_ctl)" stop -m fast -D "$(native_path "$DATA/postgres")" >/dev/null 2>&1
}

redis_start() { # port
  rs="$(find_redis)" || return 1
  dir="$DATA/redis"; mkdir -p "$dir" "$STATE"
  # exec: the recorded pid must be Redis itself, not a wrapper shell
  ( cd "$dir" && exec nohup "$rs" --port "$1" --bind 127.0.0.1 --appendonly yes --dir ./ > "$STATE/redis.log" 2>&1 ) &
  echo $! > "$STATE/redis.pid"
  mark_started redis "native $(cat "$STATE/redis.pid")"
}
kill_tree() { # a process and everything it started
  if [ "$WIN" = 1 ]; then kids="$(ps 2>/dev/null | awk -v p="$1" '$2 == p {print $1}')"
  else kids="$(ps -A -o pid=,ppid= 2>/dev/null | awk -v p="$1" '$2 == p {print $1}')"; fi
  for c in $kids; do kill_tree "$c"; done
  # Git Bash: a plain kill is ignored by native Windows programs; -f ends them.
  if [ "$WIN" = 1 ]; then kill -f "$1" 2>/dev/null; else kill "$1" 2>/dev/null; fi
}
stop_pid() { # pidfile
  [ -f "$1" ] || return 0
  pid="$(cat "$1")"; kill_tree "$pid"; sleep 1; kill -9 "$pid" 2>/dev/null; rm -f "$1"
}
redis_stop() {
  # Ask Redis to flush and exit; only force-kill if it does not.
  if rs="$(find_redis)" && cli="$(exe_in "$(dirname "$rs")" redis-cli)"; then
    "$cli" -h 127.0.0.1 -p "$(endpoint redis | cut -d' ' -f2)" shutdown >/dev/null 2>&1
    sleep 1
  fi
  stop_pid "$STATE/redis.pid"
}

rabbit_env() { # exports the environment RabbitMQ's scripts read; $1 = port
  export RABBITMQ_NODENAME="$RMQ_NODE" RABBITMQ_NODE_IP_ADDRESS=127.0.0.1 RABBITMQ_NODE_PORT="$1"
  export RABBITMQ_DIST_PORT=$(( $1 + 20001 ))
  if [ "$WIN" = 1 ]; then
    export RABBITMQ_BASE="$(native_path "$DATA/rabbitmq")" ERLANG_HOME="$(native_path "$(find_erlang_home)")"
  else
    export RABBITMQ_MNESIA_BASE="$DATA/rabbitmq/mnesia" RABBITMQ_LOG_BASE="$DATA/rabbitmq/log"
  fi
}
rabbit_start() { # port
  sbin="$(find_rabbit)" || return 1
  if [ "$WIN" = 1 ]; then find_erlang_home >/dev/null || { err "  Erlang is missing"; return 1; }; fi
  mkdir -p "$DATA/rabbitmq" "$STATE"
  rabbit_env "$1"
  if [ "$WIN" = 1 ]; then
    nohup cmd.exe //c "$(native_path "$(exe_in "$sbin" rabbitmq-server)")" > "$STATE/rabbitmq.log" 2>&1 &
  else
    nohup "$sbin/rabbitmq-server" > "$STATE/rabbitmq.log" 2>&1 &
  fi
  echo $! > "$STATE/rabbitmq.pid"
  mark_started rabbitmq "native $(cat "$STATE/rabbitmq.pid")"
}
rabbit_stop() {
  sbin="$(find_rabbit)" || return 0
  rabbit_env "$(endpoint rabbitmq | cut -d' ' -f2)"
  if [ "$WIN" = 1 ]; then cmd.exe //c "$(native_path "$(exe_in "$sbin" rabbitmqctl)")" -n "$RMQ_NODE" stop >/dev/null 2>&1
  else "$sbin/rabbitmqctl" -n "$RMQ_NODE" stop >/dev/null 2>&1; fi
  stop_pid "$STATE/rabbitmq.pid"
}

# ---------------------------------------------------------------------------------- verbs
do_start() { # service -> 0 running (found or started), 1 failed, 3 remote and not answering
  svc="$1"; set -- $(endpoint "$svc"); host="$1"; port="$2"
  if tcp_open "$host" "$port"; then say "$svc already answers on $host:$port"; return 0; fi
  if ! is_local "$host"; then err "$svc: $host:$port is a remote endpoint and does not answer"; return 3; fi
  [ "$host" = localhost ] && host=127.0.0.1
  if [ "$(backend)" = docker ]; then
    say "starting $svc in Docker on $host:$port"
    docker_start "$svc" "$port" || { err "$svc: docker could not start the container"; return 1; }
  else
    say "starting $svc natively on $host:$port"
    install_service "$svc" || { err "$svc: program not available"; return 1; }
    case "$svc" in
      postgres) pg_start "$port" ;;
      redis)    redis_start "$port" ;;
      rabbitmq) rabbit_start "$port" ;;
    esac || return 1
  fi
  wait=60; [ "$svc" = rabbitmq ] && wait=240
  if wait_port "$host" "$port" "$wait"; then say "$svc is up on $host:$port"; return 0; fi
  err "$svc did not open $host:$port within ${wait}s; see $STATE/$svc.log"; return 1
}

do_stop() {
  svc="$1"; m="$(marker "$svc")"
  [ -n "$m" ] || { say "$svc: not started by this script; left alone"; return 0; }
  case "$m" in
    docker*) docker stop "${m#docker }" >/dev/null 2>&1 ;;
    *) case "$svc" in postgres) pg_stop ;; redis) redis_stop ;; rabbitmq) rabbit_stop ;; esac ;;
  esac
  rm -f "$STATE/$svc.started"
  say "$svc stopped"
}

do_status() {
  svc="$1"; set -- $(endpoint "$svc"); host="$1"; port="$2"
  if tcp_open "$host" "$port"; then
    if [ -n "$(marker "$svc")" ]; then say "$svc: running on $host:$port (started by infra.sh)"
    else say "$svc: running on $host:$port (external instance)"; fi
  else say "$svc: not running ($host:$port)"; fi
}

cmd="${1:-}"; [ $# -gt 0 ] && shift
case "$cmd" in
  check)    [ $# -eq 1 ] || { err "usage: infra.sh check <service>"; exit 2; }
            ep="$(endpoint "$1")" || exit 2; set -- $ep; tcp_open "$1" "$2"; exit $? ;;
  endpoint) [ $# -eq 1 ] || { err "usage: infra.sh endpoint <service>"; exit 2; }
            ep="$(endpoint "$1")" || exit 2; set -- $1 $ep
            if is_local "$2"; then echo "$2 $3 local"; else echo "$2 $3 remote"; fi ;;
  status|start|stop|install)
    list="${*:-$SERVICES}"; rc=0
    for s in $list; do
      case "$s" in postgres|redis|rabbitmq) ;; *) err "unknown service: $s"; exit 2 ;; esac
    done
    for s in $list; do
      case "$cmd" in
        status) do_status "$s" ;;
        start) do_start "$s" || rc=$? ;;
        stop) do_stop "$s" ;;
        install) say "$s:"; install_service "$s" && say "  ready" || rc=1 ;;
      esac
    done
    exit $rc ;;
  *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
