# Shared services (for developers)

Every backend service runs once, on the shared server `172.31.65.20`, and every developer uses the same instances with the same credentials. Nobody has to install or run any of them locally. This page says what is shared, how to connect, and what the checks mean. The server side is documented separately, in the shared-services folder kept by whoever runs the server.

## What is shared

| Service | Address | Setting in `.env` |
|---|---|---|
| Qdrant (vector search) | `https://172.31.65.20:6333` (gRPC `6334`) | `QDRANT_URL` + `QDRANT_API_KEY` |
| SeaweedFS (S3 file storage) | `https://172.31.65.20:8333` | `S3_ENDPOINT_URL` + access key |
| Embeddings (`BAAI/bge-small-en-v1.5`, 384 dimensions) | `https://172.31.65.20:8080` | `EMBEDDING_BASE_URL` + `EMBEDDING_API_KEY` |
| OpenObserve (logs, metrics, traces) | `https://172.31.65.20:5080` | `OPENOBSERVE_URL` |
| OpenTelemetry collector | `https://172.31.65.20:4318` (gRPC `4317`) | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Postgres 16 | `172.31.65.20:5432` | `DATABASE_URL` |
| Redis | `172.31.65.20:6380` (TLS) | `REDIS_URL` |
| RabbitMQ | `172.31.65.20:5671` (AMQPS), admin page `https://172.31.65.20:15671` | `CELERY_BROKER_URL` |

The address is fixed and reachable only from machines on the company network (the AWS WorkSpaces subnet). Every connection is encrypted with the team's own certificate authority, which ships in the repo as `config/shared-services-ca.crt`; `SSL_CA_FILE` points at it.

## Connect in three steps

1. **Get the team file** `advise-workbench-team.env` from the shared-services owner. Everybody gets the same file; it is sent privately (chat or email inside the team).
2. **Paste its contents into your repo-root `.env`**. Never commit `.env`; it is git-ignored on purpose.
3. **Check it works:**
   ```powershell
   scripts\run_agent.cmd --check      # Windows (cmd or PowerShell)
   ```
   ```bash
   ./scripts/run_agent.sh --check     # macOS / Linux / Git Bash
   ```
   Because `DATABASE_URL`, `REDIS_URL` and `CELERY_BROKER_URL` point at the shared server, `run_agent` checks those addresses and starts nothing on your machine.

For a deeper test (SQL login, Redis write, S3, Qdrant search, an embedding, a telemetry round-trip):
```bash
python scripts/check_shared_services.py --env .env
```

## Things to know

- **One database, one queue, one cache for everybody.** Everyone works on the same data. Do not run destructive migrations or wipe tables without telling the team, and expect to see other people's test data.
- **Keep your own work apart** where names are free to choose: add your first name to `QDRANT_COLLECTION_PREFIX`, `OPENOBSERVE_STREAM` and `OTEL_RESOURCE_ATTRIBUTES`, and keep your S3 files under a `<yourname>/` folder.
- **OpenObserve:** with `OPENOBSERVE_ENABLED=true` the app sends its traces, metrics and logs to the shared OpenObserve. Set it to `false` to keep telemetry local.
- **S3 clients (boto3 1.36 or later):** configure `Config(request_checksum_calculation="when_required", response_checksum_validation="when_required")`. Otherwise uploads are stored with extra framing bytes and come back corrupted (SeaweedFS 3.80). `scripts/check_shared_services.py` does this for you.
- **Do not commit or paste the team file outside the team.** If it leaks, tell the owner; they rotate the keys and send a new file.
