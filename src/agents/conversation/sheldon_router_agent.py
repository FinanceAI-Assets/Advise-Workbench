"""Sheldon's router agent: which agent answers a message in an engagement Conversation.

- ``rag``:          a question to look up in the engagement's documents / the Leading Practice Library -> rag_agent
- ``supervisor``:   a deliverable (deck, document, workbook ...) -> discovery, plan, "go", run (supervisor_agent)
- ``conversation``: everything else -> Sheldon's conversational reply

It reads the conversation router's decision (one model call per message, already made for the turn). When the
router could not decide (model down, invalid output, low confidence), a question-shaped message that asks for no
deliverable goes to rag, outside a deliverable flow.
"""

from __future__ import annotations

import re

RAG, SUPERVISOR, CONVERSATION = "rag", "supervisor", "conversation"

# States of a deliverable flow: messages there answer Sheldon's questions about the deliverable.
_BUILD_STATES = {"discovery", "storyline_building", "slide_negotiation", "structure_agreed", "ready_to_plan",
                 "plan_proposed", "confirming"}
_DELIVERABLE_INTENTS = {"commit", "refine", "discovery_answer", "storyline_feedback", "slide_agree", "slide_modify",
                        "structure_approve"}
_CREATE = re.compile(r"\b(create|make|build|draft|generate|prepare|produce|design|write|put together|turn (this|it) into)\b", re.I)
_DELIVERABLE = re.compile(
    r"\b(deck|slides?|presentation|pptx?|docx?|word document|document|report|proposal|memo|brief|spreadsheet|"
    r"workbook|xlsx|excel|financial model|sop|process map|raci|narrative)\b", re.I,
)
_QUESTION = re.compile(
    r"\?\s*$|^\s*(who|whom|whose|what|when|where|why|how|which|is|are|was|were|does|do|did|can|could|should|"
    r"list|explain|describe|summari[sz]e|tell me|find|show me|give me)\b", re.I,
)


def asks_for_deliverable(message: str) -> bool:
    """"Create a deck on ..." asks for a deliverable; "what does the report say ..." does not."""
    return bool(_CREATE.search(message or "") and _DELIVERABLE.search(message or ""))


def is_question(message: str) -> bool:
    return bool(_QUESTION.search((message or "").strip()))


def route(*, intent: str, rationale: str, message: str, state: str, router_failed: bool | None = None) -> str:
    """The agent for this message: ``rag`` | ``supervisor`` | ``conversation``.

    ``router_failed``: the router's decision is a fallback (defaults to its rationale starting with ``router_``)."""
    if asks_for_deliverable(message):
        return SUPERVISOR
    if intent == "knowledge_question":
        return RAG
    failed = rationale.startswith("router_") if router_failed is None else router_failed
    if failed and state not in _BUILD_STATES and is_question(message):
        return RAG
    if intent in _DELIVERABLE_INTENTS or state in _BUILD_STATES:
        return SUPERVISOR
    return CONVERSATION
