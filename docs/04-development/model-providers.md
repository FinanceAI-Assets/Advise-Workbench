# Model providers

The app reaches its language model through one module, `src/llm/gateway.py`. Which service it talks to is a setting, so the same code runs on the Anthropic API, on a local Claude Code sign-in, or on any OpenAI-style service.

## Choosing a provider

Set the provider in `config/model_config.yaml`, or override it in `.env`. Values in `.env` win.

| Provider | Use it when | Required settings |
|---|---|---|
| `anthropic` (default) | You have an Anthropic API key | `ANTHROPIC_API_KEY` |
| `claude_cli` | You have a Claude Code subscription and no API key | `LLM_PROVIDER=claude_cli`; the `claude` command installed and signed in |
| `openai_compatible` | You use OpenAI, Groq, an Azure-style gateway or a local server | `LLM_PROVIDER=openai_compatible`, `LLM_MODEL`, and `LLM_API_KEY` and/or `LLM_BASE_URL` |

Examples for `.env`:

```bash
# Claude Code subscription, no bridge process needed
LLM_PROVIDER=claude_cli

# Groq
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your key>
LLM_MODEL=<model name>

# A local server
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=<model name>
```

`./scripts/run_agent.sh --check` reports which provider is active and whether its settings are complete.

API keys never go in `config/model_config.yaml`; that file is committed.

## Models per tier

The app uses three tiers: `default` for bulk drafting, `planning` for outlines and plans, `critique` for reviews.

| Setting | Tier |
|---|---|
| `LLM_MODEL` or `models.default` | default |
| `LLM_PLANNING_MODEL` or `models.planning` | planning |
| `LLM_CRITIQUE_MODEL` or `models.critique` | critique |

A tier that is not set falls back to the default tier. For `anthropic` and `claude_cli`, unset tiers use the existing `ANTHROPIC_CLAUDE_MODEL`, `ANTHROPIC_PLANNING_MODEL` and `ANTHROPIC_CRITIQUE_MODEL` settings. `MODEL_TIERING_ENABLED=false` sends everything to the default tier.

## What each provider can do

| Capability | `anthropic` | `claude_cli` | `openai_compatible` |
|---|---|---|---|
| Agent tool calling | Yes | No | Yes (switch off with `supports_tools: false`) |
| Image input (visual QA) | Yes | Yes | Yes (switch off with `supports_vision: false`) |
| Extended thinking (planner) | Yes | No | No |
| Anthropic bash / text-editor tools | Yes | No | No |

When a capability is missing the app degrades instead of failing:

- **No tool calling:** document agents write in a single call from the context they are given.
- **No extended thinking:** the planner makes a plain call; there is no thinking trace in the UI.
- **No image input:** image-based calls raise a clear error, and visual QA is skipped.
- **No Anthropic tools:** the bash and text-editor endpoints return an error naming the provider.

## Before offering a new model to users

The prompts and skills were written for Claude. A new model can pass every unit test and still produce weaker documents. Run the sample scenarios in `data/examples/northwind-p2p/run-scenarios/` on the new model and compare the quality, guardrail and evidence results with a Claude run before relying on it.

As of this writing the `openai_compatible` provider has been tested against a fake server only (request and response translation, including a tool-calling round trip). It has not been run against a live OpenAI, Groq or local endpoint.

## How it is built

```
src/llm/
├── gateway.py            create_message(), capabilities(), is_enabled(), model_for(tier)
├── config.py             reads .env settings, then config/model_config.yaml
├── capabilities.py       the capability flags
└── providers/
    ├── anthropic_api.py      Anthropic SDK
    ├── claude_cli.py         runs `claude -p` once per call
    └── openai_compatible.py  /chat/completions over HTTP, with message and tool translation
```

- `gateway.create_message()` takes Anthropic Messages API arguments (`model`, `system`, `messages`, `max_tokens`, `temperature`, `tools`, …) and returns a message with `content` blocks, `stop_reason` and `usage`, whatever the provider. Other providers translate to and from that shape, so the agent tool loops did not need provider-specific code.
- `src/llm/claude.py` and `src/agents/tool_agent.py` (formerly `services/claude.py` and `services/claude_tools.py`) keep their function names (`claude_generate`, `claude_generate_json`, `run_subagent_tool_loop`, …). They hold the cross-cutting logic: token budgets, the circuit breaker, usage charging and run aborts. Only the model call itself moved into the gateway. Renaming these functions is left for the later clean-up stage.

### Adding a provider

1. Add `src/llm/providers/<name>.py` with a class that has `name`, `capabilities`, `default_models`, `is_enabled()` and `create_message(*, stream, beta, on_event, **kwargs)`.
2. Register it in `gateway._build()` and in `PROVIDERS` in `src/llm/config.py`.
3. Add its options to `config/model_config.yaml`.
4. Add tests next to `tests/unit/test_llm_gateway.py`.

## The bridge

`scripts/claude_cli_bridge.py` is the earlier way to run on a Claude Code subscription: the app stays on the `anthropic` provider and `ANTHROPIC_BASE_URL` points at the bridge. It still works. `LLM_PROVIDER=claude_cli` does the same job without a second process to keep running.
