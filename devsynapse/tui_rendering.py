"""Rich renderers for TUI command and tool output."""
from __future__ import annotations

import re
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.text import Text


@dataclass(frozen=True)
class DiffStats:
    """Summary for unified diff output."""

    files: int
    hunks: int
    additions: int
    deletions: int


def is_unified_diff(text: str) -> bool:
    """Return True when text looks like a unified diff or git patch."""
    if not text.strip():
        return False
    lines = text.splitlines()
    if any(line.startswith("diff --git ") for line in lines):
        return True
    has_old = any(line.startswith("--- ") for line in lines)
    has_new = any(line.startswith("+++ ") for line in lines)
    has_hunk = any(line.startswith("@@ ") for line in lines)
    return has_old and has_new and has_hunk


def diff_stats(text: str) -> DiffStats:
    """Count files, hunks, additions and deletions in diff-like text."""
    files = set()
    hunks = additions = deletions = 0

    for line in text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.add(parts[3].removeprefix("b/"))
            continue
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            files.add(line[4:].strip().removeprefix("b/"))
            continue
        if line.startswith("@@ "):
            hunks += 1
            continue
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            deletions += 1

    if not files and (additions or deletions or hunks):
        files.add("patch")
    return DiffStats(
        files=len(files),
        hunks=hunks,
        additions=additions,
        deletions=deletions,
    )


def render_command_result(
    *,
    message: str,
    output: str | None = None,
    reason_code: str | None = None,
) -> RenderableType:
    """Build a Rich renderable for command output."""
    sections: list[RenderableType] = [Text(message)]
    if reason_code:
        sections.append(Text(f"reason: {reason_code}", style="dim"))
    if not output:
        return Group(*sections)

    if is_unified_diff(output):
        stats = diff_stats(output)
        sections.append(
            Text.assemble(
                ("diff ", "bold"),
                (f"{stats.files} files  ", "dim"),
                (f"+{stats.additions} ", "green"),
                (f"-{stats.deletions}  ", "red"),
                (f"{stats.hunks} hunks", "dim"),
            )
        )
        sections.append(
            Syntax(
                output,
                "diff",
                word_wrap=False,
                theme="ansi_dark",
                line_numbers=False,
            )
        )
        return Group(*sections)

    sections.append(Text(output))
    return Group(*sections)


def strip_ansi(text: str) -> str:
    """Remove ANSI control sequences before diff detection."""
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
