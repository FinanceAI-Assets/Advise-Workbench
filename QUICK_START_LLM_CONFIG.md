# Quick Start: LLM Configuration (PHASE 2)

## 30-Second Setup

1. **Edit `.env` file:**
   ```bash
   # Anthropic Claude (Recommended)
   LLM_PROVIDER=anthropic
   LLM_API_KEY=sk-ant-v0-your-key-here
   LLM_MODEL=claude-3-5-sonnet-20241022
   LLM_PLANNING_MODEL=claude-opus-4-1
   LLM_CRITIQUE_MODEL=claude-3-5-sonnet-20241022
   ```

2. **Start the app:**
   ```bash
   uvicorn src.app.main:app --reload
   ```

Done! The app will validate your configuration on startup.

---

## Other Providers

### OpenAI
```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=sk-your-openai-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

### Groq (Fast & Cheap)
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
# No API key needed
```

### Local Ollama
```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=mistral
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `LLM_PROVIDER not set` | Add to `.env`: `LLM_PROVIDER=anthropic` |
| `LLM_API_KEY not set` | Add to `.env`: `LLM_API_KEY=sk-...` |
| `LLM_MODEL not set` | Add to `.env`: `LLM_MODEL=claude-3-5-sonnet-20241022` |
| Invalid API key | Verify key format matches provider (sk-ant-* for Anthropic, sk-* for OpenAI, gsk_* for Groq) |
| Connection error | Check endpoint is reachable: `curl https://api.openai.com/v1/models -H "Authorization: Bearer YOUR_KEY"` |
| Claude CLI not found | Install from https://claude.ai/download or use a different provider |

---

## Documentation

- **Complete Guide**: See `LLM_ENV_CONFIG_GUIDE.md`
- **Implementation Details**: See `PHASE2_ENV_CONFIG_IMPLEMENTATION.md`
- **Examples**: See `.env.example`

## Support

Questions? Check `.env.example` for all examples, or consult the full guide in `LLM_ENV_CONFIG_GUIDE.md`.
