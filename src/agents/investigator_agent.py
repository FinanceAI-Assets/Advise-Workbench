"""Investigator Agent: LangGraph-based root cause analysis for Phase 4 evaluation failures.

When Phase 4 quality checks fail 3 times, this agent analyzes patterns,
classifies root cause into 5 categories, explains to user, and routes intelligently.

This is a proper LangGraph agent with state management, not just a Python class.
"""

import json
import logging
from typing import Any, TypedDict

# Try to import LangGraph, with graceful fallback for testing
try:
    from langgraph.graph import StateGraph, START, END
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    # Create dummy classes for testing when langgraph not available
    StateGraph = object
    START = "START"
    END = "END"

from src.llm.claude import claude_generate_json, is_claude_enabled
from src.core.observability.metrics import increment

_LOG = logging.getLogger(__name__)


class InvestigatorState(TypedDict):
    """Complete state for investigator agent workflow."""
    # Input
    attempts: list[dict]
    context: dict

    # Analysis step
    analysis: dict

    # Classification step
    classification: dict

    # Explanation step
    chat_message: str

    # Routing step
    routing_decision: dict

    # Final output
    investigator_confidence: float
    ready_to_route: bool


def analyze_failures_node(state: InvestigatorState) -> InvestigatorState:
    """Analyze all failed attempts to find patterns.

    Node 1: Extract patterns from 3 failed attempts.
    """
    print(f"\n{'─'*80}")
    print(f"[INVESTIGATOR-NODE] 🔍 NODE 1: ANALYZE FAILURES")
    print(f"[INVESTIGATOR-NODE] Input: {len(state['attempts'])} failed attempts")
    _LOG.info(f"[INVESTIGATOR-NODE] analyze_failures: analyzing {len(state['attempts'])} attempts")

    attempts = state["attempts"]
    attempt_summaries = []
    error_messages = []
    error_stages = []

    # Extract key info from each attempt
    for i, attempt in enumerate(attempts):
        try:
            error = attempt.get("error") or attempt.get("message", "Unknown")
            stage = attempt.get("stage", "unknown")
            artifact = attempt.get("artifact", "unknown")

            attempt_summaries.append(
                {
                    "attempt": i + 1,
                    "error": str(error)[:200],
                    "stage": stage,
                    "artifact": artifact,
                }
            )
            error_messages.append(str(error).lower())
            error_stages.append(stage)
        except Exception as e:
            _LOG.warning(f"[INVESTIGATOR-NODE] Could not parse attempt {i}: {e}")
            attempt_summaries.append({"attempt": i + 1, "error": "Parse failed"})

    # Find common patterns
    common_patterns = []
    if len(error_messages) >= 2:
        keywords = set()
        for msg in error_messages:
            words = msg.split()[:10]
            keywords.update(words)

        for keyword in keywords:
            count = sum(1 for msg in error_messages if keyword in msg)
            if count >= len(error_messages) * 0.66:
                common_patterns.append(
                    {
                        "keyword": keyword,
                        "frequency": f"{count}/{len(error_messages)}",
                    }
                )

    # Determine error evolution
    if len(error_stages) >= 2:
        if len(set(error_stages)) == 1:
            error_evolution = f"SAME stage fails every attempt: {error_stages[0]}"
        else:
            error_evolution = f"Different stages fail: {' -> '.join(error_stages)}"
    else:
        error_evolution = "Single attempt"

    analysis = {
        "attempt_summaries": attempt_summaries,
        "common_patterns": common_patterns,
        "error_evolution": error_evolution,
        "total_attempts": len(attempts),
    }

    state["analysis"] = analysis
    _LOG.info(f"[INVESTIGATOR-NODE] analyze_failures: found {len(common_patterns)} patterns")
    print(f"[INVESTIGATOR-NODE]   Patterns found: {len(common_patterns)}")
    print(f"[INVESTIGATOR-NODE]   Error evolution: {error_evolution}")
    print(f"[INVESTIGATOR-NODE] ✅ NODE 1 COMPLETE\n")
    return state


def classify_root_cause_node(state: InvestigatorState) -> InvestigatorState:
    """Classify root cause into one of 5 categories.

    Node 2: Use Claude to classify the failure patterns.
    """
    print(f"{'─'*80}")
    print(f"[INVESTIGATOR-NODE] 🎯 NODE 2: CLASSIFY ROOT CAUSE")
    print(f"[INVESTIGATOR-NODE] Input: {len(state['analysis'].get('attempt_summaries', []))} attempts analyzed")
    _LOG.info(f"[INVESTIGATOR-NODE] classify_root_cause: analyzing patterns")

    analysis = state["analysis"]
    context = state["context"]

    root_causes = {
        "data_problem": "Data Problem",
        "approach_problem": "Approach Problem",
        "requirements_problem": "Requirements Problem",
        "technical_problem": "Technical Problem",
        "llm_problem": "LLM Problem",
    }

    if not is_claude_enabled():
        _LOG.warning("[INVESTIGATOR-NODE] Claude not enabled, using fallback")
        classification = {
            "root_cause": "llm_problem",
            "category": root_causes["llm_problem"],
            "confidence": 0.5,
            "reasoning": "LLM not available for analysis",
        }
        state["classification"] = classification
        return state

    # Prepare classification prompt
    patterns_text = "\n".join(
        [f"- {p['keyword']} (appears in {p['frequency']} attempts)"
         for p in analysis.get("common_patterns", [])]
    )

    context_validation = context.get("context_validation", {})
    has_conflicts = context_validation.get("has_conflicts", False)
    is_stale = context_validation.get("overall_confidence", 1.0) < 0.7

    system_prompt = """You are a root cause classification expert. Analyze generation failures.

Classify into EXACTLY ONE category:
- data_problem: Missing/incomplete/conflicting data
- approach_problem: Wrong strategy/methodology
- requirements_problem: Unclear/ambiguous specifications
- technical_problem: Tool limitation, unsupported format
- llm_problem: Model understanding failure, hallucination, logic error

Return JSON: {"root_cause": "category", "confidence": 0.0-1.0, "reasoning": "..."}"""

    user_prompt = f"""Classify the root cause of these generation failures:

Error Evolution: {analysis.get("error_evolution", "unknown")}

Common Patterns: {patterns_text if patterns_text else "No common patterns found"}

Attempt Summaries:
{json.dumps(analysis.get("attempt_summaries", []), indent=2)}

Context Info:
- Instruction: {context.get("run_instruction", "")[:200]}
- Data/Context conflicts detected: {has_conflicts}
- Context freshness: {"STALE (>140 days)" if is_stale else "FRESH"}
- Context confidence: {context_validation.get("overall_confidence", 1.0):.2f}

Classify the root cause and explain your reasoning."""

    try:
        classification_result = claude_generate_json(
            system=system_prompt,
            user=user_prompt,
            temperature=0.3,
            max_tokens=400,
        )

        root_cause = classification_result.get("root_cause", "llm_problem")
        confidence = min(1.0, max(0.0, classification_result.get("confidence", 0.5)))

        classification = {
            "root_cause": root_cause,
            "category": root_causes.get(root_cause, "Unknown"),
            "confidence": confidence,
            "reasoning": classification_result.get("reasoning", "No reasoning provided"),
            "evidence_from_attempts": analysis.get("attempt_summaries", []),
        }

        increment("investigator_classifications_total")

    except Exception as e:
        _LOG.error(f"[INVESTIGATOR-NODE] Classification failed: {e}")
        classification = {
            "root_cause": "llm_problem",
            "category": root_causes["llm_problem"],
            "confidence": 0.5,
            "reasoning": f"Classification error: {str(e)[:100]}",
        }

    state["classification"] = classification
    _LOG.info(f"[INVESTIGATOR-NODE] classify_root_cause: {classification['root_cause']} "
              f"(confidence={classification['confidence']:.2f})")
    print(f"[INVESTIGATOR-NODE]   Root Cause: {classification['root_cause']}")
    print(f"[INVESTIGATOR-NODE]   Confidence: {classification['confidence']:.1%}")
    print(f"[INVESTIGATOR-NODE]   Reasoning: {classification['reasoning'][:100]}...")
    print(f"[INVESTIGATOR-NODE] ✅ NODE 2 COMPLETE\n")
    return state


def generate_chat_explanation_node(state: InvestigatorState) -> InvestigatorState:
    """Generate user-friendly explanation of findings.

    Node 3: Create chat message showing reasoning.
    """
    print(f"{'─'*80}")
    print(f"[INVESTIGATOR-NODE] 💬 NODE 3: GENERATE CHAT EXPLANATION")
    print(f"[INVESTIGATOR-NODE] Input: {state['classification'].get('root_cause')} at confidence {state['classification'].get('confidence'):.1%}")
    _LOG.info(f"[INVESTIGATOR-NODE] generate_chat_explanation: creating message")

    analysis = state["analysis"]
    classification = state["classification"]

    root_cause = classification.get("root_cause", "unknown")
    category = classification.get("category", "Unknown")
    confidence = classification.get("confidence", 0.5)
    reasoning = classification.get("reasoning", "Unknown")
    total_attempts = analysis.get("total_attempts", 0)

    # Build message
    lines = [
        "Investigator Agent Analysis Complete\n",
        f"I've reviewed all {total_attempts} failed attempts. Here's what I found:\n",
        "---",
        "\nPattern Analysis:",
    ]

    # Add attempt summaries
    for attempt in analysis.get("attempt_summaries", [])[:3]:
        error = attempt.get("error", "Unknown")[:80]
        stage = attempt.get("stage", "?")
        lines.append(f"• Attempt {attempt['attempt']}: Failed at {stage} - \"{error}\"")

    error_evolution = analysis.get("error_evolution", "")
    if error_evolution:
        lines.append(f"\n-> Pattern: {error_evolution}")

    # Add common patterns
    patterns = analysis.get("common_patterns", [])
    if patterns:
        lines.append("\nCommon Keywords:")
        for p in patterns[:3]:
            lines.append(f"• {p['keyword']} ({p['frequency']})")

    # Add root cause classification
    lines.extend(
        [
            "\n---",
            f"\nRoot Cause Classification:",
            f"Category: {category}",
            f"Confidence: {confidence * 100:.0f}%",
            f"\nExplanation:",
            f"{reasoning}",
        ]
    )

    message = "\n".join(lines)
    state["chat_message"] = message
    _LOG.info(f"[INVESTIGATOR-NODE] generate_chat_explanation: message created ({len(message)} chars)")
    print(f"[INVESTIGATOR-NODE]   Message length: {len(message)} chars")
    print(f"[INVESTIGATOR-NODE] ✅ NODE 3 COMPLETE\n")
    return state


def make_routing_decision_node(state: InvestigatorState) -> InvestigatorState:
    """Decide where to route: Phase 2, Phase 3, or escalate.

    Node 4: Final routing decision based on classification.
    """
    print(f"{'─'*80}")
    print(f"[INVESTIGATOR-NODE] 🚦 NODE 4: MAKE ROUTING DECISION")
    print(f"[INVESTIGATOR-NODE] Input: {state['classification'].get('root_cause')}")
    _LOG.info(f"[INVESTIGATOR-NODE] make_routing_decision: making routing decision")

    classification = state["classification"]
    context_validation = state.get("context", {}).get("context_validation", {})

    root_cause = classification.get("root_cause", "llm_problem")
    confidence = classification.get("confidence", 0.5)

    # Data Problem -> Phase 2
    if root_cause == "data_problem":
        clarifications = []

        if context_validation.get("has_conflicts"):
            conflicts = context_validation.get("conflicts", {}).get("conflicts", [])
            for conflict in conflicts[:2]:
                clarifications.append(
                    {
                        "field": conflict.get("field", "unknown"),
                        "wiki": conflict.get("wiki_value", "unknown"),
                        "lp": conflict.get("lp_value", "unknown"),
                        "ask": f"Should we use wiki or best practice for {conflict.get('field')}?",
                    }
                )

        if context_validation.get("is_stale"):
            clarifications.append(
                {
                    "field": "data_freshness",
                    "issue": f"Context is {context_validation.get('age_days', '?')} days old",
                    "ask": "Should we fetch fresh data?",
                }
            )

        routing = {
            "route_to": "phase_2",
            "reason": "Data/context issue needs clarification",
            "message": "Let's clarify the data before retrying.",
            "clarifications": clarifications
            if clarifications
            else [{"ask": "What data is missing or unclear?"}],
            "confidence": confidence,
        }

    # Approach Problem -> Phase 2
    elif root_cause == "approach_problem":
        routing = {
            "route_to": "phase_2",
            "reason": "Wrong approach detected",
            "message": "Let's reconsider the strategy and approach.",
            "ask": "Should we try a different approach?",
            "confidence": confidence,
        }

    # Requirements Problem -> Phase 2
    elif root_cause == "requirements_problem":
        routing = {
            "route_to": "phase_2",
            "reason": "Requirements are unclear or ambiguous",
            "message": "Let's clarify the requirements before retrying.",
            "ask": "Can you clarify what you need?",
            "confidence": confidence,
        }

    # LLM Problem -> Phase 3
    elif root_cause == "llm_problem":
        routing = {
            "route_to": "phase_3",
            "reason": "Model needs better guidance",
            "message": "I'll add more detailed guidance to help generation understand better.",
            "guidance": [
                "Include step-by-step instructions",
                "Provide explicit examples",
                "Add validation checkpoints",
            ],
            "confidence": confidence,
        }

    # Technical Problem -> Escalate
    else:
        routing = {
            "route_to": "escalate",
            "reason": "Format or tool limitation",
            "message": "This format or request isn't currently supported.",
            "alternatives": [
                "Try a different file format",
                "Simplify the request",
                "Use a different approach",
            ],
            "confidence": confidence,
        }

    state["routing_decision"] = routing
    state["investigator_confidence"] = confidence
    state["ready_to_route"] = True

    _LOG.info(f"[INVESTIGATOR-NODE] make_routing_decision: routing to {routing['route_to']}")
    print(f"[INVESTIGATOR-NODE]   Route: {routing['route_to']}")
    print(f"[INVESTIGATOR-NODE]   Reason: {routing.get('reason', '?')}")
    print(f"[INVESTIGATOR-NODE]   Message: {routing.get('message', '?')[:80]}...")
    print(f"[INVESTIGATOR-NODE] ✅ NODE 4 COMPLETE")
    print(f"{'═'*80}\n")
    return state


def build_investigator_graph():
    """Build the LangGraph investigator workflow.

    Nodes:
    1. analyze_failures - Extract patterns
    2. classify_root_cause - Classify into 5 categories
    3. generate_chat_explanation - Create user message
    4. make_routing_decision - Decide phase routing

    Flow: START -> analyze -> classify -> explain -> route -> END
    """
    if not _LANGGRAPH_AVAILABLE:
        # Return a mock graph object when langgraph not available (for testing)
        class MockGraph:
            def invoke(self, state):
                # Run sequential node execution manually
                state = analyze_failures_node(state)
                state = classify_root_cause_node(state)
                state = generate_chat_explanation_node(state)
                state = make_routing_decision_node(state)
                return state
        return MockGraph()

    graph = StateGraph(InvestigatorState)

    # Add nodes
    graph.add_node("analyze", analyze_failures_node)
    graph.add_node("classify", classify_root_cause_node)
    graph.add_node("explain", generate_chat_explanation_node)
    graph.add_node("route", make_routing_decision_node)

    # Add edges
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "classify")
    graph.add_edge("classify", "explain")
    graph.add_edge("explain", "route")
    graph.add_edge("route", END)

    return graph.compile()


# Build the compiled graph (singleton)
_investigator_graph = build_investigator_graph()


def investigate_and_decide(attempts: list[dict], context: dict[str, Any]) -> dict[str, Any]:
    """Execute the investigator workflow.

    This is the main entry point that runs the compiled LangGraph.

    Args:
        attempts: All 3 failed attempts
        context: Run context including context_validation

    Returns:
        Complete investigation result with routing decision
    """
    print(f"[INVESTIGATOR] Starting investigation via LangGraph...")
    _LOG.info(f"[INVESTIGATOR] Starting LangGraph workflow")

    # Prepare initial state
    initial_state: InvestigatorState = {
        "attempts": attempts,
        "context": context,
        "analysis": {},
        "classification": {},
        "chat_message": "",
        "routing_decision": {},
        "investigator_confidence": 0.0,
        "ready_to_route": False,
    }

    # Run the graph
    try:
        final_state = _investigator_graph.invoke(initial_state)

        result = {
            "analysis": final_state.get("analysis", {}),
            "classification": final_state.get("classification", {}),
            "chat_message": final_state.get("chat_message", ""),
            "routing_decision": final_state.get("routing_decision", {}),
            "investigator_confidence": final_state.get("investigator_confidence", 0.0),
            "ready_to_route": final_state.get("ready_to_route", True),
        }

        _LOG.info(
            f"[INVESTIGATOR] LangGraph workflow complete: "
            f"root_cause={final_state.get('classification', {}).get('root_cause')}, "
            f"route_to={final_state.get('routing_decision', {}).get('route_to')}"
        )
        print(f"[INVESTIGATOR] LangGraph workflow complete")
        increment("investigator_investigations_complete")

        return result

    except Exception as e:
        _LOG.error(f"[INVESTIGATOR] LangGraph workflow failed: {e}", exc_info=True)
        print(f"[INVESTIGATOR] ERROR: {e}")
        return {
            "analysis": {},
            "classification": {"root_cause": "llm_problem", "confidence": 0.5},
            "chat_message": f"Investigator workflow error: {str(e)[:100]}",
            "routing_decision": {"route_to": "escalate"},
            "investigator_confidence": 0.3,
            "ready_to_route": False,
        }


# For backward compatibility, also expose the old class interface
class InvestigatorAgent:
    """Legacy class interface for backward compatibility.

    New code should use investigate_and_decide() directly.
    This class maintains the old API but delegates to the LangGraph implementation.
    """

    def __init__(self):
        """Initialize (no-op for compatibility)."""
        self.root_causes = {
            "data_problem": "Data Problem",
            "approach_problem": "Approach Problem",
            "requirements_problem": "Requirements Problem",
            "technical_problem": "Technical Problem",
            "llm_problem": "LLM Problem",
        }

    def investigate_and_decide(self, attempts: list[dict], context: dict[str, Any]) -> dict[str, Any]:
        """Legacy method - delegates to LangGraph implementation."""
        return investigate_and_decide(attempts, context)

    # The step-level methods below delegate to the graph nodes so the legacy
    # class keeps exposing each investigation step on its own.

    @staticmethod
    def _state(**values: Any) -> InvestigatorState:
        state: InvestigatorState = {
            "attempts": [],
            "context": {},
            "analysis": {},
            "classification": {},
            "chat_message": "",
            "routing_decision": {},
            "investigator_confidence": 0.0,
            "ready_to_route": False,
        }
        state.update(values)  # type: ignore[typeddict-item]
        return state

    def analyze_failures(self, attempts: list[dict]) -> dict[str, Any]:
        """Find patterns across the failed attempts."""
        return analyze_failures_node(self._state(attempts=attempts))["analysis"]

    def classify_root_cause(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Classify the root cause of the failures."""
        state = self._state(analysis=analysis, context=context)
        return classify_root_cause_node(state)["classification"]

    def generate_chat_explanation(self, analysis: dict[str, Any], classification: dict[str, Any]) -> str:
        """Write the chat message that explains the investigation."""
        state = self._state(analysis=analysis, classification=classification)
        return generate_chat_explanation_node(state)["chat_message"]

    def make_routing_decision(
        self, classification: dict[str, Any], context_validation: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Decide which phase the run goes back to."""
        state = self._state(
            classification=classification,
            context={"context_validation": context_validation or {}},
        )
        return make_routing_decision_node(state)["routing_decision"]
