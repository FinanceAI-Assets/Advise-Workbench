"""Model providers. Each exposes ``capabilities``, ``is_enabled()``, ``default_models`` and ``create_message(...)``.

``create_message`` takes Anthropic Messages API arguments (model, system, messages, max_tokens, temperature,
tools, …) and returns a message with ``content`` blocks, ``stop_reason`` and ``usage``, so callers handle
every provider the same way.
"""
