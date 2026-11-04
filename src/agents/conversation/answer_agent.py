"""Answer Agent: Path 1.a for direct conversational answers in Phase 2.

Provides text answers to questions without file generation.
Detects generation requests and signals path switching.
"""

import logging
from typing import Any

from src.llm.claude import claude_generate, is_claude_enabled
from src.core.observability.metrics import increment

_LOG = logging.getLogger(__name__)


def answer_user_question(router_input: dict[str, Any]) -> dict[str, Any]:
    """Generate a conversational answer to user's question (Path 1.a).

    Args:
        router_input: Dict containing user_instruction, conversation_digest, plan_payload, etc.

    Returns:
        Dict with answer, metadata, and path switch signals
    """
    user_instruction = router_input.get("user_instruction", "")
    conversation_digest = router_input.get("conversation_digest", "")
    plan_payload = router_input.get("plan_payload", {})
    project_context = router_input.get("project_context", {})
    init_state = router_input.get("init_state", {})

    # Build context for the conversation
    context_parts = []

    if conversation_digest:
        context_parts.append(f"Previous conversation:\n{conversation_digest}")

    if project_context:
        try:
            context_parts.append(f"Project context:\n{json.dumps(project_context, indent=2)[:500]}")
        except Exception:
            pass

    if plan_payload:
        try:
            context_parts.append(f"Plan details:\n{json.dumps(plan_payload, indent=2)[:500]}")
        except Exception:
            pass

    assembled_context = "\n\n".join(context_parts) if context_parts else ""

    system_prompt = """You are Sheldon, an intelligent execution partner in a document generation platform.

Your role is to answer questions conversationally and helpfully using the provided context.
Keep responses concise, clear, and practical.
If you need more information, ask clarifying questions.

Style:
- Be conversational and supportive
- Use the AgentPersonality catchphrases when appropriate
- Provide actionable insights"""

    user_message = f"""User Question: {user_instruction}

{"Context:\n" + assembled_context if assembled_context else ""}

Please answer the user's question helpfully using the context provided."""

    try:
        if not is_claude_enabled():
            _LOG.warning("Claude not enabled, returning error")
            return {
                "success": False,
                "answer": "I'm unable to process your question right now. Please try again.",
                "sources": [],
                "confidence": 0.0,
                "switch_to_generation": False,
            }

        answer_text = claude_generate(
            system=system_prompt,
            user=user_message,
            temperature=0.7,
            max_tokens=1000,
        )

        # Detect if user is asking for generation (from the original question)
        generation_keywords = ["create", "generate", "make", "build", "produce", "prepare", "develop", "design", "draft"]
        switch_to_generation = any(
            keyword in user_instruction.lower()
            for keyword in generation_keywords
        )

        increment("conversation_answer_total")
        _LOG.info(f"Conversation answer generated, switch_to_generation={switch_to_generation}")

        return {
            "success": True,
            "answer": answer_text,
            "sources": ["conversation", "context"],
            "confidence": 0.85,
            "switch_to_generation": switch_to_generation,
            "accumulated_context": {
                "previous_answer": answer_text,
                "conversation_digest": conversation_digest,
                "plan_payload": plan_payload,
                "init_state": init_state
            }
        }

    except Exception as e:
        _LOG.error(f"Answer agent error: {e}", exc_info=True)
        return {
            "success": False,
            "answer": "I encountered an issue while processing your question. Please try again.",
            "sources": [],
            "confidence": 0.0,
            "switch_to_generation": False,
            "error": str(e)
        }
