"""Tests for token-aware context budgeting (Workstream A)."""

import pytest
from unittest.mock import patch, MagicMock

from src.llm.context_budget import (
    count_tokens,
    context_window,
    MemoryBudgetPlan,
    plan_memory_budget,
    plan_from_settings,
    estimate_plan,
    DEFAULT_CONTEXT_WINDOW,
)
from src.core.config import settings


class TestCountTokens:
    """Tests for exact/estimated token counting."""

    def test_empty_text_returns_zero_exact(self) -> None:
        tokens, exact = count_tokens("", "model")
        assert tokens == 0
        assert exact is True

    def test_falls_back_to_estimate_when_exact_disabled(self) -> None:
        with patch("src.core.config.settings.memory_token_count_exact", False):
            tokens, exact = count_tokens("hello world", "claude-opus")
            assert tokens > 0
            assert exact is False

    def test_falls_back_to_estimate_on_api_error(self) -> None:
        with patch("src.llm.context_budget.settings.memory_token_count_exact", True):
            with patch("src.llm.gateway.get_provider") as mock_get_provider:
                mock_provider = MagicMock()
                mock_provider.name = "anthropic"
                mock_provider.client.messages.count_tokens.side_effect = Exception("API error")
                mock_get_provider.return_value = mock_provider

                tokens, exact = count_tokens("hello world", "claude-opus")
                assert tokens > 0
                assert exact is False

    def test_non_anthropic_provider_uses_estimate(self) -> None:
        with patch("src.llm.gateway.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.name = "openai"
            mock_get_provider.return_value = mock_provider

            tokens, exact = count_tokens("hello world", "gpt-4")
            assert tokens > 0
            assert exact is False


class TestContextWindow:
    """Tests for model context window retrieval."""

    def test_returns_fallback_for_empty_model(self) -> None:
        window = context_window("")
        assert window == DEFAULT_CONTEXT_WINDOW

    def test_returns_fallback_for_non_anthropic(self) -> None:
        with patch("src.llm.gateway.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.name = "openai"
            mock_get_provider.return_value = mock_provider

            window = context_window("gpt-4")
            assert window == DEFAULT_CONTEXT_WINDOW

    def test_returns_fallback_on_api_error(self) -> None:
        with patch("src.llm.gateway.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.name = "anthropic"
            mock_provider.client.models.retrieve.side_effect = Exception("API error")
            mock_get_provider.return_value = mock_provider

            window = context_window("claude-opus")
            assert window == DEFAULT_CONTEXT_WINDOW


class TestMemoryBudgetPlan:
    """Tests for MemoryBudgetPlan dataclass."""

    def test_context_tokens_property(self) -> None:
        plan = MemoryBudgetPlan(
            model="claude-opus",
            window=200000,
            total=32000,
            system=4000,
            memory=11200,
            retrieved=11200,
            history=5600,
            system_counted=True,
        )
        assert plan.context_tokens == 11200 + 11200 + 5600

    def test_as_dict(self) -> None:
        plan = MemoryBudgetPlan(
            model="claude-opus",
            window=200000,
            total=32000,
            system=4000,
            memory=11200,
            retrieved=11200,
            history=5600,
            system_counted=True,
        )
        d = plan.as_dict()
        assert d["model"] == "claude-opus"
        assert d["total"] == 32000
        assert d["context_tokens"] == 28000


class TestPlanMemoryBudget:
    """Tests for budget planning algorithm."""

    def test_budget_sum_equals_total(self) -> None:
        plan = plan_memory_budget(
            model="",
            token_budget=32000,
            output_reserve_tokens=4096,
            system_reserve_tokens=4000,
        )
        # total = min(32000, window - output_reserve - 5% window)
        # Since window=200_000 for empty model, total should be ~32000 - 4096 - 5% = ~25904
        # system = min(total, max(4000, 0)) = 4000
        # remainder = total - 4000
        # memory = remainder * 0.40, retrieved * 0.40, history gets remainder
        assert plan.system <= plan.total
        assert plan.memory + plan.retrieved + plan.history == plan.total - plan.system

    def test_system_reserve_honored(self) -> None:
        plan = plan_memory_budget(
            model="",
            token_budget=32000,
            output_reserve_tokens=4096,
            system_reserve_tokens=4000,
        )
        assert plan.system >= 4000

    def test_shares_normalized_correctly(self) -> None:
        plan = plan_memory_budget(
            model="",
            token_budget=32000,
            output_reserve_tokens=4096,
            system_reserve_tokens=0,
            shares=(0.25, 0.50, 0.25),
        )
        total_context = plan.memory + plan.retrieved + plan.history
        memory_ratio = plan.memory / max(total_context, 1)
        retrieved_ratio = plan.retrieved / max(total_context, 1)
        # Ratios should be close to the specified shares
        assert abs(memory_ratio - 0.25) < 0.05
        assert abs(retrieved_ratio - 0.50) < 0.05

    def test_history_gets_rounding_remainder(self) -> None:
        plan = plan_memory_budget(
            model="",
            token_budget=1000,
            output_reserve_tokens=0,
            system_reserve_tokens=0,
            shares=(0.33, 0.33, 0.34),
        )
        context_total = plan.memory + plan.retrieved + plan.history
        system_total = plan.system
        # Sum should equal the actual total
        assert context_total + system_total == plan.total


class TestPlanFromSettings:
    """Tests for creating plans from settings."""

    def test_uses_planning_tier_when_tiering_enabled(self) -> None:
        with patch("src.core.config.settings.model_tiering_enabled", True):
            with patch("src.llm.gateway.model_for") as mock_model_for:
                mock_model_for.return_value = "claude-opus-4-8"
                plan = plan_from_settings(settings)
                mock_model_for.assert_called_with("planning")
                assert plan.model == "claude-opus-4-8"

    def test_uses_default_tier_when_tiering_disabled(self) -> None:
        with patch("src.core.config.settings.model_tiering_enabled", False):
            with patch("src.llm.gateway.model_for") as mock_model_for:
                mock_model_for.return_value = "claude-haiku"
                plan = plan_from_settings(settings)
                mock_model_for.assert_called_with("default")
                assert plan.model == "claude-haiku"

    def test_reads_token_budget_settings(self) -> None:
        with patch("src.llm.gateway.model_for") as mock_model_for:
            mock_model_for.return_value = "claude-opus"
            plan = plan_from_settings(
                settings,
                system_text="",
                tier=None,
            )
            assert plan.total > 0
            assert plan.system >= 0
            assert plan.memory >= 0
            assert plan.retrieved >= 0
            assert plan.history >= 0


class TestEstimatePlan:
    """Tests for estimate-only (offline) plans."""

    def test_estimate_plan_no_api_calls(self) -> None:
        plan = estimate_plan(32000)
        assert plan.model == ""
        assert plan.system == 4000
        assert plan.total > 0
        assert plan.context_tokens > 0
        # Should be reproducible
        plan2 = estimate_plan(32000)
        assert plan.memory == plan2.memory
        assert plan.retrieved == plan2.retrieved

    def test_estimate_plan_respects_budget(self) -> None:
        plan = estimate_plan(10000)
        assert plan.total <= 10000
        assert plan.context_tokens <= plan.total
