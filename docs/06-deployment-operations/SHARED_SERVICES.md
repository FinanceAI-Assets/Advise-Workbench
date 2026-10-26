# Shared services (for developers)

Some backend services run once, on a shared server, and every developer uses the same instances through links in their own `.env`. Nobody has to install or run them locally. This page says what is shared, how to connect, and what the checks mean. The server side is documented separately, in the shared-services folder kept by whoever runs the server.

## What is shared and what is local

| Service | Where it runs | How you reach it |
|---|---|---|
| Qdrant (vector search) | Shared | `QDRANT_URL` link + `QDRANT_API_KEY` |
| SeaweedFS (S3 file storage) | Shared | `S3_ENDPOINT_URL` link + access key |
| Embeddings (`BAAI/bge-small-en-v1.5`, 384 dimensions) | Shared | `EMBEDDING_BASE_URL` link + `EMBEDDING_API_KEY` |
| OpenObserve (logs, metrics, traces) and the OpenTelemetry collector | Shared | `OPENOBSERVE_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT` links |
| Postgres, Redis, RabbitMQ | **Local, on your machine** | `run_agent` finds a running instance or starts one (`scripts/infra.sh`) |

The shared links are public `https://...trycloudflare.com` addresses: no ports, no VPN, no IP addresses. They work from any machine or network. They are protected only by the keys below, so treat the keys like passwords.

## Connect in three steps

1. **Get your keys file** from the shared-services owner. It is called `<your-name>-public.env` and is sent to you privately (chat or email to you only). It contains your own keys, bucket and collection prefix.
2. **Paste its contents into your repo-root `.env`**. `.env.example` shows every setting, commented out. Never commit `.env`; it is git-ignored on purpose.
3. **Check it works:**
   ```powershell
   scripts\run_agent.cmd --check      # Windows (cmd or PowerShell)
   ```
   ```bash
   ./scripts/run_agent.sh --check     # macOS / Linux / Git Bash
   ```
   Look at the "Shared services (public links in .env)" section: every link should say `PASS`.

For a deeper test (S3 upload and download, Qdrant search, an embedding, a telemetry round-trip):
```bash
python scripts/check_shared_services.py --env .env --ca system --only qdrant,s3,embeddings,telemetry
```

## What `run_agent` does with them

Before the tools, model and package checks, `run_agent` probes each link and reports it (details in `README_RUN.md`):

| Result | Meaning | What to do |
|---|---|---|
| `PASS ... answers` | The link is up | Nothing |
| `WARN ... does not answer` | The link is down or has changed | The links are quick tunnels and **change when the owner restarts them**. Ask the owner for a fresh `<your-name>-public.env` and replace the block in `.env`. |
| `WARN no shared-service links in .env` | You have not pasted the block yet | Do step 1 and 2 above |
| `FAIL` instead of `WARN` | `SHARED_SERVICES_REQUIRED=true` is set in your `.env` | Same fixes; unset it to go back to warnings |

## Things to know

- **Your data is namespaced.** Your bucket is `aw-<you>` and your Qdrant collections start with `aw_<you>_`. Use the prefix settings; do not touch other people's.
- **OpenObserve:** with `OPENOBSERVE_ENABLED=true` the app sends its traces, metrics and logs to the shared OpenObserve under your stream. Set it to `false` to keep telemetry local.
- **S3 clients (boto3 1.36 or later):** configure `Config(request_checksum_calculation="when_required", response_checksum_validation="when_required")`. Otherwise uploads are stored with extra framing bytes and come back corrupted (SeaweedFS 3.80). `scripts/check_shared_services.py` does this for you.
- **Not wired in yet:** the application code does not use S3, Qdrant, the embedding service or RabbitMQ yet. The settings are reserved so that when that work lands, nobody has to rename anything in their `.env`.
- **Do not commit or paste keys.** If one leaks, tell the owner; they can rotate it.
