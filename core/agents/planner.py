"""Planning agent for DevSynapse.

Creates structured plans with:
- Step-by-step breakdown
- Cost estimates
- File operations
- Success criteria
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: str
    description: str
    action_type: str  # "create_dir", "write_file", "edit_file", "run_command", "test"
    target_path: Optional[str] = None
    content: Optional[str] = None
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    success_criteria: str = ""


@dataclass
class Plan:
    """A structured plan for executing a task."""
    id: str
    title: str
    description: str
    steps: List[PlanStep]
    estimated_total_tokens: int = 0
    estimated_total_cost: float = 0.0
    target_path: Optional[str] = None
    project_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "steps": [
                {
                    "id": step.id,
                    "description": step.description,
                    "action_type": step.action_type,
                    "target_path": step.target_path,
                    "estimated_tokens": step.estimated_tokens,
                    "estimated_cost": step.estimated_cost,
                }
                for step in self.steps
            ],
            "estimated_total_tokens": self.estimated_total_tokens,
            "estimated_total_cost": self.estimated_total_cost,
            "target_path": self.target_path,
            "project_name": self.project_name,
        }

    def format_for_display(self) -> str:
        """Format plan for TUI display."""
        lines = [
            f"📋 {self.title}",
            f"{'=' * 40}",
            f"📝 {self.description}",
            "",
            f"📁 Target: {self.target_path or 'N/A'}",
            f"💰 Estimated cost: ${self.estimated_total_cost:.4f}",
            f"🔢 Estimated tokens: {self.estimated_total_tokens:,}",
            "",
            "📋 Steps:",
        ]

        for i, step in enumerate(self.steps, 1):
            status_icon = "⏸️"
            lines.append(f"  {i}. {status_icon} {step.description}")
            if step.target_path:
                lines.append(f"     📁 {step.target_path}")

        lines.append("")
        lines.append("[▶️ Executar] [✏️ Modificar] [❌ Cancelar]")

        return "\n".join(lines)


class PlanningAgent:
    """Creates structured plans for complex tasks.

    Analyzes user requests and breaks them down into executable steps
    with cost estimates and success criteria.
    """

    def __init__(self) -> None:
        self._step_counter = 0

    def create_plan(
        self,
        user_request: str,
        target_path: Optional[str] = None,
        project_name: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Plan:
        """Create a plan from user request.

        Args:
            user_request: What the user wants to accomplish
            target_path: Where to create/modify files
            project_name: Project context
            context: Additional context (existing files, etc.)

        Returns:
            Plan with steps, estimates, and success criteria
        """
        self._step_counter = 0

        # Analyze request type
        plan_type = self._analyze_request_type(user_request)

        # Create plan based on type
        if plan_type == "new_project":
            return self._create_new_project_plan(
                user_request, target_path, project_name
            )
        elif plan_type == "add_feature":
            return self._create_feature_plan(
                user_request, target_path, project_name, context
            )
        elif plan_type == "refactor":
            return self._create_refactor_plan(
                user_request, target_path, project_name, context
            )
        else:
            return self._create_generic_plan(
                user_request, target_path, project_name
            )

    def _analyze_request_type(self, request: str) -> str:
        """Analyze request to determine plan type."""
        request_lower = request.lower()

        # New project indicators
        if any(
            word in request_lower
            for word in ["crie um projeto", "crie uma api", "crie um sistema", "novo projeto", "crie uma calculadora"]
        ):
            return "new_project"

        # Feature addition indicators
        if any(
            word in request_lower
            for word in ["adicione", "implemente", "crie uma funcionalidade", "novo endpoint"]
        ):
            return "add_feature"

        # Refactoring indicators
        if any(
            word in request_lower
            for word in ["refatore", "melhore", "reestruture", "otimize"]
        ):
            return "refactor"

        return "generic"

    def _create_new_project_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
    ) -> Plan:
        """Create plan for a new project."""
        # Extract project type from request
        request_lower = request.lower()

        if "api" in request_lower or "rest" in request_lower:
            return self._create_api_project_plan(request, target_path, project_name)
        elif "calculadora" in request_lower or "calculator" in request_lower:
            return self._create_calculator_plan(request, target_path, project_name)
        else:
            return self._create_generic_project_plan(request, target_path, project_name)

    def _create_api_project_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
    ) -> Plan:
        """Create plan for an API project."""
        path = target_path or "./api-project"
        name = project_name or "api-project"

        steps = [
            PlanStep(
                id=self._next_step_id(),
                description="Criar estrutura de diretórios",
                action_type="create_dir",
                target_path=path,
                estimated_tokens=100,
                estimated_cost=0.0001,
                success_criteria="Diretórios criados",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar requirements.txt",
                action_type="write_file",
                target_path=f"{path}/requirements.txt",
                content="fastapi\nuvicorn\npydantic",
                estimated_tokens=150,
                estimated_cost=0.0002,
                success_criteria="requirements.txt criado",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar main.py com FastAPI app",
                action_type="write_file",
                target_path=f"{path}/main.py",
                estimated_tokens=500,
                estimated_cost=0.0005,
                success_criteria="main.py criado com app FastAPI",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar models.py",
                action_type="write_file",
                target_path=f"{path}/models.py",
                estimated_tokens=400,
                estimated_cost=0.0004,
                success_criteria="models.py criado",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar README.md",
                action_type="write_file",
                target_path=f"{path}/README.md",
                estimated_tokens=300,
                estimated_cost=0.0003,
                success_criteria="README.md criado",
            ),
        ]

        total_tokens = sum(s.estimated_tokens for s in steps)
        total_cost = sum(s.estimated_cost for s in steps)

        return Plan(
            id=f"plan_{self._step_counter}",
            title="Novo Projeto API",
            description=f"Criar API REST em {path}",
            steps=steps,
            estimated_total_tokens=total_tokens,
            estimated_total_cost=total_cost,
            target_path=path,
            project_name=name,
        )

    def _create_calculator_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
    ) -> Plan:
        """Create plan for a calculator project."""
        path = target_path or "./calculator"
        name = project_name or "calculator"

        steps = [
            PlanStep(
                id=self._next_step_id(),
                description="Criar diretório do projeto",
                action_type="create_dir",
                target_path=path,
                estimated_tokens=100,
                estimated_cost=0.0001,
                success_criteria="Diretório criado",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar calc.py com funções de cálculo",
                action_type="write_file",
                target_path=f"{path}/calc.py",
                estimated_tokens=400,
                estimated_cost=0.0004,
                success_criteria="calc.py criado com funções básicas",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar test_calc.py com testes",
                action_type="write_file",
                target_path=f"{path}/test_calc.py",
                estimated_tokens=350,
                estimated_cost=0.00035,
                success_criteria="test_calc.py criado",
            ),
        ]

        total_tokens = sum(s.estimated_tokens for s in steps)
        total_cost = sum(s.estimated_cost for s in steps)

        return Plan(
            id=f"plan_{self._step_counter}",
            title="Projeto Calculadora",
            description=f"Criar calculadora Python em {path}",
            steps=steps,
            estimated_total_tokens=total_tokens,
            estimated_total_cost=total_cost,
            target_path=path,
            project_name=name,
        )

    def _create_generic_project_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
    ) -> Plan:
        """Create generic project plan."""
        path = target_path or "./project"
        name = project_name or "project"

        steps = [
            PlanStep(
                id=self._next_step_id(),
                description="Criar estrutura inicial",
                action_type="create_dir",
                target_path=path,
                estimated_tokens=100,
                estimated_cost=0.0001,
                success_criteria="Estrutura criada",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Criar arquivo principal",
                action_type="write_file",
                target_path=f"{path}/main.py",
                estimated_tokens=300,
                estimated_cost=0.0003,
                success_criteria="main.py criado",
            ),
        ]

        total_tokens = sum(s.estimated_tokens for s in steps)
        total_cost = sum(s.estimated_cost for s in steps)

        return Plan(
            id=f"plan_{self._step_counter}",
            title="Novo Projeto",
            description=f"Criar projeto em {path}",
            steps=steps,
            estimated_total_tokens=total_tokens,
            estimated_total_cost=total_cost,
            target_path=path,
            project_name=name,
        )

    def _create_feature_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
        context: Optional[Dict],
    ) -> Plan:
        """Create plan for adding a feature."""
        path = target_path or "./project"

        steps = [
            PlanStep(
                id=self._next_step_id(),
                description="Analisar código existente",
                action_type="run_command",
                estimated_tokens=200,
                estimated_cost=0.0002,
                success_criteria="Código analisado",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Implementar nova funcionalidade",
                action_type="write_file",
                estimated_tokens=500,
                estimated_cost=0.0005,
                success_criteria="Funcionalidade implementada",
            ),
        ]

        total_tokens = sum(s.estimated_tokens for s in steps)
        total_cost = sum(s.estimated_cost for s in steps)

        return Plan(
            id=f"plan_{self._step_counter}",
            title="Nova Funcionalidade",
            description="Adicionar feature ao projeto",
            steps=steps,
            estimated_total_tokens=total_tokens,
            estimated_total_cost=total_cost,
            target_path=path,
            project_name=project_name,
        )

    def _create_refactor_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
        context: Optional[Dict],
    ) -> Plan:
        """Create plan for refactoring."""
        path = target_path or "./project"

        steps = [
            PlanStep(
                id=self._next_step_id(),
                description="Analisar código atual",
                action_type="run_command",
                estimated_tokens=300,
                estimated_cost=0.0003,
                success_criteria="Análise concluída",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Refatorar código",
                action_type="edit_file",
                estimated_tokens=600,
                estimated_cost=0.0006,
                success_criteria="Código refatorado",
            ),
            PlanStep(
                id=self._next_step_id(),
                description="Rodar testes para validar",
                action_type="run_command",
                estimated_tokens=200,
                estimated_cost=0.0002,
                success_criteria="Testes passando",
            ),
        ]

        total_tokens = sum(s.estimated_tokens for s in steps)
        total_cost = sum(s.estimated_cost for s in steps)

        return Plan(
            id=f"plan_{self._step_counter}",
            title="Refatoração",
            description=f"Refatorar código em {path}",
            steps=steps,
            estimated_total_tokens=total_tokens,
            estimated_total_cost=total_cost,
            target_path=path,
            project_name=project_name,
        )

    def _create_generic_plan(
        self,
        request: str,
        target_path: Optional[str],
        project_name: Optional[str],
    ) -> Plan:
        """Create generic plan for unknown request types."""
        path = target_path or "./project"

        steps = [
            PlanStep(
                id=self._next_step_id(),
                description="Executar solicitação",
                action_type="write_file",
                estimated_tokens=300,
                estimated_cost=0.0003,
                success_criteria="Tarefa concluída",
            ),
        ]

        return Plan(
            id=f"plan_{self._step_counter}",
            title="Plano Genérico",
            description=request[:100],
            steps=steps,
            estimated_total_tokens=300,
            estimated_total_cost=0.0003,
            target_path=path,
            project_name=project_name,
        )

    def _next_step_id(self) -> str:
        """Generate next step ID."""
        self._step_counter += 1
        return f"step_{self._step_counter:03d}"
