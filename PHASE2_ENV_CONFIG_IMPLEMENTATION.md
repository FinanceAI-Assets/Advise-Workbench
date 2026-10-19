# PHASE 2: Environment-Variable-Only LLM Configuration - Implementation Summary

## Overview

The Advise Workbench LLM system has been refactored to support **any model via environment variables only**. All configuration now comes exclusively from `.env` file, with no YAML fallback, no auto-detection, and no hardcoded defaults.

## User Benefit

✅ **Work with any LLM**: Anthropic Claude, OpenAI, Groq, Azure, local servers  
✅ **Simple configuration**: Just set environment variables in `.env`  
✅ **Predictable behavior**: No hidden defaults, no config file magic  
✅ **Easy deployment**: Works in Docker, Kubernetes, Cloud platforms  

## Required Environment Variables

```bash
# Provider selection (required)
LLM_PROVIDER=anthropic|claude_cli|openai_compatible|groq

# Model configuration (required)
LLM_MODEL=<model-name>                    # e.g., claude-3-5-sonnet, gpt-4
LLM_API_KEY=<api-key>                     # Not needed for claude_cli

# Tiered models (optional; default to LLM_MODEL)
LLM_PLANNING_MODEL=<model-name>           # For planning phase
LLM_CRITIQUE_MODEL=<model-name>           # For critique phase

# Custom endpoint (optional; for openai_compatible)
LLM_BASE_URL=<url>                        # e.g., https://api.openai.com/v1
```

## Files Modified

### 1. **src/llm/config.py** ← Core Logic
**Changes:**
- Removed `_file_config()` usage for YAML loading
- Removed auto-detection from API key format
- Added strict validation: all required vars must be set
- Commented out legacy fallback code for reference

**New Behavior:**
- Raises `ValueError` if `LLM_PROVIDER` not set
- Raises `ValueError` if `LLM_API_KEY` not set (except claude_cli)
- Raises `ValueError` if `LLM_MODEL` not set
- Planning/Critique models default to main model if not set

### 2. **src/llm/providers/anthropic_api.py**
**Changes:**
- `default_models` property now reads from `config.models` instead of `settings`
- Commented out: `settings.anthropic_claude_model`, `anthropic_planning_model`, `anthropic_critique_model` fallbacks

### 3. **src/llm/providers/groq.py**
**Changes:**
- Removed hardcoded `self.default_models = {"default": "allam-2-7b", ...}`
- Now reads models from `config.models`
- Commented out: hardcoded "allam-2-7b" defaults

### 4. **src/llm/providers/openai_compatible.py**
**Changes:**
- `default_models` property now reads from `config.models`
- Error message updated to reference environment variables
- Commented out: YAML config reference

### 5. **src/llm/providers/claude_cli.py**
**Changes:**
- `default_models` property now reads from `config.models`
- Error message updated to guide toward LLM_PROVIDER env var
- Commented out: `settings.anthropic_claude_model` fallback

### 6. **.env.example** ← User Documentation
**Added:**
- Comprehensive LLM configuration examples:
  - Anthropic Claude
  - OpenAI GPT-4
  - Groq
  - Local Claude CLI
  - Local LLM servers (Ollama, etc.)
  - Azure OpenAI
- Clear required vs optional variable documentation

### 7. **.env** ← Default Configuration
**Updated:**
- Added example Anthropic configuration
- Added commented examples for other providers
- Removed old `LLM_PROVIDER=claude_cli` (changed to Anthropic)

### 8. **LLM_ENV_CONFIG_GUIDE.md** ← User Guide (NEW)
**Contains:**
- Complete configuration reference
- Examples for each provider
- Migration guide from old system
- Troubleshooting section
- File location guidance

### 9. **tests/unit/test_llm_gateway.py**
**Changes:**
- Updated `test_default_provider_is_anthropic_with_tiered_models()` to test env-var validation
- Updated `test_provider_without_tools_writes_in_one_call()` to set required env vars
- Commented out: legacy test expectations

### 10. **tests/unit/test_llm_env_config.py** ← New Test Suite (NEW)
**Tests:**
- All required env variables validation
- Invalid provider rejection
- Tiered model support (planning, critique different from default)
- Each provider configuration (Anthropic, OpenAI, Groq, Local)
- No YAML fallback behavior
- Whitespace stripping

## Configuration Examples

### Anthropic Claude (Recommended)
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-v0-your-key
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_PLANNING_MODEL=claude-opus-4-1
LLM_CRITIQUE_MODEL=claude-3-5-sonnet-20241022
```

### OpenAI GPT-4
```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=sk-your-openai-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
```

### Groq (Fast)
```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=gsk-your-groq-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=mixtral-8x7b-32768
```

### Local Claude CLI
```bash
LLM_PROVIDER=claude_cli
LLM_MODEL=claude-3-5-sonnet-20241022
```

### Local Ollama Server
```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=mistral
```

## Validation Errors

When required environment variables are missing:

```
ValueError: LLM_PROVIDER environment variable is required. Must be one of: anthropic, claude_cli, openai_compatible, groq

ValueError: LLM_API_KEY environment variable is required for provider 'anthropic'

ValueError: LLM_MODEL environment variable is required. Specify the model name (e.g., claude-3-5-sonnet, gpt-4, llama-2)
```

## Backward Compatibility

❌ **Removed (No longer supported):**
- YAML config file loading (`config/model_config.yaml`)
- Auto-detection from API key format (no longer infers provider from `sk-ant-*`, `gsk_*`, etc.)
- Hardcoded provider defaults (groq's "allam-2-7b", etc.)
- Settings fallbacks (`ANTHROPIC_CLAUDE_MODEL`, `ANTHROPIC_API_KEY` in main config)

✅ **Preserved (as commented code for reference):**
- All old logic remains commented out in source files
- Tests preserve old expectations in comments
- Facilitates future reference or gradual migration

## Testing

Run new test suite:
```bash
pytest tests/unit/test_llm_env_config.py -v
```

Run updated gateway tests:
```bash
pytest tests/unit/test_llm_gateway.py::test_default_provider_is_anthropic_with_tiered_models -v
pytest tests/unit/test_llm_gateway.py::test_provider_without_tools_writes_in_one_call -v
```

## Migration Guide

### From Old Configuration (YAML)
```yaml
# config/model_config.yaml (OLD - no longer used)
provider: anthropic
models:
  default: claude-haiku-4-5
  planning: claude-opus-4-8
```

### To New Configuration (Environment Variables)
```bash
# .env (NEW - only source of truth)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5
LLM_PLANNING_MODEL=claude-opus-4-8
LLM_API_KEY=sk-ant-v0-...
```

## Deployment Notes

### Docker
```dockerfile
ENV LLM_PROVIDER=anthropic
ENV LLM_API_KEY=sk-ant-v0-...
ENV LLM_MODEL=claude-3-5-sonnet-20241022
```

### Kubernetes
```yaml
env:
  - name: LLM_PROVIDER
    value: "anthropic"
  - name: LLM_API_KEY
    valueFrom:
      secretKeyRef:
        name: llm-secrets
        key: api-key
  - name: LLM_MODEL
    value: "claude-3-5-sonnet-20241022"
```

### Environment Variables
```bash
export LLM_PROVIDER=anthropic
export LLM_API_KEY=sk-ant-v0-...
export LLM_MODEL=claude-3-5-sonnet-20241022
```

## Code Quality

- ✅ All old code preserved as comments for reference
- ✅ Comprehensive error messages guide users to fix issues
- ✅ New test suite validates environment-only behavior
- ✅ Updated tests reflect new requirements
- ✅ Configuration guide provided for users

## Next Steps (Optional)

1. Remove YAML config files when legacy references cleared
2. Add LLM provider validation at application startup
3. Add telemetry to track which providers are in use
4. Consider environment variable encryption for secrets in production
