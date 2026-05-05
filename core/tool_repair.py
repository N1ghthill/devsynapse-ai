"""Tool repair and response sanitization helpers."""

import re
from typing import Optional, Union

from core.deepseek import LLMResult


def coerce_llm_result(result: Union[str, LLMResult]) -> LLMResult:
    """Normalize API output into a guaranteed LLMResult."""
    if isinstance(result, LLMResult):
        return result
    return LLMResult(content=result)


def sanitize_unconfirmed_execution_claims(
    response_text: str,
    opencode_command: Optional[str],
) -> str:
    """Prevent the assistant from claiming side effects that never executed."""
    if opencode_command:
        return response_text

    shell_like = re.search(
        r'(^|\n)\s*(echo|cat|touch|mkdir|rm|mv|cp|find|grep|sed)\b.*(>|>>|\|\||&&)',
        response_text,
        re.IGNORECASE,
    )
    success_claim = re.search(
        r'\b(done|completed|file created|created the file|finished|ready[!,]?\s+created)\b',
        response_text,
        re.IGNORECASE,
    )

    if not shell_like and not success_claim:
        return response_text

    return (
        "I haven't executed any changes yet.\n\n"
        "I can only propose actions using my available tools, which then need "
        "to be confirmed in the interface. Ask me to try again and I'll respond "
        "with a single executable command."
    )
