"""
LLM routing and cost-efficiency helpers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

SIMPLE_KEYWORDS = (
    "o que e",
    "o que é",
    "explique",
    "explica",
    "conceito",
    "como instalo",
    "como instalar",
    "resuma",
    "resumo",
)

MEDIUM_KEYWORDS = (
    "crud",
    "boilerplate",
    "template",
    "debug",
    "erro",
    "import",
    "teste",
    "pytest",
    "eslint",
    "ajuste",
    "melhoria",
)

COMPLEX_KEYWORDS = (
    "arquitetura",
    "architecture",
    "multi-arquivo",
    "multi arquivo",
    "race condition",
    "concorrencia",
    "concorrência",
    "assíncrono",
    "assincrono",
    "refatoração grande",
    "refatoracao grande",
    "migration",
    "migração",
    "migracao",
    "schema",
    "segurança",
    "security",
    "autorização",
    "authorization",
    "autenticação",
    "authentication",
    "roteamento",
    "routing",
    "cache",
    "updater",
)

UPGRADE_KEYWORDS = (
    "resposta ruim",
    "nao gostei",
    "não gostei",
    "tenta de novo",
    "refaz",
    "melhore a resposta",
    "melhorar a resposta",
    "mais profundo",
)


@dataclass(frozen=True)
class ModelRoute:
    """Decision produced by the model router for a single LLM request."""

    model: str
    complexity: str
    reason: str
    task_type: str = "general"
    task_signature: str = ""
    fallback_model: Optional[str] = None
    budget_mode: str = "normal"
    learned_preference: Optional[str] = None
    learned_confidence: float = 0.0


@dataclass(frozen=True)
class TaskProfile:
    """Stable task description used for routing and learning."""

    task_type: str
    complexity: str
    reason: str
    signature: str


class ModelRouter:
    """Route requests to Flash or Pro with conservative heuristics."""

    def __init__(
        self,
        flash_model: str,
        pro_model: str,
        default_model: str,
        routing_enabled: bool = True,
        auto_economy_enabled: bool = True,
    ):
        self.flash_model = flash_model
        self.pro_model = pro_model
        self.default_model = default_model
        self.routing_enabled = routing_enabled
        self.auto_economy_enabled = auto_economy_enabled

    def select_model(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        budget_status: Optional[Dict[str, Any]] = None,
        learned_policy: Optional[Dict[str, Any]] = None,
    ) -> ModelRoute:
        profile = build_task_profile(user_message, context=context)
        budget_level = self._budget_level(budget_status)
        if self.auto_economy_enabled and budget_level == "critical":
            return ModelRoute(
                model=self.flash_model,
                complexity="economy",
                reason="critical_budget",
                task_type=profile.task_type,
                task_signature=profile.signature,
                fallback_model=None,
                budget_mode="economy",
            )

        if not self.routing_enabled:
            return ModelRoute(
                model=self.default_model,
                complexity="manual",
                reason="routing_disabled",
                task_type=profile.task_type,
                task_signature=profile.signature,
                fallback_model=self._fallback_for(self.default_model),
                budget_mode=budget_level,
            )

        learned_model = self._usable_learned_model(learned_policy)
        if learned_model:
            selected_model = learned_model
            reason = f"learned_preference:{learned_policy.get('learned_reason') or 'feedback'}"
        else:
            selected_model = self.pro_model if profile.complexity == "complex" else self.flash_model
            reason = profile.reason

        return ModelRoute(
            model=selected_model,
            complexity=profile.complexity,
            reason=reason,
            task_type=profile.task_type,
            task_signature=profile.signature,
            fallback_model=self._fallback_for(selected_model),
            budget_mode=budget_level,
            learned_preference=learned_model,
            learned_confidence=float((learned_policy or {}).get("confidence") or 0.0),
        )

    def _fallback_for(self, model: str) -> Optional[str]:
        if model == self.flash_model and self.pro_model != self.flash_model:
            return self.pro_model
        return None

    @staticmethod
    def _budget_level(budget_status: Optional[Dict[str, Any]]) -> str:
        if not budget_status:
            return "normal"
        status = str(budget_status.get("overall_status") or "normal")
        return status if status in {"disabled", "healthy", "warning", "critical"} else "normal"

    def _usable_learned_model(self, learned_policy: Optional[Dict[str, Any]]) -> Optional[str]:
        if not learned_policy:
            return None

        confidence = float(learned_policy.get("confidence") or 0.0)
        preferred_model = str(learned_policy.get("preferred_model") or "")
        if confidence < 0.65:
            return None
        if preferred_model in {self.flash_model, self.pro_model}:
            return preferred_model
        return None


def build_task_profile(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
) -> TaskProfile:
    complexity, reason = classify_task_complexity(user_message, context=context)
    return TaskProfile(
        task_type=classify_task_type(user_message),
        complexity=complexity,
        reason=reason,
        signature=semantic_task_signature(user_message),
    )


def classify_task_complexity(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
) -> tuple[str, str]:
    """Classify request complexity using deterministic, testable heuristics."""

    normalized = _normalize(user_message)
    if any(keyword in normalized for keyword in UPGRADE_KEYWORDS):
        return "complex", "user_requested_upgrade"

    if any(keyword in normalized for keyword in COMPLEX_KEYWORDS):
        return "complex", "complex_keyword"

    if _mentions_multiple_files(normalized):
        return "complex", "multiple_files"

    if len(user_message) > 900:
        return "complex", "long_request"

    history = (context or {}).get("conversation_history") or []
    if len(history) >= 8 and any(keyword in normalized for keyword in MEDIUM_KEYWORDS):
        return "complex", "long_conversation_debug"

    if "```" in user_message and len(user_message) > 400:
        return "medium", "code_block"

    if any(keyword in normalized for keyword in MEDIUM_KEYWORDS):
        return "medium", "medium_keyword"

    if any(keyword in normalized for keyword in SIMPLE_KEYWORDS):
        return "simple", "simple_keyword"

    if len(user_message) < 220:
        return "simple", "short_request"

    return "medium", "default_medium"


def cache_hit_rate_pct(usage: Dict[str, Any]) -> float:
    hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
    miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
    total = hit_tokens + miss_tokens
    if total <= 0:
        return 0.0
    return round((hit_tokens / total) * 100, 2)


def classify_task_type(user_message: str) -> str:
    normalized = _normalize(user_message)
    if any(keyword in normalized for keyword in ("arquitetura", "architecture", "design")):
        return "architecture"
    if any(keyword in normalized for keyword in ("debug", "erro", "traceback", "stack trace")):
        return "debug"
    if any(keyword in normalized for keyword in ("refator", "refactor", "reescrev")):
        return "refactor"
    if any(keyword in normalized for keyword in ("teste", "pytest", "eslint", "lint")):
        return "test"
    if any(keyword in normalized for keyword in ("crud", "boilerplate", "template")):
        return "boilerplate"
    if any(keyword in normalized for keyword in ("instal", "build", "release", "deploy")):
        return "operations"
    if any(keyword in normalized for keyword in ("o que é", "o que e", "explique", "conceito")):
        return "concept"
    return "general"


def semantic_task_signature(user_message: str) -> str:
    normalized = _normalize(user_message)
    normalized = re.sub(r"```.*?```", " <code> ", normalized, flags=re.DOTALL)
    normalized = re.sub(r"(/[\w.\-]+)+", " <path> ", normalized)
    normalized = re.sub(r"\b[\w.\-]+\\[\w.\-\\]+\b", " <path> ", normalized)
    normalized = re.sub(r"\b[0-9a-f]{8,}\b", " <hash> ", normalized)
    normalized = re.sub(r"\b\d+(\.\d+)?\b", " <num> ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    task_type = classify_task_type(user_message)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{task_type}:{digest}"


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _mentions_multiple_files(value: str) -> bool:
    file_markers = (
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".md",
        ".json",
        ".yaml",
        ".yml",
    )
    return sum(1 for marker in file_markers if marker in value) >= 2
