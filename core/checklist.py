"""Objective checklist helpers for auto-executed implementation tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TaskChecklist:
    expected_files: set[str]
    completed_files: set[str]
    requires_pytest: bool = False
    pytest_passed: bool = False


def build_task_checklist(user_message: str) -> Optional[TaskChecklist]:
    """Extract a small objective completion checklist from implementation requests."""

    text = user_message or ""
    file_matches = re.findall(
        r"(?<![\w./-])([\w.-]+(?:/[\w.-]+)*\.(?:py|tsx|ts|js|jsx|json|toml|md|css|html|rs|yml|yaml))(?![\w./-])",
        text,
        flags=re.IGNORECASE,
    )
    expected_files = {
        match.strip("`'\".,;:()[]{}").lstrip("./")
        for match in file_matches
        if match.strip("`'\".,;:()[]{}")
    }
    requires_pytest = bool(re.search(r"\b(pytest|testes?\s+passar|tests?\s+pass)\b", text, re.I))
    if not expected_files and not requires_pytest:
        return None
    return TaskChecklist(
        expected_files=expected_files,
        completed_files=set(),
        requires_pytest=requires_pytest,
    )


def update_task_checklist(
    checklist: TaskChecklist,
    command: str,
    output: Optional[str],
) -> None:
    write_match = re.match(r'write\s+"([^"]+)"', command)
    if write_match:
        written_path = write_match.group(1).lstrip("./")
        for expected_file in checklist.expected_files:
            if written_path.endswith(expected_file):
                checklist.completed_files.add(expected_file)

    if "pytest" in command.lower():
        result_text = f"{output or ''}".lower()
        if re.search(r"\b\d+\s+passed\b", result_text) or "passed" in result_text:
            checklist.pytest_passed = True


def task_checklist_complete(checklist: TaskChecklist) -> bool:
    files_done = checklist.expected_files.issubset(checklist.completed_files)
    tests_done = not checklist.requires_pytest or checklist.pytest_passed
    return files_done and tests_done


def task_checklist_status(checklist: TaskChecklist) -> str:
    missing_files = sorted(checklist.expected_files - checklist.completed_files)
    lines = []
    if checklist.expected_files:
        done = sorted(checklist.completed_files)
        lines.append(f"Files done: {', '.join(done) if done else '(none)'}")
        lines.append(f"Files missing: {', '.join(missing_files) if missing_files else '(none)'}")
    if checklist.requires_pytest:
        lines.append(f"Pytest passed: {'yes' if checklist.pytest_passed else 'no'}")
    return "\n".join(lines)


def build_checklist_repair_messages(
    assistant_text: str,
    checklist: TaskChecklist,
) -> List[Dict[str, str]]:
    return [
        {"role": "assistant", "content": assistant_text or "Continuing the task."},
        {
            "role": "user",
            "content": (
                "The original task is not complete according to this objective checklist:\n"
                f"{task_checklist_status(checklist)}\n\n"
                "Continue the original task now. Emit exactly one next tool call. "
                "Do not provide a final summary until every listed file exists and "
                "the required test command has passed."
            ),
        },
    ]
