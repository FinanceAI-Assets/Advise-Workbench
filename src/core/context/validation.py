"""Context Validation: Check for wiki/LP conflicts and freshness."""

import logging
from typing import Any
from datetime import datetime, timedelta

_LOG = logging.getLogger(__name__)


class ContextValidator:
    """Validates project context for wiki/LP conflicts and staleness."""

    def __init__(
        self,
        wiki_context: dict[str, Any],
        lp_context: dict[str, Any],
        instruction: str,
        wiki_refs: list[dict] | None = None,
    ):
        """
        Args:
            wiki_context: Wiki-sourced context (client, strategy, etc.)
            lp_context: Leading practice context (best practices, schemas)
            instruction: User's request/instruction
            wiki_refs: Wiki page metadata with timestamps
        """
        self.wiki_context = wiki_context or {}
        self.lp_context = lp_context or {}
        self.instruction = instruction
        self.wiki_refs = wiki_refs or []

    def detect_conflicts(self) -> dict[str, Any]:
        """Detect conflicts between wiki and LP context.

        Returns:
            {
                "has_conflicts": bool,
                "conflicts": [...],
                "severity": "high|medium|low",
                "needs_clarification": bool
            }
        """
        conflicts = []

        # Check for common conflict patterns
        wiki_text = str(self.wiki_context).lower() if self.wiki_context else ""
        lp_text = str(self.lp_context).lower() if self.lp_context else ""

        # Pattern 1: Old vs new client info
        if "client" in wiki_text and "client" in lp_text:
            wiki_has_year = any(str(year) in wiki_text for year in range(2020, 2023))
            if wiki_has_year and ("current" in lp_text or "2024" in lp_text):
                conflicts.append({
                    "field": "client_information",
                    "wiki_indicator": "Older client reference found",
                    "lp_indicator": "Uses current company profiles",
                    "severity": "high",
                    "description": "Wiki may reference outdated client information"
                })

        # Pattern 2: Strategy/focus mismatch
        wiki_cost_focus = any(word in wiki_text for word in ["cost", "reduction", "efficiency"])
        lp_growth_focus = any(word in lp_text for word in ["growth", "innovation", "expansion"])

        if wiki_cost_focus and lp_growth_focus:
            conflicts.append({
                "field": "strategic_focus",
                "wiki_value": "Cost/efficiency focus",
                "lp_value": "Growth/innovation focus",
                "severity": "high",
                "description": "Wiki and best practice suggest different strategic directions"
            })

        # Pattern 3: Timeline/planning mismatch - ONLY flag if there's a REAL conflict
        # (e.g., wiki says "annual" but LP says "monthly", not just presence of timeline words)
        wiki_annual = "annual" in wiki_text or "yearly" in wiki_text
        wiki_monthly = "monthly" in wiki_text
        wiki_quarterly = "quarterly" in wiki_text or "q1" in wiki_text or "q2" in wiki_text

        lp_annual = "annual" in lp_text or "yearly" in lp_text
        lp_monthly = "monthly" in lp_text
        lp_quarterly = "quarterly" in lp_text or "q1" in lp_text or "q2" in lp_text

        # Only flag if there's actual contradiction (e.g., wiki says annual but LP says monthly)
        if (wiki_annual and (lp_monthly or lp_quarterly)) or (wiki_monthly and lp_annual) or (wiki_quarterly and lp_monthly and not wiki_monthly):
            conflicts.append({
                "field": "planning_cadence",
                "wiki_indicator": "Custom timeline found",
                "lp_indicator": "Different planning recommended",
                "severity": "medium",
                "description": "Wiki and best practice use different planning cycles"
            })

        # Only ask for clarification on HIGH severity conflicts, not all conflicts
        has_high_severity = any(c.get("severity") == "high" for c in conflicts)

        return {
            "has_conflicts": len(conflicts) > 0,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "severity": self._calculate_severity(conflicts),
            "needs_clarification": has_high_severity,
            "recommendation": "ask_user" if has_high_severity else "continue"
        }

    def check_freshness(self) -> dict[str, Any]:
        """Check if context sources are recent and reliable.

        Returns:
            {
                "is_fresh": bool,
                "freshness_issues": [...],
                "overall_confidence": 0.0-1.0,
                "needs_clarification": bool
            }
        """
        issues = []
        confidence = 1.0

        # Check wiki page freshness
        for ref in self.wiki_refs:
            if not isinstance(ref, dict):
                continue

            last_updated = ref.get("last_updated")
            if isinstance(last_updated, str):
                try:
                    last_updated = datetime.fromisoformat(last_updated)
                except (ValueError, TypeError):
                    last_updated = None

            if last_updated and isinstance(last_updated, datetime):
                age_days = (datetime.now() - last_updated).days
                severity = "low"

                if age_days > 180:
                    severity = "high"
                    confidence -= 0.25
                elif age_days > 90:
                    severity = "medium"
                    confidence -= 0.15
                elif age_days > 30:
                    severity = "low"
                    confidence -= 0.05

                # Only flag as an issue if truly stale (>90 days)
                if age_days > 90:
                    issues.append({
                        "source": ref.get("title", "Unknown wiki page"),
                        "last_updated": last_updated.isoformat(),
                        "age_days": age_days,
                        "severity": severity,
                        "description": f"Wiki page not updated for {age_days} days"
                    })

        return {
            "is_fresh": len(issues) == 0,
            "freshness_issues": issues,
            "issue_count": len(issues),
            "overall_confidence": max(0.0, confidence),
            "needs_clarification": len(issues) > 0 and any(
                i["severity"] == "high" for i in issues
            ),
            "recommendation": "ask_user" if issues and any(i["severity"] == "high" for i in issues) else "continue"
        }

    def validate_all(self) -> dict[str, Any]:
        """Run all validations and return combined report.

        Returns combined conflict and freshness report.
        """
        conflicts_report = self.detect_conflicts()
        freshness_report = self.check_freshness()

        # Combine reports
        has_issues = conflicts_report["has_conflicts"] or freshness_report["needs_clarification"]
        overall_confidence = freshness_report["overall_confidence"]
        # Only ask for clarification on HIGH severity conflicts or freshness issues, not all conflicts
        needs_clarification = conflicts_report["needs_clarification"] or freshness_report["needs_clarification"]

        return {
            "has_issues": has_issues,
            "conflicts": conflicts_report,
            "freshness": freshness_report,
            "overall_confidence": overall_confidence,
            "needs_clarification": needs_clarification,
            "clarification_items": [
                {
                    "type": "conflict",
                    "item": c
                } for c in conflicts_report["conflicts"]
            ] + [
                {
                    "type": "freshness",
                    "item": f
                } for f in freshness_report["freshness_issues"]
            ],
            "recommendation": "ask_user" if has_issues else "continue"
        }

    @staticmethod
    def _calculate_severity(conflicts: list[dict]) -> str:
        """Calculate overall severity from conflict list."""
        if not conflicts:
            return "none"
        if any(c.get("severity") == "high" for c in conflicts):
            return "high"
        if any(c.get("severity") == "medium" for c in conflicts):
            return "medium"
        return "low"
