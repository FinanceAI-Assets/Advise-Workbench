"""Process extraction agent: turns the source documents into the process model."""

from __future__ import annotations

import json

from src.prompts.prompt_hygiene import wrap_untrusted
from src.core.state import AdviseWorkbenchState
from src.agents.process_extraction import extract_process_model
from src.agents.specialists import _shared
from src.llm import gateway
from src.llm.claude import _extract_first_json_object
from src.agents.tool_agent import _record_message_usage, _extract_final_text_from_message


def run_process_extraction(state: AdviseWorkbenchState) -> AdviseWorkbenchState:
    from src.agents.deliverable_archetype import is_meta_process_model
    from src.evaluation.qa_remediation_channel import strip_qa_feedback

    # Use the immutable original intent to avoid contamination from QA/guardrail annotations
    raw = strip_qa_feedback(str(state.get("user_intent_original") or state.get("raw_text") or ""))
    ctx = strip_qa_feedback(str(state.get("assembled_context") or ""))
    archetype = str(state.get("deliverable_archetype") or "process_doc")

    # When the plan carries discovery (client, outcome, audience, themes), prepend
    # that brief to the raw intent so the extractor names the process after the
    # client's reality rather than the user's conversational chat line (e.g.
    # "Help create the proposal please").
    discovery = state.get("proposal_discovery") if isinstance(state.get("proposal_discovery"), dict) else None
    if discovery:
        brief_lines: list[str] = []
        client = discovery.get("client") if isinstance(discovery.get("client"), dict) else {}
        outcome = discovery.get("outcome") if isinstance(discovery.get("outcome"), dict) else {}
        themes = discovery.get("win_themes") if isinstance(discovery.get("win_themes"), list) else []
        if client:
            name = str(client.get("name") or "").strip()
            industry = str(client.get("industry") or "").strip()
            if name:
                brief_lines.append(
                    f"Client: {name}" + (f" ({industry})" if industry else "")
                )
        if outcome:
            primary = str(outcome.get("primary") or "").strip()
            decision = str(outcome.get("decision") or "").strip()
            if primary:
                brief_lines.append(f"Desired outcome: {primary}")
            if decision:
                brief_lines.append(f"Decision to drive: {decision}")
        if themes:
            theme_text = ", ".join(str(t).strip() for t in themes if str(t).strip())[:400]
            if theme_text:
                brief_lines.append(f"Win themes: {theme_text}")
        if brief_lines:
            raw = (
                "Engagement brief (use this for process_name + metadata):\n- "
                + "\n- ".join(brief_lines)
                + "\n\nUser instruction:\n"
                + str(raw)
            )

    if _shared.is_claude_enabled():
        from src.prompts.registry import get_prompt

        system_prompt = get_prompt("extraction_system")
        system = system_prompt.render_system()

        prompt = get_prompt("extraction_process_user")
        user = prompt.render_user()

        if archetype == "advisory_pov":
            advisory_prompt = get_prompt("extraction_advisory_pov_rules")
            user += "\n\n" + advisory_prompt.render_user()

        user += (
            f"\nInstruction:\n{wrap_untrusted('user_instruction', str(raw))}\n\n"
            f"Context:\n{wrap_untrusted('assembled_context', str(ctx))}\n"
        )
        try:
            # [DEPRECATED: Hardcoded claude_generate_json] Use gateway for provider-agnostic call
            # pm = _shared.claude_generate_json(system=system, user=user, temperature=0.2, max_tokens=2500)
            
            # [NEW: Gateway-based provider-agnostic call with JSON extraction - Supports all LLM providers]
            # All imports at module level: json, gateway, _extract_first_json_object,
            # _record_message_usage, _extract_final_text_from_message
            msg = gateway.create_message(
                model=gateway.model_for("default"),
                max_tokens=2500,
                temperature=0.2,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            _record_message_usage(msg)
            text = _extract_final_text_from_message(msg)
            try:
                pm = json.loads(text)
            except json.JSONDecodeError:
                pm = _extract_first_json_object(text)
            
            if isinstance(pm, dict) and isinstance(pm.get("steps"), list):
                if archetype == "advisory_pov" and is_meta_process_model(pm):
                    retry_user = (
                        user
                        + "\n\nCORRECTION: your previous model described document production. "
                        "Re-extract using only the client's operational domain process stages."
                    )
                    try:
                        corrected = _shared.claude_generate_json(
                            system=system, user=retry_user, temperature=0.2, max_tokens=2500
                        )
                        if isinstance(corrected, dict) and isinstance(corrected.get("steps"), list):
                            pm = corrected
                    except Exception:  # noqa: BLE001, S110 — keep first pass
                        pass
                if is_meta_process_model(pm):
                    meta = pm.get("metadata") if isinstance(pm.get("metadata"), dict) else {}
                    meta["meta_process_suspect"] = "true"
                    pm["metadata"] = meta
                state["process_model"] = pm  # type: ignore[assignment]
                return state
        except Exception:  # noqa: BLE001, S110 — fallback
            pass

    pm = extract_process_model(raw, ctx)
    if is_meta_process_model(pm):
        meta = pm.get("metadata") if isinstance(pm.get("metadata"), dict) else {}
        meta["meta_process_suspect"] = "true"
        pm["metadata"] = meta
    state["process_model"] = pm
    return state
