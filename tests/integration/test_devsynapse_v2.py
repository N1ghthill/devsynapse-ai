"""Integration tests for DevSynapse 2.0 features.

Tests the complete flow from intent detection to plan execution,
validating cost calculation, path resolution, and multi-model support.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core.agents.builder import BuildAgent
from core.agents.planner import Plan, PlanningAgent, PlanStep
from core.intent_detector import IntentDetector, IntentMode
from core.usage_tracker import UsageTracker


class TestIntentToBuildFlow:
    """Test complete flow from user intent to build execution."""

    def setup_method(self):
        self.detector = IntentDetector()
        self.planner = PlanningAgent()

    def test_detect_new_project_intent(self):
        """Test that 'create a project' is detected as planning mode."""
        result = self.detector.detect("Crie o projeto calc em ~/projects/calc")

        assert result.mode in [IntentMode.PLANNING, IntentMode.BUILD]
        assert result.target_path == "~/projects/calc"
        assert result.project_name == "calc"

    def test_detect_question_intent(self):
        """Test that questions are detected as chat mode."""
        result = self.detector.detect("O que é JWT?")

        assert result.mode == IntentMode.CHAT

    def test_detect_complex_task_intent(self):
        """Test that complex tasks are detected as planning mode."""
        result = self.detector.detect("Crie uma API REST completa com autenticação")

        assert result.mode == IntentMode.PLANNING

    def test_planner_creates_plan_from_intent(self):
        """Test that planner creates a plan from detected intent."""
        self.detector.detect("Crie uma calculadora em Python")

        plan = self.planner.create_plan(
            "Crie uma calculadora em Python",
            target_path="~/projects/calc",
            project_name="calc",
        )

        assert plan is not None
        assert len(plan.steps) >= 2
        assert plan.target_path == "~/projects/calc"
        assert plan.project_name == "calc"

    @pytest.mark.asyncio
    async def test_build_agent_executes_plan(self):
        """Test that build agent executes a plan successfully."""
        plan = Plan(
            id="test_plan",
            title="Test Plan",
            description="A test plan",
            steps=[
                PlanStep(
                    id="step_001",
                    description="Create file",
                    action_type="write_file",
                    target_path="/test/main.py",
                    estimated_tokens=100,
                    estimated_cost=0.0001,
                    success_criteria="File created",
                ),
            ],
            estimated_total_tokens=100,
            estimated_total_cost=0.0001,
        )

        async def mock_execute(step):
            return f"Executed: {step.description}"

        agent = BuildAgent(execute_fn=mock_execute)
        progress = await agent.execute_plan(plan)

        assert progress.is_complete
        assert progress.completed_count == 1
        assert progress.failed_count == 0
        assert progress.progress_pct == 100.0


class TestMultiModelCostCalculation:
    """Test cost calculation for multiple providers and models."""

    def setup_method(self):
        self.memory = Mock()
        self.memory.get_llm_model = Mock(return_value=None)
        self.tracker = UsageTracker(
            memory=self.memory,
            model_pricing_lookup=self.memory.get_llm_model,
        )

    def test_calculate_cost_with_fallback_pricing(self):
        """Test that cost is calculated using fallback pricing when catalog is unavailable."""
        usage = {
            "provider": "openai",
            "model": "gpt-4o",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        }

        result = self.tracker.enrich_usage_cost("openai", "gpt-4o", usage)

        assert result is not None
        assert result.get("estimated_cost_usd") is not None
        assert result["estimated_cost_usd"] > 0
        assert result["pricing_source"] == "fallback"

    def test_calculate_cost_for_deepseek(self):
        """Test cost calculation for DeepSeek models."""
        usage = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        }

        result = self.tracker.enrich_usage_cost("deepseek", "deepseek-chat", usage)

        assert result is not None
        assert result.get("estimated_cost_usd") is not None
        assert result["estimated_cost_usd"] > 0

    def test_calculate_cost_for_claude(self):
        """Test cost calculation for Claude models."""
        usage = {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        }

        result = self.tracker.enrich_usage_cost("anthropic", "claude-3-5-sonnet", usage)

        assert result is not None
        assert result.get("estimated_cost_usd") is not None
        assert result["estimated_cost_usd"] > 0

    def test_calculate_cost_for_kimi(self):
        """Test cost calculation for Kimi models."""
        usage = {
            "provider": "moonshot",
            "model": "kimi-k2",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        }

        result = self.tracker.enrich_usage_cost("moonshot", "kimi-k2", usage)

        assert result is not None
        assert result.get("estimated_cost_usd") is not None
        assert result["estimated_cost_usd"] > 0

    def test_merge_usage_preserves_cost(self):
        """Test that merging usage preserves cost information."""
        base = {
            "provider": "openai",
            "model": "gpt-4o",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "estimated_cost_usd": 0.005,
        }
        extra = {
            "provider": "openai",
            "model": "gpt-4o",
            "prompt_tokens": 500,
            "completion_tokens": 250,
            "total_tokens": 750,
            "estimated_cost_usd": 0.0025,
        }

        result = self.tracker.merge_usage(base, extra)

        assert result["prompt_tokens"] == 1500
        assert result["completion_tokens"] == 750
        assert result["total_tokens"] == 2250
        assert result["estimated_cost_usd"] == 0.0075


class TestPathResolverIntegration:
    """Test path resolution in realistic scenarios."""

    def setup_method(self):
        from core.project_path_resolver import ProjectPathResolver

        self.resolver = ProjectPathResolver(
            repos_root=Path.home() / "ruas" / "repositorios",
            workspace_root=Path.home() / "workspace",
            allowed_directories=[
                Path.home() / "ruas" / "repositorios",
                Path.home() / "workspace",
            ],
        )

    def test_resolve_exact_path_from_message(self):
        """Test that exact path is extracted from user message."""
        message = "Crie uma calculadora em ~/ruas/repositorios/calc_py"

        result = self.resolver.resolve_from_message(message)

        assert result.is_valid
        assert result.project_name == "calc_py"
        assert "calc_py" in str(result.absolute_path)

    def test_resolve_relative_path_from_message(self):
        """Test that relative path is resolved correctly."""
        message = "Crie projeto em ./meu-app"

        result = self.resolver.resolve_from_message(message)

        # Should resolve relative to current directory
        assert result.is_valid or result.project_name is not None

    def test_resolve_project_name_only(self):
        """Test that project name is extracted when no path is given."""
        message = "Crie o projeto minha-api"

        result = self.resolver.resolve_from_message(message)

        assert result.project_name == "minha-api"


class TestPlanAndBuildIntegration:
    """Test complete plan and build flow."""

    def setup_method(self):
        self.planner = PlanningAgent()

    @pytest.mark.asyncio
    async def test_full_plan_and_build_flow(self):
        """Test complete flow: intent -> plan -> build."""
        # 1. Detect intent
        detector = IntentDetector()
        detector.detect("Crie uma calculadora em Python")

        # 2. Create plan
        plan = self.planner.create_plan(
            "Crie uma calculadora em Python",
            target_path="~/projects/calc",
            project_name="calc",
        )

        assert plan is not None
        assert len(plan.steps) >= 2

        # 3. Execute build
        async def mock_execute(step):
            return f"Executed: {step.description}"

        builder = BuildAgent(execute_fn=mock_execute)
        progress = await builder.execute_plan(plan)

        assert progress.is_complete
        assert progress.completed_count == len(plan.steps)
        assert progress.failed_count == 0

    @pytest.mark.asyncio
    async def test_build_with_progress_tracking(self):
        """Test that build progress is tracked correctly."""
        plan = Plan(
            id="test_plan",
            title="Test Plan",
            description="A test plan",
            steps=[
                PlanStep(
                    id="step_001",
                    description="Step 1",
                    action_type="write_file",
                    estimated_tokens=100,
                    estimated_cost=0.0001,
                ),
                PlanStep(
                    id="step_002",
                    description="Step 2",
                    action_type="write_file",
                    estimated_tokens=100,
                    estimated_cost=0.0001,
                ),
                PlanStep(
                    id="step_003",
                    description="Step 3",
                    action_type="write_file",
                    estimated_tokens=100,
                    estimated_cost=0.0001,
                ),
            ],
            estimated_total_tokens=300,
            estimated_total_cost=0.0003,
        )

        progress_updates = []

        async def mock_execute(step):
            return f"Executed: {step.description}"

        def on_progress(progress):
            progress_updates.append(progress.progress_pct)

        builder = BuildAgent(execute_fn=mock_execute)
        await builder.execute_plan(plan, on_progress=on_progress)

        # Should have progress updates
        assert len(progress_updates) > 0
        assert progress_updates[-1] == 100.0
        assert progress_updates[0] < progress_updates[-1]


class TestTelemetryWithPlans:
    """Test telemetry calculation for plan-based billing."""

    def setup_method(self):
        self.memory = Mock()

    def test_plan_usage_calculation(self):
        """Test that plan-based usage is calculated correctly."""
        # Mock catalog entry for plan-based model
        self.memory.get_llm_model = Mock(return_value={
            "provider": "openrouter",
            "model_id": "gpt-4o",
            "billing_type": "plan",
            "plan_tokens_limit": 100000,
            "plan_start_date": "2024-01-01",
            "plan_reset_cycle": "monthly",
            "input_cost_per_token": 0.0000025,
            "output_cost_per_token": 0.00001,
        })

        tracker = UsageTracker(
            memory=self.memory,
            model_pricing_lookup=self.memory.get_llm_model,
        )

        usage = {
            "provider": "openrouter",
            "model": "gpt-4o",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        }

        result = tracker.enrich_usage_cost("openrouter", "gpt-4o", usage)

        assert result is not None
        assert result.get("billing_type") == "plan"
        assert result.get("plan_tokens_used") == 1500
        assert result.get("plan_tokens_limit") == 100000
        assert result.get("plan_pct_used") == 1.5
