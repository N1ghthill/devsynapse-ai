"""Tests for core/agents/planner.py."""

from core.agents.planner import PlanningAgent, PlanStep


class TestPlanningAgent:
    def setup_method(self):
        self.agent = PlanningAgent()

    def test_create_new_api_project_plan(self):
        plan = self.agent.create_plan(
            "Crie uma API REST completa",
            target_path="~/projects/api",
            project_name="my-api",
        )

        assert plan.title == "Novo Projeto API"
        assert len(plan.steps) >= 3
        assert plan.target_path == "~/projects/api"
        assert plan.project_name == "my-api"
        assert plan.estimated_total_tokens > 0
        assert plan.estimated_total_cost > 0

    def test_create_calculator_plan(self):
        plan = self.agent.create_plan(
            "Crie uma calculadora em Python",
            target_path="~/projects/calc",
            project_name="calc",
        )

        assert "Calculadora" in plan.title
        assert len(plan.steps) >= 2
        assert any("calc.py" in (s.target_path or "") for s in plan.steps)

    def test_create_refactor_plan(self):
        plan = self.agent.create_plan(
            "Refatore o módulo de pagamentos",
            target_path="~/projects/app",
            project_name="app",
        )

        assert "Refatoração" in plan.title
        assert len(plan.steps) >= 2
        assert any(s.action_type == "edit_file" for s in plan.steps)

    def test_create_feature_plan(self):
        plan = self.agent.create_plan(
            "Adicione autenticação JWT",
            target_path="~/projects/app",
            project_name="app",
        )

        assert "Funcionalidade" in plan.title
        assert len(plan.steps) >= 2

    def test_plan_step_ids_are_unique(self):
        plan = self.agent.create_plan("Crie uma API", target_path="~/api")

        step_ids = [s.id for s in plan.steps]
        assert len(step_ids) == len(set(step_ids)), "Step IDs should be unique"

    def test_plan_format_for_display(self):
        plan = self.agent.create_plan(
            "Crie uma calculadora",
            target_path="~/calc",
        )

        display = plan.format_for_display()

        assert "📋" in display
        assert "💰" in display
        assert "🔢" in display
        assert "▶️" in display

    def test_plan_to_dict(self):
        plan = self.agent.create_plan("Crie projeto", target_path="~/proj")

        plan_dict = plan.to_dict()

        assert "id" in plan_dict
        assert "title" in plan_dict
        assert "steps" in plan_dict
        assert isinstance(plan_dict["steps"], list)

    def test_plan_step_has_all_fields(self):
        step = PlanStep(
            id="step_001",
            description="Test step",
            action_type="write_file",
            target_path="/test.py",
            estimated_tokens=100,
            estimated_cost=0.0001,
            success_criteria="File created",
        )

        assert step.id == "step_001"
        assert step.description == "Test step"
        assert step.action_type == "write_file"
        assert step.target_path == "/test.py"
        assert step.estimated_tokens == 100
        assert step.estimated_cost == 0.0001
        assert step.success_criteria == "File created"

    def test_empty_request_creates_generic_plan(self):
        plan = self.agent.create_plan("ajuda")

        assert plan is not None
        assert len(plan.steps) >= 1
