# Model providers

The app reaches its language model through one module, `src/llm/gateway.py`. The provider is chosen by a single setting, `LLM_PROVIDER` in `.env`, so the same code runs on a local Claude Code sign-in, the Anthropic API, OpenAI or an OpenAI-compatible router, Azure OpenAI, or Claude on AWS Bedrock.

## Choosing a provider

Every provider has its own settings, and they can all be in `.env` at the same time. To switch, change `LLM_PROVIDER` and restart the backend.

| `LLM_PROVIDER` | Use it when | Required settings |
|---|---|---|
| `claude_cli` | You have a Claude Code subscription and no API key | Claude Code installed; `claude auth login` run once |
| `anthropic` | You have an Anthropic API key | `ANTHROPIC_API_KEY` |
| `openai` | You use the OpenAI API | `OPENAI_API_KEY`, `OPENAI_MODEL` (or `LLM_MODEL`) |
| `azure_openai` | You use Azure OpenAI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` |
| `bedrock` | You use Claude through AWS Bedrock | `AWS_REGION`, `BEDROCK_MODEL`, plus AWS credentials (keys, `AWS_PROFILE`, or the default boto3 chain) |
| `groq`, `openrouter`, `mistral`, `deepseek`, `together`, `xai` | You use one of these hosted services | `<NAME>_API_KEY` (for example `GROQ_API_KEY`) and `LLM_MODEL` |
| `litellm`, `ollama`, `lmstudio` | You run a proxy or local server on its default port | `LLM_MODEL` (`LITELLM_API_KEY` if your proxy needs it) |
| `openai_compatible` | Any other `/chat/completions` server | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` if the server needs one |

`.env.example` has a commented block for each provider that you can copy.

These generic values override the active provider's own settings: `LLM_MODEL`, `LLM_PLANNING_MODEL`, `LLM_CRITIQUE_MODEL`, `LLM_API_KEY` and `LLM_BASE_URL`. The generic `openai_compatible` provider sends only `LLM_API_KEY`, so a provider-specific key such as `OPENAI_API_KEY` is never sent to an address you typed in.

### Checking the setup

```bash
make llm.check          # validates the config and readiness; spends no tokens
make llm.check PING=1   # also sends one tiny request to prove the credentials work
python -m src.llm providers
```

When the app starts it validates the provider config and logs the provider, models and capabilities. The readiness check runs in the background, so startup isn't delayed. An invalid config is logged with the name of the env var to fix. Set `LLM_REQUIRED=true` to stop startup instead, which is the recommended setting for production. Admins can call `GET /api/admin/llm/status` for the same report.

## Models per tier

The app uses three tiers: `default` for bulk drafting, `planning` for outlines and plans, and `critique` for reviews.

| Order | Where the model name comes from |
|---|---|
| 1 | `LLM_PLANNING_MODEL` / `LLM_CRITIQUE_MODEL` (that tier only) |
| 2 | `LLM_MODEL` |
| 3 | The provider's own setting: `CLAUDE_CLI_MODEL`, `ANTHROPIC_MODEL` (then `ANTHROPIC_CLAUDE_MODEL`), `OPENAI_MODEL`, `AZURE_OPENAI_DEPLOYMENT`, `BEDROCK_MODEL` |

A tier that isn't set uses the default tier. With `claude_cli` and no model set, the CLI uses its own default model. `MODEL_TIERING_ENABLED=false` sends every call to the default tier.

## What each provider can do

| Capability | `anthropic` | `bedrock` | `claude_cli` | `openai`, presets, `azure_openai` |
|---|---|---|---|---|
| Agent tool calling | Yes | Yes | Yes, through the local MCP bridge (below) | Yes (`OPENAI_COMPAT_SUPPORTS_TOOLS=false` turns it off) |
| Image input (visual QA) | Yes | Yes | Yes | Yes (`OPENAI_COMPAT_SUPPORTS_VISION=false` turns it off) |
| Extended thinking (planner) | Yes | Yes | No | No |
| Anthropic bash / text-editor tools | Yes | Opt-in (`BEDROCK_ANTHROPIC_TOOLS_ENABLED`) | No | No |

When a capability is missing, the app degrades instead of failing:

- **No tool calling:** document agents write in a single call from the context they are given.
- **No extended thinking:** the planner makes a plain call, and there is no thinking trace in the UI.
- **No image input:** image-based calls raise a clear error, and visual QA is skipped.
- **No Anthropic tools:** the bash and text-editor endpoints return an error naming the provider.

## Reliability

Every model call goes through the same steps in the gateway, whatever the provider:

1. **Error mapping.** Each provider turns its own failures into one set of errors: `LLMAuthError`, `LLMBadRequestError`, `LLMRateLimitError`, `LLMTimeoutError`, `LLMUnavailableError` and `LLMConfigError` (see `src/llm/errors.py`).
2. **Retry.** Rate limits, timeouts, 5xx responses and connection failures are retried up to `LLM_MAX_RETRIES` times, with exponential backoff and jitter. A provider's `retry-after` hint is honoured, up to 60s. Bad requests and authentication failures are not retried. A run abort is still checked while the gateway waits between attempts.
3. **Circuit breaker.** After `LLM_CIRCUIT_BREAKER_FAILURES` failures in a row, calls to that provider fail fast for `LLM_CIRCUIT_BREAKER_RESET_SEC` seconds. Then one trial call is let through.
4. **Fallback.** If the primary provider is still unavailable after the retries and `LLM_FALLBACK_PROVIDER` is set, the call is replayed on the fallback with `LLM_FALLBACK_MODEL`. Request fields the fallback doesn't support, such as thinking, are dropped. A call in the middle of a tool loop only falls back to a provider that returns `tool_use` blocks.
5. **Usage.** Tokens are charged to the run and project budgets exactly once, in the gateway. The old per-caller `_record_message_usage` helpers are kept as no-ops so existing imports still work.

Providers are cached by a fingerprint of their resolved settings. SDK clients and HTTP connection pools are therefore reused across calls, and any settings change creates a fresh instance. The OpenAI-compatible provider streams responses over SSE, so a run abort lands while the model is still writing.

## Claude CLI with agent tools

The CLI can't import the app's Python tools, but it can talk MCP. The `claude_cli` provider (`src/llm/providers/claude_cli/`) connects the two without the Claude Agent SDK:

1. The first time a process (the API server or a `run_execution_worker`) needs tools in CLI mode, it starts a small HTTP server on `127.0.0.1` on a random port. This is `tool_bridge.py`.
2. Each agent tool loop opens a session with a random bearer token. The token is bound to that agent's allowed tools, a tool executor, and a copy of the caller's context, which carries the run budget, project and run IDs, and abort state.
3. The CLI is started with `--mcp-config` pointing at that session, plus `--strict-mcp-config`, `--tools ""` (no built-in tools), `--allowedTools mcp__advise__<tool>,…` and `--permission-mode dontAsk`.
4. The CLI runs its own tool loop and calls the app's tools over the bridge. The tools run in-process, with embeddings already loaded and the same allow-list and error handling as the API tool loop.
5. The provider reads the CLI's stream-json output while it runs. It reports each tool round as an `agent_tool_round` event, so the UI shows progress, and it charges the session's total usage once at the end.

Safeguards:

- The bridge accepts only loopback `Host` headers, to block DNS rebinding.
- Requests must carry a valid session token, and a session is removed as soon as its call ends.
- The CLI never inherits `ANTHROPIC_API_KEY` or `ANTHROPIC_BASE_URL`, so it always uses its own sign-in.
- Tool rounds are limited to the agent's `max_rounds`. Once the limit is reached, further calls are told to stop, and a hard cap of `max_rounds × 8` calls stays in force.
- Delegated tool sessions are never retried, because tools may already have written data.

`CLAUDE_CLI_TOOLS_ENABLED=false` switches back to single-call generation. Each CLI call takes about 1–3 seconds of process start-up that API providers don't have. `CLAUDE_CLI_TIMEOUT_SEC` caps a single call or session.

## Before offering a new model to users

The prompts and skills were written for Claude. A new model can pass every unit test and still produce weaker documents. Before relying on a new model, run the sample scenarios in `data/examples/northwind-p2p/run-scenarios/` on it and compare the quality, guardrail and evidence results with a Claude run.

The OpenAI-compatible, Azure and Bedrock providers are covered by unit tests against fake transports and clients. Run `make llm.check PING=1` against a real endpoint before using one.

## How it is built

```
src/llm/
├── gateway.py              create_message(), run_tool_session(), capabilities(), is_enabled(), model_for(), health()
├── config.py               LLM_PROVIDER + per-provider settings -> LLMConfig (validation, precedence, fallback)
├── presets.py              OpenAI-compatible endpoints (openai, groq, openrouter, ollama, ...)
├── factory.py              ProviderRegistry: lazy imports, cached instances keyed by config fingerprint
├── base_provider.py        BaseLLMProvider contract, HealthStatus, ToolCallRecord
├── capabilities.py         capability flags (tools, vision, thinking, anthropic_tools, delegated_tools)
├── errors.py               provider-neutral error types
├── middleware/
│   ├── resilience.py       retry with backoff, per-provider circuit breaker
│   └── usage.py            single usage charge + metrics + span attributes
├── startup.py              startup validation and shutdown cleanup
├── __main__.py             python -m src.llm check [--ping]
└── providers/
    ├── anthropic_api.py    Anthropic SDK (cached client, error mapping)
    ├── bedrock.py          AnthropicBedrock (boto3 via anthropic[bedrock])
    ├── openai_compatible.py  /chat/completions over httpx, SSE streaming, tool translation
    ├── azure_openai.py     Azure deployment / v1 routes, api-key header
    └── claude_cli/         claude -p runner, transcript folding, loopback MCP tool bridge
```

`gateway.create_message()` takes Anthropic Messages API arguments (`model`, `system`, `messages`, `max_tokens`, `temperature`, `tools`, …). Whatever the provider, it returns a message with `content` blocks, `stop_reason` and `usage`. `src/llm/claude.py` (`claude_generate`, `claude_generate_json`, …) and `src/agents/tool_agent.py` (`run_subagent_tool_loop`, …) keep their function names and handle token-budget compression and run aborts. Retries, the circuit breaker and usage charging live in the gateway.

### Adding a provider

1. Add `src/llm/providers/<name>.py` with a `BaseLLMProvider` subclass. Set `name` and `capabilities`, implement `is_enabled()` and `create_message(*, stream, beta, on_event, **kwargs)`, and raise `src.llm.errors` types. Override `health_check()` and `close()` if the provider holds clients.
2. Register it in `ProviderRegistry._providers` in `src/llm/factory.py` as `"module:Class"`, and add its name to `PROVIDERS` in `src/llm/config.py`. A plain OpenAI-compatible service only needs an entry in `src/llm/presets.py` and a key field in `src/core/config.py`.
3. Add its settings to `src/core/config.py` and `.env.example`, and resolve them in `load_llm_config()`.
4. Add tests under `tests/unit/llm/`.

## The bridge script

`scripts/claude_cli_bridge.py` is the earlier way to run on a Claude Code subscription. The app stays on the `anthropic` provider, and `ANTHROPIC_BASE_URL` points at the bridge. It still works, but it has no tool calling. `LLM_PROVIDER=claude_cli` does the same job, includes agent tools, and needs no second process.
