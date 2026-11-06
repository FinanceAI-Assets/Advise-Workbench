"""RAG Agent: Path 1.b for knowledge base search in Phase 2.

Searches the knowledge base (RAG1) and decides if answer is sufficient or generation needed.
Currently uses placeholder with dummy data.
"""

import logging
from typing import Any
from datetime import datetime

from src.llm.claude import claude_generate_json, is_claude_enabled
from src.core.observability.metrics import increment

_LOG = logging.getLogger(__name__)


def _get_rag1_placeholder_results(query: str) -> dict[str, Any]:
    """Get placeholder RAG results (dummy data for now).

    This will be replaced with real RAG integration later.
    """
    # Dummy documents for demonstration
    dummy_docs = [
        {
            "id": "doc_q4_2024_report",
            "title": "Q4 2024 Business Report",
            "excerpt": "Q4 2024 showed strong performance with 15% growth in revenue...",
            "relevance": 0.95,
            "source": "knowledge_base"
        },
        {
            "id": "doc_strategic_plan_2024",
            "title": "Strategic Plan 2024",
            "excerpt": "Our strategic initiatives focus on market expansion and operational efficiency...",
            "relevance": 0.82,
            "source": "knowledge_base"
        },
        {
            "id": "doc_project_status",
            "title": "Current Project Status",
            "excerpt": "All active projects are on track with 85% completion rate...",
            "relevance": 0.75,
            "source": "knowledge_base"
        }
    ]

    return {
        "query": query,
        "documents": dummy_docs,
        "total_found": len(dummy_docs),
        "search_confidence": 0.8,
        "timestamp": datetime.now().isoformat()
    }


def search_knowledge_base(router_input: dict[str, Any]) -> dict[str, Any]:
    """Search RAG knowledge base for user query (Path 1.b).

    Args:
        router_input: Dict containing user_instruction and context

    Returns:
        Dict with search results and decision recommendation
    """
    user_instruction = router_input.get("user_instruction", "")
    conversation_digest = router_input.get("conversation_digest", "")
    plan_payload = router_input.get("plan_payload", {})
    init_state = router_input.get("init_state", {})

    try:
        # Get RAG results (placeholder for now)
        rag_results = _get_rag1_placeholder_results(user_instruction)
        documents = rag_results.get("documents", [])

        # Build context from found documents
        doc_context = "\n".join([
            f"- {doc.get('title')}: {doc.get('excerpt')}"
            for doc in documents[:5]
        ])

        # Use LLM to decide if answer is sufficient or generation needed
        if not is_claude_enabled():
            _LOG.warning("Claude not enabled for RAG decision, defaulting to generation")
            return {
                "success": True,
                "documents": documents,
                "context": doc_context,
                "should_answer": False,
                "should_generate": True,
                "confidence": 0.3,
                "answer_preview": "",
                "reasoning": "LLM unavailable; recommend generation",
                "accumulated_context": {
                    "rag_documents": documents,
                    "rag_context": doc_context,
                    "conversation_digest": conversation_digest,
                    "plan_payload": plan_payload,
                    "init_state": init_state
                }
            }

        decision_prompt_system = "You are a RAG decision agent. Based on search results, decide if the information is sufficient to answer directly or if generation is needed."
        decision_prompt_user = f"""Based on the search results below, decide if:
1. The information is SUFFICIENT to answer the user's question directly (should_answer=true)
2. The information needs file GENERATION to be properly presented (should_answer=false)

User Query: {user_instruction}

Search Results:
{doc_context}

Respond with JSON:
{{
  "should_answer": true or false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "answer_preview": "if should_answer is true, provide the answer based on docs"
}}"""

        decision = claude_generate_json(
            system=decision_prompt_system,
            user=decision_prompt_user,
            temperature=0.5,
            max_tokens=800,
        )

        increment("rag_search_total")
        _LOG.info(f"RAG search completed: should_answer={decision.get('should_answer')}")

        return {
            "success": True,
            "documents": documents,
            "context": doc_context,
            "should_answer": decision.get("should_answer", False),
            "should_generate": not decision.get("should_answer", True),
            "confidence": decision.get("confidence", 0.5),
            "answer_preview": decision.get("answer_preview", "") if decision.get("should_answer") else "",
            "reasoning": decision.get("reasoning", ""),
            "accumulated_context": {
                "rag_documents": documents,
                "rag_context": doc_context,
                "conversation_digest": conversation_digest,
                "plan_payload": plan_payload,
                "init_state": init_state
            }
        }

    except Exception as e:
        _LOG.error(f"RAG agent error: {e}", exc_info=True)
        return {
            "success": False,
            "documents": [],
            "context": "",
            "should_answer": False,
            "should_generate": True,
            "confidence": 0.0,
            "answer_preview": "",
            "reasoning": "RAG search failed",
            "error": str(e),
            "accumulated_context": {
                "rag_documents": [],
                "rag_context": "",
                "conversation_digest": conversation_digest,
                "plan_payload": plan_payload,
                "init_state": init_state
            }
        }
