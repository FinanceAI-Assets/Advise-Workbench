#!/usr/bin/env python3
"""Connectivity and smoke test for the shared services, from any machine.

    python scripts/check_shared_services.py --env .env --ca system --only qdrant,s3,embeddings,telemetry
    python check_services.py --env .env            # a repo-root .env that holds the block
    python check_services.py --env x.env --ca ca.crt --worker --only qdrant,s3

Only the standard library is required. Deeper checks switch on when the optional
package is importable: psycopg (SQL round-trip), boto3 (object put/get/multipart/
presign), amqp (publish -> consume -> dead-letter), celery (task round-trip with
--worker). Exit status is 1 when any check FAILs; WARN and SKIP do not fail.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import ssl
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"
results: list[tuple[str, str, str, str]] = []  # (service, check, status, detail)


def record(service: str, check: str, status: str, detail: str = "") -> None:
    results.append((service, check, status, detail))
    print(f"  [{status}] {service}: {check}" + (f" - {detail}" if detail else ""), flush=True)


def guard(service: str, check: str):
    """Decorator-free helper: run fn, record PASS with its return text or FAIL with the error."""
    def run(fn):
        try:
            out = fn()
            record(service, check, PASS, out if isinstance(out, str) else "")
        except Exception as exc:  # noqa: BLE001 - a diagnostic tool reports everything
            record(service, check, FAIL, f"{type(exc).__name__}: {exc}")
    return run


# ---- config ---------------------------------------------------------------------------------
def load_env(path: str | None) -> dict[str, str]:
    env = dict(os.environ)
    if path:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def tls_context(ca: str) -> ssl.SSLContext:
    # "system" = trust the normal public CAs (links served through a public tunnel).
    return ssl.create_default_context() if ca == "system" else ssl.create_default_context(cafile=ca)


# ---- http helper -------------------------------------------------------------------------------
def http(method: str, url: str, ctx: ssl.SSLContext, headers: dict | None = None,
         body: bytes | dict | None = None, timeout: float = 20) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    hdrs = dict(headers or {})
    if isinstance(body, dict):
        hdrs.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


# ---- postgres -----------------------------------------------------------------------------------
def check_postgres(env, ctx, ca):
    url = env.get("DATABASE_URL")
    if not url:
        return record("postgres", "config", SKIP, "DATABASE_URL not set")
    u = urllib.parse.urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    host, port = u.hostname, u.port or 5432

    @guard("postgres", "TLS is mandatory (SSLRequest accepted)")
    def _():
        with socket.create_connection((host, port), timeout=10) as s:
            s.sendall(struct.pack("!II", 8, 80877103))
            if s.recv(1) != b"S":
                raise RuntimeError("server refused TLS")
            with ctx.wrap_socket(s, server_hostname=host) as t:
                return t.version()

    try:
        import psycopg
    except ImportError:
        return record("postgres", "SQL round-trip", SKIP, "psycopg not installed")

    @guard("postgres", "login + SELECT over verify-full")
    def _():
        with psycopg.connect(host=host, port=port, user=u.username, password=urllib.parse.unquote(u.password or ""),
                             dbname=u.path.lstrip("/"), sslmode="verify-full", sslrootcert=ca, connect_timeout=10) as c:
            ver = c.execute("select current_setting('server_version')").fetchone()[0]
            c.execute("create temp table aw_check(i int)")
            c.execute("insert into aw_check values (1)")
            if c.execute("select count(*) from aw_check").fetchone()[0] != 1:
                raise RuntimeError("temp table round-trip failed")
            return f"postgres {ver}"


# ---- redis ----------------------------------------------------------------------------------------
def _resp(*args) -> bytes:
    out = f"*{len(args)}\r\n".encode()
    for a in args:
        b = str(a).encode()
        out += f"${len(b)}\r\n".encode() + b + b"\r\n"
    return out


def _reply(f):
    line = f.readline()
    kind, rest = line[:1], line[1:-2]
    if kind == b"-":
        raise RuntimeError(rest.decode())
    if kind == b"$":
        n = int(rest)
        return None if n < 0 else f.read(n + 2)[:-2]
    return rest


def check_redis(env, ctx, ca):
    url = env.get("REDIS_URL")
    if not url:
        return record("redis", "config", SKIP, "REDIS_URL not set")
    u = urllib.parse.urlparse(url)

    @guard("redis", "TLS + AUTH + SET/GET/DEL in tenant DB")
    def _():
        with socket.create_connection((u.hostname, u.port or 6380), timeout=10) as raw, \
                ctx.wrap_socket(raw, server_hostname=u.hostname) as s:
            f = s.makefile("rb")
            key = f"aw:check:{uuid.uuid4().hex[:8]}"
            s.sendall(_resp("AUTH", urllib.parse.unquote(u.password or ""))); _reply(f)
            s.sendall(_resp("SELECT", (u.path or "/0").lstrip("/") or "0")); _reply(f)
            s.sendall(_resp("SET", key, "ok", "EX", 30)); _reply(f)
            s.sendall(_resp("GET", key))
            if _reply(f) != b"ok":
                raise RuntimeError("GET returned unexpected value")
            s.sendall(_resp("DEL", key)); _reply(f)
            return f"db {(u.path or '/0').lstrip('/') or '0'}"

    @guard("redis", "unauthenticated access is rejected")
    def _():
        with socket.create_connection((u.hostname, u.port or 6380), timeout=10) as raw, \
                ctx.wrap_socket(raw, server_hostname=u.hostname) as s:
            s.sendall(_resp("PING"))
            reply = s.makefile("rb").readline()
            if not reply.startswith(b"-"):
                raise RuntimeError(f"PING without AUTH was accepted: {reply!r}")


# ---- rabbitmq ----------------------------------------------------------------------------------------
def check_rabbitmq(env, ctx, ca):
    url = env.get("CELERY_BROKER_URL")
    if not url:
        return record("rabbitmq", "config", SKIP, "CELERY_BROKER_URL not set")
    u = urllib.parse.urlparse(url)
    host, port = u.hostname, u.port or 5671
    vhost = urllib.parse.unquote(u.path.lstrip("/")) or "/"

    @guard("rabbitmq", "AMQPS handshake")
    def _():
        with socket.create_connection((host, port), timeout=10) as raw, ctx.wrap_socket(raw, server_hostname=host) as s:
            s.sendall(b"AMQP\x00\x00\x09\x01")
            if s.recv(1) != b"\x01":  # frame type 1 = method frame (Connection.Start)
                raise RuntimeError("no Connection.Start from broker")
            return s.version()

    try:
        import amqp
    except ImportError:
        return record("rabbitmq", "publish/consume/dead-letter", SKIP, "amqp package not installed")

    @guard("rabbitmq", "publish -> consume -> reject -> dead-letter")
    def _():
        conn = amqp.Connection(host=f"{host}:{port}", userid=urllib.parse.unquote(u.username or ""),
                               password=urllib.parse.unquote(u.password or ""), virtual_host=vhost,
                               ssl={"ca_certs": ca, "cert_reqs": ssl.CERT_REQUIRED}, connect_timeout=10)
        conn.connect()
        ch = conn.channel()
        src = f"aw.check.{uuid.uuid4().hex[:8]}"
        try:
            ch.queue_declare(src, durable=True, auto_delete=False, arguments={
                "x-queue-type": "quorum", "x-dead-letter-exchange": "dlx", "x-dead-letter-routing-key": "ingest.dead"})
            ch.basic_publish(amqp.Message(b"hello", delivery_mode=2), exchange="", routing_key=src)
            msg = None
            for _ in range(20):
                msg = ch.basic_get(src)
                if msg:
                    break
                time.sleep(0.25)
            if not msg or msg.body != b"hello":
                raise RuntimeError("message not consumed")
            ch.basic_reject(msg.delivery_tag, requeue=False)
            dead = None
            for _ in range(40):
                dead = ch.basic_get("ingest.dead")
                if dead and dead.body == b"hello":
                    ch.basic_ack(dead.delivery_tag)
                    return "dead-lettered to ingest.dead"
                if dead:
                    ch.basic_ack(dead.delivery_tag)
                time.sleep(0.25)
            raise RuntimeError("rejected message never reached ingest.dead (is the tenant provisioned?)")
        finally:
            try:
                ch.queue_delete(src)
            finally:
                conn.close()


# ---- s3 / seaweedfs ------------------------------------------------------------------------------------
def check_s3(env, ctx, ca):
    endpoint = env.get("S3_ENDPOINT_URL")
    if not endpoint:
        return record("s3", "config", SKIP, "S3_ENDPOINT_URL not set")

    @guard("s3", "anonymous request is rejected")
    def _():
        code, _ = http("GET", f"{endpoint}/{env.get('S3_BUCKET', 'x')}/", ctx)
        if code not in (401, 403):
            raise RuntimeError(f"anonymous GET returned HTTP {code}; S3 auth is not enforced")
        return f"HTTP {code}"

    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        return record("s3", "object put/get/multipart/presign", SKIP, "boto3 not installed")

    # boto3 >= 1.36 adds trailing CRC checksums (aws-chunked) to every upload by default. SeaweedFS
    # 3.80 stores that framing as object data, corrupting it, so only send checksums when required.
    cfg = dict(s3={"addressing_style": "path"}, signature_version="s3v4", retries={"max_attempts": 2})
    try:
        config = Config(**cfg, request_checksum_calculation="when_required", response_checksum_validation="when_required")
    except TypeError:  # older botocore has no such options and does not add the checksum
        config = Config(**cfg)
    s3 = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=env["S3_ACCESS_KEY_ID"],
                      aws_secret_access_key=env["S3_SECRET_ACCESS_KEY"], region_name="us-east-1", verify=(True if ca == "system" else ca), config=config)
    bucket, key = env["S3_BUCKET"], f"aw-check/{uuid.uuid4().hex[:8]}.txt"

    @guard("s3", "put / get / list / delete")
    def _():
        s3.put_object(Bucket=bucket, Key=key, Body=b"hello")
        if s3.get_object(Bucket=bucket, Key=key)["Body"].read() != b"hello":
            raise RuntimeError("content mismatch")
        if key not in [o["Key"] for o in s3.list_objects_v2(Bucket=bucket, Prefix="aw-check/").get("Contents", [])]:
            raise RuntimeError("object missing from listing")

    @guard("s3", "presigned GET URL")
    def _():
        url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=60)
        code, body = http("GET", url, ctx)
        if code != 200 or body != b"hello":
            raise RuntimeError(f"presigned GET returned HTTP {code}")

    @guard("s3", "multipart upload (5 MiB + tail)")
    def _():
        mkey = f"aw-check/mp-{uuid.uuid4().hex[:8]}.bin"
        up = s3.create_multipart_upload(Bucket=bucket, Key=mkey)
        parts = []
        for n, data in enumerate((b"a" * (5 * 1024 * 1024), b"b" * 1024), start=1):
            etag = s3.upload_part(Bucket=bucket, Key=mkey, UploadId=up["UploadId"], PartNumber=n, Body=data)["ETag"]
            parts.append({"ETag": etag, "PartNumber": n})
        s3.complete_multipart_upload(Bucket=bucket, Key=mkey, UploadId=up["UploadId"], MultipartUpload={"Parts": parts})
        size = s3.head_object(Bucket=bucket, Key=mkey)["ContentLength"]
        s3.delete_object(Bucket=bucket, Key=mkey)
        if size != 5 * 1024 * 1024 + 1024:
            raise RuntimeError(f"unexpected size {size}")

    @guard("s3", "key cannot reach another tenant's bucket")
    def _():
        try:
            s3.list_objects_v2(Bucket="aw-isolation-probe")
        except Exception:  # noqa: BLE001 - any error means access was denied
            return
        raise RuntimeError("listing a foreign bucket succeeded")

    try:
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception:  # noqa: BLE001
        pass


# ---- qdrant ---------------------------------------------------------------------------------------------
def check_qdrant(env, ctx, ca):
    base, api_key = env.get("QDRANT_URL"), env.get("QDRANT_API_KEY")
    if not base:
        return record("qdrant", "config", SKIP, "QDRANT_URL not set")
    hdr = {"api-key": api_key or ""}
    # One fixed collection, reused by every run and never dropped: removing a collection on a Windows Qdrant fails
    # with "Access is denied" for its folder and would leave a ~130 MB orphan per run. Only its test points are deleted.
    name = f"{env.get('QDRANT_COLLECTION_PREFIX', 'aw_')}selftest"

    @guard("qdrant", "request without API key is rejected")
    def _():
        code, _ = http("GET", f"{base}/collections", ctx)
        if code not in (401, 403):
            raise RuntimeError(f"unauthenticated GET returned HTTP {code}")

    @guard("qdrant", "upsert / filtered search / delete points (reusable self-test collection)")
    def _():
        try:
            code, body = http("GET", f"{base}/collections/{name}", ctx, hdr)
            if code == 404:
                code, body = http("PUT", f"{base}/collections/{name}", ctx, hdr, {"vectors": {"size": 4, "distance": "Cosine"}})
                assert code == 200, f"create -> HTTP {code} {body[:200]!r}"
            else:
                assert code == 200, f"collection lookup -> HTTP {code} {body[:200]!r}"
            code, body = http("PUT", f"{base}/collections/{name}/points?wait=true", ctx, hdr, {"points": [
                {"id": 1, "vector": [1, 0, 0, 0], "payload": {"project_id": "a"}},
                {"id": 2, "vector": [1, 0.1, 0, 0], "payload": {"project_id": "b"}}]})
            assert code == 200, f"upsert -> HTTP {code} {body[:200]!r}"
            code, body = http("POST", f"{base}/collections/{name}/points/search", ctx, hdr, {
                "vector": [1, 0, 0, 0], "limit": 5, "filter": {"must": [{"key": "project_id", "match": {"value": "b"}}]}})
            hits = json.loads(body).get("result", [])
            assert code == 200 and [h["id"] for h in hits] == [2], f"filtered search -> {code} {hits}"
        finally:
            http("POST", f"{base}/collections/{name}/points/delete?wait=true", ctx, hdr, {"points": [1, 2]})


# ---- embeddings (TEI) -------------------------------------------------------------------------------------
def check_embeddings(env, ctx, ca):
    base = env.get("EMBEDDING_BASE_URL")
    if not base:
        return record("embeddings", "config", SKIP, "EMBEDDING_BASE_URL not set")

    @guard("embeddings", "request without key is rejected")
    def _():
        code, _ = http("POST", f"{base}/embed", ctx, body={"inputs": ["x"]})
        if code not in (401, 403):
            raise RuntimeError(f"unauthenticated /embed returned HTTP {code}")

    @guard("embeddings", "/embed returns a vector")
    def _():
        code, body = http("POST", f"{base}/embed", ctx, {"authorization": f"Bearer {env.get('EMBEDDING_API_KEY', '')}"},
                          {"inputs": ["Advise Workbench shared services check"], "normalize": True})
        if code != 200:
            raise RuntimeError(f"HTTP {code}: {body[:200]!r}")
        dim = len(json.loads(body)[0])
        if dim != 384:
            raise RuntimeError(f"expected 384 dimensions for bge-small, got {dim}")
        return f"{dim} dimensions ({env.get('EMBEDDING_MODEL', '?')})"


# ---- openobserve + otel collector ----------------------------------------------------------------------------
def check_telemetry(env, ctx, ca):
    oo = env.get("OPENOBSERVE_URL")
    if not oo:
        record("openobserve", "config", SKIP, "OPENOBSERVE_URL not set")
    else:
        org = env.get("OPENOBSERVE_ORG", "default")
        basic = base64.b64encode(f"{env.get('OPENOBSERVE_USER', '')}:{env.get('OPENOBSERVE_PASSWORD', '')}".encode()).decode()

        @guard("openobserve", "health endpoint")
        def _():
            code, _ = http("GET", f"{oo}/healthz", ctx)
            if code != 200:
                raise RuntimeError(f"HTTP {code}")

        @guard("openobserve", "tenant credentials accepted")
        def _():
            code, _ = http("GET", f"{oo}/api/{org}/streams", ctx, {"authorization": f"Basic {basic}"})
            if code != 200:
                raise RuntimeError(f"HTTP {code}")

    otlp = env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp:
        return record("otel", "config", SKIP, "OTEL_EXPORTER_OTLP_ENDPOINT not set")
    token = ""
    for part in env.get("OTEL_EXPORTER_OTLP_HEADERS", "").split(","):
        k, _, v = part.partition("=")
        if k.strip().lower() == "authorization":
            token = urllib.parse.unquote(v.strip())
    span_name = f"aw-check-{uuid.uuid4().hex[:8]}"
    now = time.time_ns()
    payload = {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "aw-check"}},
        {"key": "aw.tenant", "value": {"stringValue": env.get("OTEL_RESOURCE_ATTRIBUTES", "").partition("=")[2] or "unknown"}}]},
        "scopeSpans": [{"spans": [{"traceId": uuid.uuid4().hex, "spanId": uuid.uuid4().hex[:16], "name": span_name,
                                   "kind": 1, "startTimeUnixNano": str(now - 1_000_000), "endTimeUnixNano": str(now)}]}]}]}

    @guard("otel", "OTLP without token is rejected")
    def _():
        code, _ = http("POST", f"{otlp}/v1/traces", ctx, body=payload)
        if code not in (401, 403):
            raise RuntimeError(f"HTTP {code}")

    sent = []

    @guard("otel", "OTLP span accepted by collector")
    def _():
        code, body = http("POST", f"{otlp}/v1/traces", ctx, {"authorization": token}, payload)
        if code != 200:
            raise RuntimeError(f"HTTP {code}: {body[:200]!r}")
        sent.append(True)

    if sent and oo:
        org = env.get("OPENOBSERVE_ORG", "default")
        basic = base64.b64encode(f"{env.get('OPENOBSERVE_USER', '')}:{env.get('OPENOBSERVE_PASSWORD', '')}".encode()).decode()
        found = False
        for _ in range(12):  # ingestion is batched: allow up to ~60 s
            time.sleep(5)
            code, body = http("POST", f"{oo}/api/{org}/_search?type=traces", ctx, {"authorization": f"Basic {basic}"}, {
                "query": {"sql": f"SELECT operation_name FROM \"default\" WHERE operation_name = '{span_name}'",
                          "start_time": int((time.time() - 600) * 1e6), "end_time": int((time.time() + 60) * 1e6),
                          "from": 0, "size": 5}})
            if code == 200 and json.loads(body).get("hits"):
                found = True
                break
        record("otel", "span visible in OpenObserve", PASS if found else WARN,
               "" if found else "not found within 60 s (check the collector logs and the tenant's search permission)")


# ---- celery ----------------------------------------------------------------------------------------------------
def check_celery(env, ctx, ca):
    url = env.get("CELERY_BROKER_URL")
    if not url:
        return record("celery", "config", SKIP, "CELERY_BROKER_URL not set")
    try:
        from celery import Celery
    except ImportError:
        return record("celery", "task round-trip", SKIP, "celery not installed")
    app = Celery("aw-check", broker=url, backend=env.get("CELERY_RESULT_BACKEND"))
    app.conf.broker_use_ssl = {"ca_certs": ca, "cert_reqs": ssl.CERT_REQUIRED}
    app.conf.redis_backend_use_ssl = {"ssl_ca_certs": ca, "ssl_cert_reqs": ssl.CERT_REQUIRED}

    @guard("celery", "aw.ping round-trip through RabbitMQ + Redis")
    def _():
        res = app.send_task("aw.ping", queue="ingest")
        out = res.get(timeout=30)
        if out != "pong":
            raise RuntimeError(f"unexpected result {out!r}")

    @guard("celery", "Docling converts and chunks a document in the worker")
    def _():
        out = app.send_task("aw.docling_smoke", queue="ingest").get(timeout=240)
        if not out.get("chunks"):
            raise RuntimeError(f"no chunks produced: {out}")
        return f"{out['chunks']} chunk(s), models at {out.get('artifacts_path')}"


CHECKS = {
    "postgres": check_postgres, "redis": check_redis, "rabbitmq": check_rabbitmq, "s3": check_s3,
    "qdrant": check_qdrant, "embeddings": check_embeddings, "telemetry": check_telemetry,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", help="env file holding the client block (default: process environment)")
    ap.add_argument("--ca", help="path to ca.crt, or 'system' for public links (default: SSL_CA_FILE from the env)")
    ap.add_argument("--only", help="comma-separated subset: " + ",".join([*CHECKS, "celery"]))
    ap.add_argument("--worker", action="store_true", help="also run the Celery/Docling round-trip (needs the worker profile up)")
    args = ap.parse_args()

    env = load_env(args.env)
    ca = args.ca or env.get("SSL_CA_FILE")
    if not ca or (ca != "system" and not Path(ca).is_file()):
        print(f"CA certificate not found ({ca!r}); pass --ca", file=sys.stderr)
        return 2
    ctx = tls_context(ca)

    wanted = set(args.only.split(",")) if args.only else {*CHECKS, *(["celery"] if args.worker else [])}
    for name, fn in {**CHECKS, "celery": check_celery}.items():
        if name in wanted:
            print(f"{name}:")
            fn(env, ctx, ca)

    counts = {s: sum(1 for r in results if r[2] == s) for s in (PASS, WARN, SKIP, FAIL)}
    print("\n" + "  ".join(f"{s}={n}" for s, n in counts.items()))
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
