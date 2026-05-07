"""Tests for core/agents/builder.py."""

import pytest

from core.agents.builder import BuildAgent, BuildProgress, StepStatus
from core.agents.planner import Plan, PlanStep


class TestBuildAgent:
    def setup_method(self):
        self.agent = BuildAgent()

    def _create_test_plan(self) -> Plan:
        """Create a simple test plan."""
        return Plan(
            id="test_plan",
            title="Test Plan",
            description="A test plan",
            steps=[
                PlanStep(
                    id="step_001",
                    description="Create directory",
                    action_type="create_dir",
                    target_path="/test",
                    estimated_tokens=100,
                    estimated_cost=0.0001,
                    success_criteria="Dir created",
                ),
                PlanStep(
                    id="step_002",
                    description="Write file",
                    action_type="write_file",
                    target_path="/test/main.py",
                    estimated_tokens=200,
                    estimated_cost=0.0002,
                    success_criteria="File written",
                ),
            ],
            estimated_total_tokens=300,
            estimated_total_cost=0.0003,
        )

    @pytest.mark.asyncio
    async def test_execute_plan_success(self):
        """Test successful plan execution."""
        plan = self._create_test_plan()

        # Mock execute function
        async def mock_execute(step):
            return f"Executed: {step.description}"

        agent = BuildAgent(execute_fn=mock_execute)
        progress = await agent.execute_plan(plan)

        assert progress.is_complete
        assert not progress.is_failed
        assert progress.completed_count == 2
        assert progress.failed_count == 0
        assert progress.progress_pct == 100.0

    @pytest.mark.asyncio
    async def test_execute_plan_failure(self):
        """Test plan execution with failure."""
        plan = self._create_test_plan()

        # Mock execute function that always fails on second step
        async def mock_execute(step):
            if step.id == "step_002":
                raise Exception("Step failed")
            return f"Executed: {step.description}"

        agent = BuildAgent(execute_fn=mock_execute, )
        agent.max_retries = 0  # Disable retries for this test
        progress = await agent.execute_plan(plan)

        assert not progress.is_complete
        assert progress.is_failed
        assert progress.completed_count == 1
        assert progress.failed_count == 1

    @pytest.mark.asyncio
    async def test_execute_plan_with_progress_callback(self):
        """Test progress callback is called."""
        plan = self._create_test_plan()
        progress_updates = []

        async def mock_execute(step):
            return f"Executed: {step.description}"

        def on_progress(progress):
            progress_updates.append(progress.progress_pct)

        agent = BuildAgent(execute_fn=mock_execute)
        await agent.execute_plan(plan, on_progress=on_progress)

        # Should have progress updates
        assert len(progress_updates) > 0
        assert progress_updates[-1] == 100.0

    def test_build_progress_format(self):
        """Test progress formatting."""
        plan = self._create_test_plan()
        progress = BuildProgress(
            plan=plan,
            total_steps=2,
            completed_count=1,
        )

        formatted = progress.format_progress()

        assert "🏗️" in formatted
        assert "50%" in formatted
        assert "✅ 1/2" in formatted

    def test_build_progress_complete(self):
        """Test complete progress formatting."""
        plan = self._create_test_plan()
        progress = BuildProgress(
            plan=plan,
            total_steps=2,
            completed_count=2,
            is_complete=True,
        )

        formatted = progress.format_progress()

        assert "100%" in formatted
        assert "Build complete" in formatted

    def test_build_progress_with_failure(self):
        """Test failure progress formatting."""
        plan = self._create_test_plan()
        progress = BuildProgress(
            plan=plan,
            total_steps=2,
            completed_count=1,
            failed_count=1,
            is_failed=True,
        )

        formatted = progress.format_progress()

        assert "❌ 1 failed" in formatted

    def test_check_dependencies_met(self):
        """Test dependency checking when met."""
        from core.agents.builder import StepResult

        step = PlanStep(
            id="step_003",
            description="Test",
            action_type="write_file",
            dependencies=["step_001", "step_002"],
        )

        completed = [
            StepResult(
                step=PlanStep(id="step_001", description="", action_type=""),
                status=StepStatus.SUCCESS,
            ),
            StepResult(
                step=PlanStep(id="step_002", description="", action_type=""),
                status=StepStatus.SUCCESS,
            ),
        ]

        assert self.agent._check_dependencies(step, completed)

    def test_check_dependencies_not_met(self):
        """Test dependency checking when not met."""
        from core.agents.builder import StepResult

        step = PlanStep(
            id="step_003",
            description="Test",
            action_type="write_file",
            dependencies=["step_001", "step_002"],
        )

        completed = [
            StepResult(
                step=PlanStep(id="step_001", description="", action_type=""),
                status=StepStatus.SUCCESS,
            ),
        ]

        assert not self.agent._check_dependencies(step, completed)

    def test_requires_root_detection(self):
        """Test root requirement detection."""
        step_with_sudo = PlanStep(
            id="step_001",
            description="Install package",
            action_type="run_command",
            content="sudo apt install python3",
        )

        step_without_sudo = PlanStep(
            id="step_002",
            description="Write file",
            action_type="write_file",
        )

        assert self.agent._requires_root(step_with_sudo)
        assert not self.agent._requires_root(step_without_sudo)
