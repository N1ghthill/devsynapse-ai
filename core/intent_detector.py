"""Intent detection for DevSynapse 3-spectra system.

Classifies user messages into:
- CHAT: Conversational, questions, explanations
- PLANNING: Complex tasks that need analysis before execution
- BUILD: Simple tasks that can be executed directly
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class IntentMode(Enum):
    """The 3 spectra of DevSynapse."""
    CHAT = "chat"
    PLANNING = "planning"
    BUILD = "build"


@dataclass
class IntentResult:
    """Result of intent detection."""
    mode: IntentMode
    confidence: float  # 0.0 to 1.0
    reasoning: str
    target_path: Optional[str] = None
    project_name: Optional[str] = None


# Patterns for classification
CHAT_PATTERNS = [
    # Questions
    r"\b(o que|como|por que|quando|onde|qual|quem)\b",
    r"\b(what|how|why|when|where|which|who)\b",
    # Explanations
    r"\b(explica|explique|explicar|entenda|entender|compreenda)\b",
    r"\b(explain|understand|describe)\b",
    # Opinions/Advice
    r"\b(qual\s+(o|a)\s+melhor|qual\s+voc[eê]\s+(recomenda|sugere))\b",
    r"\b(what\s+do\s+you\s+(think|recommend|suggest))\b",
    # Greetings/Small talk
    r"^(oi|ol[aá]|hey|hello|bom\s+dia|boa\s+tarde|boa\s+noite)\b",
    r"\b(obrigad[oa]|valeu|thanks|thank\s+you)\b",
]

PLANNING_PATTERNS = [
    # Complex tasks
    r"\b(crie|criar|implemente|implementar|desenvolva|desenvolver)\b.*\b(sistema|api|aplica[cç][aã]o|projeto)\b",
    r"\b(create|implement|develop|build)\b.*\b(system|api|application|project)\b",
    # Architecture/Design
    r"\b(arquitetura|design|estrutura|planej[aee])\b",
    r"\b(architecture|design|structure|plan)\b",
    # Multi-file tasks
    r"\b(m[úu]ltiplos?\s+arquivos?|v[aá]rios?\s+arquivos?|v[aá]rias?\s+partes?)\b",
    r"\b(multiple\s+files|several\s+files)\b",
    # Refactoring
    r"\b(refator[aee]|reestrutur[aee]|melhor[eie]|refactor)\b",
    r"\b(refactor|restructure|improve)\b",
    # Full features
    r"\b(funcionalidade\s+completa|feature\s+completa|sistema\s+completo)\b",
    r"\b(full\s+feature|complete\s+system)\b",
    # Modules/components
    r"\b(m[óo]dulo|componente|servi[cç]o)\b",
    r"\b(module|component|service)\b",
]

BUILD_PATTERNS = [
    # Simple file creation
    r"\b(crie|criar|adicione|adicionar)\b.*\b(arquivo|file)\b",
    r"\b(create|add)\b.*\b(file)\b",
    # Simple commands
    r"\b(rode|rodar|execute|executar|teste|testar)\b",
    r"\b(run|execute|test)\b",
    # Specific file operations
    r"\b(leia|ler|abra|abrir|edite|editar|salve|salvar)\b",
    r"\b(read|open|edit|save)\b",
    # Small tasks
    r"\b(fun[cç][aã]o|m[eé]todo|classe)\b",
    r"\b(function|method|class)\b",
]


class IntentDetector:
    """Detects user intent and classifies into Chat, Planning, or Build mode.

    Uses pattern matching for fast classification with confidence scores.
    """

    def __init__(self) -> None:
        self._chat_patterns = [re.compile(p, re.IGNORECASE) for p in CHAT_PATTERNS]
        self._planning_patterns = [re.compile(p, re.IGNORECASE) for p in PLANNING_PATTERNS]
        self._build_patterns = [re.compile(p, re.IGNORECASE) for p in BUILD_PATTERNS]

    def detect(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> IntentResult:
        """Detect user intent from message.

        Args:
            message: User message text
            conversation_history: Previous messages for context

        Returns:
            IntentResult with mode, confidence, and reasoning
        """
        if not message or not message.strip():
            return IntentResult(
                mode=IntentMode.CHAT,
                confidence=0.5,
                reasoning="Empty message, defaulting to chat",
            )

        # Score each mode
        chat_score = self._score_patterns(message, self._chat_patterns)
        planning_score = self._score_patterns(message, self._planning_patterns)
        build_score = self._score_patterns(message, self._build_patterns)

        # Adjust scores based on message length
        # Longer messages often indicate complex tasks
        if len(message) > 200:
            planning_score *= 1.2
        elif len(message) < 50:
            build_score *= 1.1

        # Check for explicit mode commands
        explicit_mode = self._detect_explicit_mode(message)
        if explicit_mode:
            return IntentResult(
                mode=explicit_mode,
                confidence=0.95,
                reasoning="Explicit mode command detected",
            )

        # Determine winner
        scores = {
            IntentMode.CHAT: chat_score,
            IntentMode.PLANNING: planning_score,
            IntentMode.BUILD: build_score,
        }

        best_mode = max(scores, key=scores.get)
        best_score = scores[best_mode]
        total_score = sum(scores.values())

        # Calculate confidence
        if total_score > 0:
            confidence = best_score / total_score
        else:
            # Default to build for action-oriented messages
            confidence = 0.5
            best_mode = IntentMode.BUILD

        # Generate reasoning
        reasoning = self._generate_reasoning(best_mode, chat_score, planning_score, build_score)

        # Extract target path if present
        target_path = self._extract_path(message)
        project_name = self._extract_project_name(message)

        return IntentResult(
            mode=best_mode,
            confidence=min(confidence, 1.0),
            reasoning=reasoning,
            target_path=target_path,
            project_name=project_name,
        )

    def _score_patterns(self, text: str, patterns: List[re.Pattern]) -> float:
        """Score text against list of patterns."""
        score = 0.0
        for pattern in patterns:
            if pattern.search(text):
                score += 1.0
        return score

    def _detect_explicit_mode(self, message: str) -> Optional[IntentMode]:
        """Detect explicit mode commands like /plan, /build, /chat."""
        text = message.strip().lower()

        if text.startswith("/plan") or text.startswith("/planejar"):
            return IntentMode.PLANNING
        if text.startswith("/build") or text.startswith("/construir"):
            return IntentMode.BUILD
        if text.startswith("/chat") or text.startswith("/conversar"):
            return IntentMode.CHAT

        return None

    def _generate_reasoning(
        self,
        mode: IntentMode,
        chat_score: float,
        planning_score: float,
        build_score: float,
    ) -> str:
        """Generate human-readable reasoning for classification."""
        if mode == IntentMode.CHAT:
            return f"Chat mode (scores: chat={chat_score:.1f}, planning={planning_score:.1f}, build={build_score:.1f})"
        elif mode == IntentMode.PLANNING:
            return f"Planning mode (scores: chat={chat_score:.1f}, planning={planning_score:.1f}, build={build_score:.1f})"
        else:
            return f"Build mode (scores: chat={chat_score:.1f}, planning={planning_score:.1f}, build={build_score:.1f})"

    def _extract_path(self, message: str) -> Optional[str]:
        """Extract path from message if present."""
        patterns = [
            r"(?:em|no|na|para|at|in|to)\s+([~\.]?/[\w\-./]+)",
            r"(/(?:home|Users|ruas)/[\w\-./]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_project_name(self, message: str) -> Optional[str]:
        """Extract project name from message."""
        patterns = [
            r"(?:projeto|projecto?|app|aplicação?)\s+([a-zA-Z0-9][\w\-]{2,})",
            r"([a-zA-Z0-9][\w\-]{2,})\s+(?:projeto|projecto?|app|aplicação?)",
        ]
        common_words = {
            "um", "uma", "o", "a", "meu", "minha", "este", "esta",
            "a", "an", "the", "my", "this", "that",
        }
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1)
                if name.lower() not in common_words:
                    return name
        return None
