"""Sheldon Router Agent: Intelligent intent analyzer for Phase 2.

Routes user intent to one of three paths using LLM semantic understanding:
- Path 1.a: Conversation (direct answers)
- Path 1.b: RAG search (knowledge retrieval + decision)
- Path 1.c: Generation (file creation)
"""

import logging
from typing import Any

from src.llm.claude import claude_generate_json, is_claude_enabled
from src.core.observability.metrics import increment

_LOG = logging.getLogger(__name__)


def route_user_intent(router_input: dict[str, Any]) -> dict[str, Any]:
    """Analyze user intent and determine routing path using LLM semantic understanding.

    Uses Claude to semantically analyze user intent, not keyword matching.

    Args:
        router_input: Dict containing:
            - user_instruction: User's query/request
            - conversation_digest: Previous conversation context
            - plan_payload: User requirements/context
            - requested_outputs: Deliverables user wants

    Returns:
        Dict with routing decision:
            - path: "1.a" (conversation) | "1.b" (RAG) | "1.c" (generation)
            - reasoning: Why this path was chosen
            - confidence: 0.0-1.0 confidence score
            - needs_rag_context: True if RAG data should be included
            - generation_intent: True if user wants file generation
    """
    user_instruction = router_input.get("user_instruction", "")
    conversation_digest = router_input.get("conversation_digest", "")
    plan_payload = router_input.get("plan_payload", {})
    requested_outputs = router_input.get("requested_outputs", [])

    system_prompt = """You are Sheldon Router Agent, an intelligent intent analyzer for document generation systems.

Your task: Analyze the user's request and determine the BEST path using SEMANTIC understanding (not keyword matching).

Three Available Paths:

Path 1.a: CONVERSATION ONLY
- User wants information/answers without file generation
- Examples: "What are our metrics?", "Tell me about Q4", "How is our project?"
- Response: Direct text answer in chat, no files generated

Path 1.b: RAG SEARCH + DECISION
- User wants to search or find information from the knowledge base
- System will search documents and decide if answer is sufficient or generation is needed
- Examples: "Find Q4 reports", "Search for budget data", "Look for previous presentations"
- Response: Search knowledge base, then either answer or generate based on results

Path 1.c: GENERATION
- User wants to create files/deliverables
- System will generate 7 files: PPTX, DOCX, XLSX, PDF, SOP, Narrative, DrawIO
- Examples: "Create a presentation", "Make a summary document", "Build an analysis report"
- Response: Generate files with optional RAG context for enrichment

Decision Logic:
1. Is the user seeking INFORMATION without asking for files? → Path 1.a or 1.b
2. Is the user explicitly SEARCHING or FINDING something? → Path 1.b
3. Is the user REQUESTING GENERATION of files/deliverables? → Path 1.c
4. UNCERTAIN? → Default to Path 1.c (safe default)

CRITICAL: Analyze SEMANTIC INTENT, not keywords. Consider context and purpose."""

    user_message = f"""User Request: "{user_instruction}"

Previous Context: {conversation_digest if conversation_digest.strip() else "(No previous context)"}

Available Outputs: {', '.join(requested_outputs) if requested_outputs else "All standard outputs (PPTX, DOCX, XLSX, PDF, SOP, Narrative, DrawIO)"}

Analyze the user's intent semantically and determine the routing path.

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "path": "1.a" or "1.b" or "1.c",
  "reasoning": "Brief explanation of why this path was chosen based on semantic analysis",
  "confidence": 0.0-1.0,
  "needs_rag_context": true or false,
  "generation_intent": true or false
}}"""

    try:
        if not is_claude_enabled():
            _LOG.warning("Claude not enabled, defaulting to generation path")
            return {
                "path": "1.c",
                "reasoning": "LLM not available, defaulting to generation",
                "confidence": 0.5,
                "needs_rag_context": False,
                "generation_intent": True,
            }

        routing_decision = claude_generate_json(
            system=system_prompt,
            user=user_message,
            temperature=0.5,
            max_tokens=500,
        )

        # Validate and ensure required fields
        routing_decision.setdefault("path", "1.c")
        routing_decision.setdefault("reasoning", "")
        routing_decision.setdefault("confidence", 0.5)
        routing_decision.setdefault("needs_rag_context", False)
        routing_decision.setdefault("generation_intent", False)

        # Ensure path is valid
        if routing_decision["path"] not in ["1.a", "1.b", "1.c"]:
            routing_decision["path"] = "1.c"

        # Ensure confidence is in range
        routing_decision["confidence"] = max(0.0, min(1.0, float(routing_decision["confidence"])))

        increment("sheldon_router_decision_total")
        _LOG.info(
            f"Router decision: path={routing_decision['path']}, "
            f"confidence={routing_decision['confidence']:.2f}, "
            f"reasoning={routing_decision['reasoning'][:100]}"
        )

        return routing_decision

    except Exception as e:
        _LOG.error(f"Router agent error: {e}", exc_info=True)
        # Safe fallback to generation
        return {
            "path": "1.c",
            "reasoning": "Router error occurred, defaulting to generation",
            "confidence": 0.1,
            "needs_rag_context": False,
            "generation_intent": True,
            "error": str(e)
        }
