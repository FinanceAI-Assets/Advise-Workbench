"""Process extraction agent: turns the source documents into the process model."""

from __future__ import annotations

from src.prompts.prompt_hygiene import wrap_untrusted
from src.core.state import AdviseWorkbenchState
from src.agents.process_extraction import extract_process_model
from src.agents.specialists import _shared


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
        system = (
            "You are a process extraction engine. "
            "Your sole output is a single JSON object — no preamble, no explanation, no markdown fences. "
            "If any field has no data, use an empty array [] or empty string \"\", never null or omit the key. "
            "Step IDs must follow the pattern 's1', 's2', ..., 'sN' in order of appearance. "
            "Decision IDs must follow the pattern 'd1', 'd2', ..., 'dN'. "
            "Every step referenced in decisions.true_path or decisions.false_path must exist in steps[*].id. "
            "Every step referenced in swimlanes[role] must exist in steps[*].id."
        )
        user = (
            "Extract a structured process model from the instruction and context below.\n\n"
            "Return a JSON object with EXACTLY these top-level keys (no others):\n\n"
            "  process_name   string — the process title; infer from heading, first sentence, or topic if not explicit\n"
            "  roles          string[] — every distinct human role that performs a step; omit system names and tools\n"
            "  steps          ProcessStep[] — one entry per discrete action in execution order\n"
            "  decisions      DecisionBranch[] — one entry per conditional fork; empty [] if none\n"
            "  swimlanes      { [role: string]: string[] } — maps each role to its step IDs in order\n"
            "  metrics        MetricFact[] — every quantified fact in the text (time, count, %, currency, volume); "
            "empty [] if no numeric data present\n"
            "  metadata       { [key: string]: string } — any named attributes (e.g. 'frequency', 'owner', 'SLA') "
            "found in the text; empty {} if none\n\n"
            "ProcessStep schema:\n"
            "  id               string — 's1', 's2', ..., 'sN'\n"
            "  name             string — imperative verb phrase, ≤10 words (e.g. 'Collect KYC documents')\n"
            "  role             string — role from roles[]; 'TBD' if not specified\n"
            "  inputs           string[] — named artifacts or data consumed by this step; [] if none\n"
            "  outputs          string[] — named artifacts or data produced by this step; [] if none\n"
            "  tools            string[] — systems, apps, or tools used in this step; [] if none\n"
            "  duration_estimate string — e.g. '2 hours', '1 day'; \"\" if not specified\n"
            "  notes            string — any caveats, exceptions, or extra detail; \"\" if none\n\n"
            "DecisionBranch schema:\n"
            "  id         string — 'd1', 'd2', ...\n"
            "  condition  string — the yes/no question at the fork (e.g. 'Documents complete?')\n"
            "  true_path  string[] — step IDs taken when condition is true\n"
            "  false_path string[] — step IDs taken when condition is false\n\n"
            "MetricFact schema:\n"
            "  stat    string — the value/number (e.g. '12 days', '94%', 'INR 50,000', '3')\n"
            "  label   string — what it measures in 2–5 words (e.g. 'Invoice Cycle Time', 'Error Rate')\n"
            "  source  string — one of: 'client-provided data' | 'benchmark assumptions' | 'inferred from context'\n\n"
            "Edge-case rules:\n"
            "  - If no numbered or bulleted steps exist, infer steps from verbs in the text (minimum 1 step).\n"
            "  - If no roles are named, use ['Process Owner'] as the sole role and assign all steps to it.\n"
            "  - Do not invent steps that are not implied by the source text.\n\n"
        )
        if archetype == "advisory_pov":
            user += (
                "ADVISORY POV RULES:\n"
                "Extract the SUBJECT-DOMAIN business process (e.g. Record-to-Report: journals, "
                "intercompany, reconciliation, close, consolidation, reporting).\n"
                "Do NOT model the workflow of writing, designing, or producing this POV note/deck.\n"
                "Never include steps like 'develop POV document', 'create presentation', or tools "
                "such as PowerPoint/Word as process steps.\n"
                "If the source lacks operational detail, derive a standard industry-reference model "
                "and set metadata.grounding='illustrative'.\n\n"
            )
        user += (
            f"Instruction:\n{wrap_untrusted('user_instruction', str(raw))}\n\n"
            f"Context:\n{wrap_untrusted('assembled_context', str(ctx))}\n"
        )
        try:
            pm = _shared.claude_generate_json(system=system, user=user, temperature=0.2, max_tokens=2500)
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
