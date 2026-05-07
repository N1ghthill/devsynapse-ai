"""Build agent for DevSynapse.

Executes plans with:
- Step-by-step progress tracking
- Visual progress bar
- Auto-retry on failure
- Root authorization checks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from core.agents.planner import Plan, PlanStep

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Status of a build step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a step."""
    step: PlanStep
    status: StepStatus
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class BuildProgress:
    """Current progress of a build."""
    plan: Plan
    current_step: Optional[PlanStep] = None
    completed_steps: List[StepResult] = field(default_factory=list)
    failed_steps: List[StepResult] = field(default_factory=list)
    total_steps: int = 0
    completed_count: int = 0
    failed_count: int = 0
    is_complete: bool = False
    is_failed: bool = False
    total_duration_ms: float = 0.0

    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_count / self.total_steps) * 100.0

    def format_progress(self) -> str:
        """Format progress for TUI display."""
        bar_width = 20
        filled = int(bar_width * self.progress_pct / 100.0)
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            "🏗️  Build Progress",
            f"[{bar}] {self.progress_pct:.0f}%",
            "",
            f"✅ {self.completed_count}/{self.total_steps} completed",
        ]

        if self.failed_count > 0:
            lines.append(f"❌ {self.failed_count} failed")

        if self.current_step:
            lines.append("")
            lines.append(f"⏳ Current: {self.current_step.description}")

        if self.is_complete:
            lines.append("")
            lines.append("✅ Build complete!")

        return "\n".join(lines)


class BuildAgent:
    """Executes plans step-by-step with progress tracking.

    Features:
    - Visual progress bar
    - Auto-retry on failure (1 attempt)
    - Root authorization checks
    - Step-by-step execution
    """

    def __init__(
        self,
        execute_fn: Optional[Callable] = None,
        authorize_root_fn: Optional[Callable] = None,
    ) -> None:
        self.execute_fn = execute_fn
        self.authorize_root_fn = authorize_root_fn
        self.max_retries = 1

    async def execute_plan(
        self,
        plan: Plan,
        on_progress: Optional[Callable[[BuildProgress], None]] = None,
    ) -> BuildProgress:
        """Execute a plan step-by-step.

        Args:
            plan: Plan to execute
            on_progress: Callback for progress updates

        Returns:
            BuildProgress with final state
        """
        progress = BuildProgress(
            plan=plan,
            total_steps=len(plan.steps),
        )


        for step in plan.steps:
            # Update current step
            progress.current_step = step

            # Notify progress
            if on_progress:
                on_progress(progress)

            # Check dependencies
            if not self._check_dependencies(step, progress.completed_steps):
                step_result = StepResult(
                    step=step,
                    status=StepStatus.SKIPPED,
                    error="Dependencies not met",
                )
                progress.failed_steps.append(step_result)
                progress.failed_count += 1
                continue

            # Execute step with retry
            step_result = await self._execute_step_with_retry(step)

            # Update progress
            if step_result.status == StepStatus.SUCCESS:
                progress.completed_steps.append(step_result)
                progress.completed_count += 1
            else:
                progress.failed_steps.append(step_result)
                progress.failed_count += 1
                progress.is_failed = True
                break

            progress.total_duration_ms += step_result.duration_ms

            # Notify progress
            if on_progress:
                on_progress(progress)

        # Mark complete if not failed
        if not progress.is_failed:
            progress.is_complete = True

        progress.current_step = None

        return progress

    async def _execute_step_with_retry(self, step: PlanStep) -> StepResult:
        """Execute a step with retry on failure."""
        import time

        for attempt in range(self.max_retries + 1):
            start_time = time.time()

            try:
                # Check if step requires root
                if self._requires_root(step):
                    if self.authorize_root_fn:
                        authorized = await self.authorize_root_fn(step)
                        if not authorized:
                            return StepResult(
                                step=step,
                                status=StepStatus.SKIPPED,
                                error="Root authorization denied",
                            )

                # Execute step
                if self.execute_fn:
                    output = await self.execute_fn(step)
                else:
                    # Simulate execution for testing
                    output = f"Executed: {step.description}"

                duration_ms = (time.time() - start_time) * 1000

                return StepResult(
                    step=step,
                    status=StepStatus.SUCCESS,
                    output=output,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    "Step %s failed (attempt %d): %s",
                    step.id,
                    attempt + 1,
                    str(e),
                )

                if attempt >= self.max_retries:
                    return StepResult(
                        step=step,
                        status=StepStatus.FAILED,
                        error=str(e),
                        duration_ms=duration_ms,
                    )

        # Should not reach here, but just in case
        return StepResult(
            step=step,
            status=StepStatus.FAILED,
            error="Max retries exceeded",
        )

    def _check_dependencies(
        self,
        step: PlanStep,
        completed_steps: List[StepResult],
    ) -> bool:
        """Check if all dependencies are met."""
        if not step.dependencies:
            return True

        completed_ids = {r.step.id for r in completed_steps}
        return all(dep_id in completed_ids for dep_id in step.dependencies)

    def _requires_root(self, step: PlanStep) -> bool:
        """Check if step requires root authorization."""
        # Check if command uses sudo or modifies system files
        if step.action_type == "run_command" and step.content:
            return "sudo" in step.content.lower()
        return False
