# LLM Environment Variable Configuration Guide

## Overview (PHASE 2)

The application now supports **any LLM model** by configuring it purely through **environment variables**. There is no YAML fallback, no auto-detection, and no hardcoded defaults.

### Key Benefits
✅ **Flexibility**: Use any LLM provider (Anthropic, OpenAI, Groq, local servers, etc.)  
✅ **Predictability**: No hidden defaults or config file precedence  
✅ **Simplicity**: Single source of truth—environment variables  
✅ **Reproducibility**: Easy to share configs and reproduce setups  

---

## Required Environment Variables

### `LLM_PROVIDER` (REQUIRED)
Specifies which LLM provider to use.

**Valid values:**
- `anthropic` — Anthropic Claude via official API
- `openai_compatible` — OpenAI, Groq, Azure, local servers (OpenAI-compatible endpoints)
- `claude_cli` — Local Claude CLI (no API key needed)
- `groq` — *(deprecated, use openai_compatible instead)*

**Example:**
```bash
LLM_PROVIDER=anthropic
```

### `LLM_API_KEY` (REQUIRED, except for `claude_cli`)
Your API key for the chosen provider.

**Format depends on provider:**
- **Anthropic**: `sk-ant-v0-xxxxx...`
- **OpenAI**: `sk-xxxxx...`
- **Groq**: `gsk_xxxxx...`
- **Local server**: Leave empty or omit

**Example:**
```bash
LLM_API_KEY=sk-ant-v0-abcdef123456789...
```

### `LLM_MODEL` (REQUIRED)
The specific model to use.

**Examples by provider:**
| Provider | Model Examples |
|----------|---|
| Anthropic | `claude-3-5-sonnet-20241022`, `claude-opus-4-1`, `claude-haiku-4-5` |
| OpenAI | `gpt-4`, `gpt-4o`, `gpt-3.5-turbo` |
| Groq | `mixtral-8x7b-32768`, `llama2-70b` |
| Local | `mistral`, `llama2`, any model your server supports |

**Example:**
```bash
LLM_MODEL=claude-3-5-sonnet-20241022
```

---

## Optional Environment Variables

### `LLM_PLANNING_MODEL`
Model to use for the planning phase (reasoning/planning step).  
**Default**: Uses `LLM_MODEL` if not set.

```bash
LLM_PLANNING_MODEL=claude-opus-4-1
```

### `LLM_CRITIQUE_MODEL`
Model to use for the critique/review phase.  
**Default**: Uses `LLM_MODEL` if not set.

```bash
LLM_CRITIQUE_MODEL=claude-3-5-sonnet-20241022
```

### `LLM_BASE_URL`
Custom endpoint URL (only for `openai_compatible` provider).  
**Default**: `https://api.openai.com/v1` for OpenAI.

```bash
# For Groq
LLM_BASE_URL=https://api.groq.com/openai/v1

# For local Ollama
LLM_BASE_URL=http://localhost:11434/v1

# For Azure OpenAI
LLM_BASE_URL=https://your-resource.openai.azure.com/
```

---

## Configuration Examples

### Example 1: Anthropic Claude (Most Common)

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-v0-your-actual-key-here
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_PLANNING_MODEL=claude-opus-4-1
LLM_CRITIQUE_MODEL=claude-3-5-sonnet-20241022
```

### Example 2: OpenAI GPT-4

```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=sk-your-openai-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
LLM_PLANNING_MODEL=gpt-4o
LLM_CRITIQUE_MODEL=gpt-4
```

### Example 3: Groq (Fast Inference)

```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=gsk_your-groq-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=mixtral-8x7b-32768
LLM_PLANNING_MODEL=mixtral-8x7b-32768
LLM_CRITIQUE_MODEL=mixtral-8x7b-32768
```

### Example 4: Local Claude CLI

```bash
LLM_PROVIDER=claude_cli
LLM_MODEL=claude-3-5-sonnet-20241022
# No API key needed; uses your local Claude CLI sign-in
```

### Example 5: Local Ollama Server

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=mistral
# No API key needed for local server
```

### Example 6: Azure OpenAI

```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your-azure-api-key
LLM_BASE_URL=https://your-resource.openai.azure.com/
LLM_MODEL=gpt-4
```

---

## File Locations

### Where to Put Configuration

1. **Development (Local)**: Create or edit `.env` in the repo root
   ```bash
   cp .env.example .env
   # Then edit .env with your LLM settings
   ```

2. **Production/Staging**: Set environment variables via:
   - Docker: `docker-compose.yml` or `docker run -e LLM_PROVIDER=...`
   - Kubernetes: ConfigMap or Secret
   - Cloud Platform: Environment variables settings
   - Systemd/Supervisor: `Environment=LLM_PROVIDER=...` in service file

### Do NOT Use

❌ `config/model_config.yaml` — **No longer checked for LLM config**  
❌ Hardcoded defaults in code — **All come from environment**  
❌ Auto-detection from API key — **Explicit provider required**

---

## Validation & Errors

### Startup Validation

The application validates on startup:

1. ✅ `LLM_PROVIDER` is set and valid
2. ✅ `LLM_API_KEY` is set (unless using `claude_cli`)
3. ✅ `LLM_MODEL` is set

If any required variable is missing, you'll see:
```
ValueError: LLM_PROVIDER environment variable is required. Must be one of: anthropic, claude_cli, openai_compatible, groq
ValueError: LLM_API_KEY environment variable is required for provider 'anthropic'
ValueError: LLM_MODEL environment variable is required. Specify the model name (e.g., claude-3-5-sonnet, gpt-4, llama-2)
```

### Fixing Configuration Issues

| Error | Fix |
|-------|-----|
| `LLM_PROVIDER not set` | Add `LLM_PROVIDER=anthropic` to `.env` |
| `LLM_API_KEY not set` | Add `LLM_API_KEY=sk-...` to `.env` |
| `LLM_MODEL not set` | Add `LLM_MODEL=claude-3-5-sonnet-20241022` to `.env` |
| Invalid model for provider | Check model name is correct for your provider |
| Connection refused | Check `LLM_BASE_URL` and endpoint availability |

---

## Migration from Old Config

### Old Way (YAML + Settings Fallback)
```yaml
# config/model_config.yaml
provider: anthropic
base_url: ""
models:
  default: claude-haiku-4-5
  planning: claude-opus-4-8
  critique: claude-sonnet-4-6
```

### New Way (Environment Only)
```bash
# .env
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-v0-...
LLM_MODEL=claude-haiku-4-5
LLM_PLANNING_MODEL=claude-opus-4-8
LLM_CRITIQUE_MODEL=claude-sonnet-4-6
```

---

## Code Changes

### Affected Files

1. **src/llm/config.py** — Now requires all settings from environment
   - Removed YAML config file loading
   - Removed auto-detection from API key format
   - Added strict validation for required env vars
   - Commented out legacy code for reference

2. **src/llm/providers/*.py** — All providers now read models from config
   - `anthropic_api.py`: Models from `config.models`, not `settings`
   - `groq.py`: Models from `config.models`, not hardcoded
   - `openai_compatible.py`: Models from `config.models`
   - `claude_cli.py`: Models from `config.models`

3. **.env.example** — Added comprehensive LLM configuration examples

4. **.env** — Updated with recommended Anthropic configuration

### Legacy Code Preserved

All old code remains in comments for reference during migration:
- YAML config file loading logic (commented)
- Auto-detection from key format (commented)
- Hardcoded provider defaults (commented)
- Settings fallback logic (commented)

---

## Troubleshooting

### "Claude CLI not found"
```bash
# Check Claude CLI is installed
claude --version

# If not installed, download from https://claude.ai/download

# Or switch to a different provider:
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-v0-...
```

### "No model configured"
```bash
# Make sure LLM_MODEL is set
LLM_MODEL=claude-3-5-sonnet-20241022
```

### "API key invalid" or "Unauthorized"
```bash
# Verify API key format for your provider
# Anthropic: sk-ant-v0-*
# OpenAI: sk-*
# Groq: gsk_*

# Check key has proper permissions/hasn't expired
```

### "Connection refused" for custom endpoint
```bash
# Check LLM_BASE_URL is correct
# Test endpoint with curl:
curl -X POST https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mixtral-8x7b-32768","messages":[{"role":"user","content":"test"}]}'
```

---

## Support

For issues or questions about LLM configuration:
1. Check `.env.example` for examples
2. Review error message for what's missing
3. Verify API key format for your provider
4. Test provider endpoint directly (e.g., with curl)
5. Check provider's documentation for model names and limits
