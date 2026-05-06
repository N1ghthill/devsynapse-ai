"""Rich renderers for TUI command and tool output."""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree


@dataclass(frozen=True)
class DiffStats:
    """Summary for unified diff output."""

    files: int
    hunks: int
    additions: int
    deletions: int


@dataclass(frozen=True)
class ProgressSummary:
    """Summary for explicit command progress output."""

    current: float
    total: float
    percent: float
    label: str


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

    table = render_table_output(output)
    if table is not None:
        rows = tabular_output_rows(output)
        row_count = max(len(rows or []) - 1, 0)
        col_count = len(rows[0]) if rows else 0
        sections.append(
            Text.assemble(
                ("table ", "bold"),
                (f"{row_count} rows  {col_count} cols", "dim"),
            )
        )
        sections.append(table)
        return Group(*sections)

    tree = render_structured_tree(output)
    if tree is not None:
        sections.append(Text.assemble(("tree ", "bold"), ("JSON", "dim")))
        sections.append(tree)
        return Group(*sections)

    structured = structured_output_lexer(output)
    if structured is not None:
        lexer, normalized = structured
        sections.append(
            Text.assemble(
                ("structured ", "bold"),
                (lexer.upper(), "dim"),
            )
        )
        sections.append(
            Syntax(
                normalized,
                lexer,
                word_wrap=False,
                theme="ansi_dark",
                line_numbers=False,
            )
        )
        return Group(*sections)

    progress = progress_summary(output)
    if progress is not None:
        sections.append(render_progress_bar(progress))

    sections.append(Text(output))
    return Group(*sections)


def structured_output_lexer(text: str) -> tuple[str, str] | None:
    """Return a syntax lexer and normalized text for JSON/YAML-like output."""
    stripped = text.strip()
    if not stripped:
        return None

    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            return "json", json.dumps(parsed, indent=2, ensure_ascii=False)

    if _looks_like_yaml(stripped):
        return "yaml", stripped

    return None


def render_structured_tree(text: str, *, max_depth: int = 5, max_items: int = 40) -> Tree | None:
    """Build a Rich tree for JSON objects and arrays."""
    stripped = strip_ansi(text).strip()
    if not stripped.startswith(("{", "[")):
        return None

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, (dict, list)):
        return None

    root = Tree(_container_label("JSON", parsed))
    _append_tree_items(root, parsed, depth=0, max_depth=max_depth, max_items=max_items)
    return root


def progress_summary(text: str) -> ProgressSummary | None:
    """Return explicit progress from command output when a line declares it."""
    for line in reversed(strip_ansi(text).splitlines()):
        stripped = line.strip()
        if not re.search(r"\b(progress|completed|done)\b", stripped, flags=re.IGNORECASE):
            continue
        ratio = re.search(r"(?P<current>\d+(?:\.\d+)?)\s*/\s*(?P<total>\d+(?:\.\d+)?)", stripped)
        if ratio:
            current = float(ratio.group("current"))
            total = float(ratio.group("total"))
            if total <= 0:
                continue
            percent = max(0.0, min(current / total * 100.0, 100.0))
            return ProgressSummary(current=current, total=total, percent=percent, label=stripped)

        percent_match = re.search(r"(?P<percent>\d+(?:\.\d+)?)\s*%", stripped)
        if percent_match:
            percent = max(0.0, min(float(percent_match.group("percent")), 100.0))
            return ProgressSummary(current=percent, total=100.0, percent=percent, label=stripped)
    return None


def render_progress_bar(progress: ProgressSummary, *, width: int = 24) -> Text:
    """Build a deterministic static progress bar."""
    filled = int(round(width * progress.percent / 100.0))
    bar = "#" * filled + "-" * (width - filled)
    return Text.assemble(
        ("progress ", "bold"),
        (f"[{bar}] ", "cyan"),
        (f"{progress.percent:5.1f}% ", "green"),
        (progress.label, "dim"),
    )


def tabular_output_rows(text: str) -> list[list[str]] | None:
    """Return normalized CSV/TSV rows when text is safe to render as a table."""
    stripped = strip_ansi(text).strip()
    if not stripped:
        return None

    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    first_line = lines[0]
    delimiter = "\t" if "\t" in first_line else ","
    if delimiter not in first_line:
        return None

    try:
        rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter))
    except csv.Error:
        return None

    if len(rows) < 2:
        return None

    rows = [[cell.strip() for cell in row] for row in rows]
    col_count = len(rows[0])
    if col_count < 2 or col_count > 10:
        return None
    if any(len(row) != col_count for row in rows):
        return None
    if any(not cell for cell in rows[0]):
        return None
    if all(not any(cell for cell in row) for row in rows[1:]):
        return None

    return rows


def render_table_output(text: str, *, max_rows: int = 30) -> Table | None:
    """Build a Rich table for CSV/TSV output."""
    rows = tabular_output_rows(text)
    if rows is None:
        return None

    headers, data_rows = rows[0], rows[1:]
    table = Table(show_header=True, header_style="bold cyan", expand=False)
    for index, header in enumerate(headers, start=1):
        table.add_column(header or f"column {index}", overflow="fold")

    visible_rows = data_rows[:max_rows]
    for row in visible_rows:
        table.add_row(*row)
    if len(data_rows) > max_rows:
        table.add_row(*(["..."] * len(headers)))

    return table


def strip_ansi(text: str) -> str:
    """Remove ANSI control sequences before diff detection."""
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _append_tree_items(
    parent: Tree,
    value: dict | list,
    *,
    depth: int,
    max_depth: int,
    max_items: int,
) -> None:
    if depth >= max_depth:
        parent.add(Text("... max depth reached", style="dim"))
        return

    if isinstance(value, dict):
        items = list(value.items())
        for key, item in items[:max_items]:
            key_text = str(key)
            if isinstance(item, (dict, list)):
                branch = parent.add(_container_label(key_text, item))
                _append_tree_items(
                    branch,
                    item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )
            else:
                parent.add(_scalar_row(key_text, item))
        _append_truncation(parent, len(items), max_items)
        return

    for index, item in enumerate(value[:max_items]):
        key_text = f"[{index}]"
        if isinstance(item, (dict, list)):
            branch = parent.add(_container_label(key_text, item))
            _append_tree_items(
                branch,
                item,
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
            )
        else:
            parent.add(_scalar_row(key_text, item))
    _append_truncation(parent, len(value), max_items)


def _container_label(name: str, value: dict | list) -> Text:
    if isinstance(value, dict):
        shape = f"{len(value)} keys"
    else:
        shape = f"{len(value)} items"
    return Text.assemble((name, "bold cyan"), ("  ", "dim"), (shape, "dim"))


def _scalar_row(name: str, value: object) -> Text:
    return Text.assemble((name, "bold"), (": ", "dim"), _scalar_value(value))


def _scalar_value(value: object) -> Text:
    if value is None:
        return Text("null", style="dim")
    if isinstance(value, bool):
        return Text(str(value).lower(), style="magenta")
    if isinstance(value, (int, float)):
        return Text(str(value), style="green")
    serialized = json.dumps(value, ensure_ascii=False)
    if len(serialized) > 100:
        serialized = f"{serialized[:97]}..."
    return Text(serialized)


def _append_truncation(parent: Tree, total: int, max_items: int) -> None:
    if total > max_items:
        parent.add(Text(f"... {total - max_items} more", style="dim"))


def _looks_like_yaml(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    yamlish = 0
    for line in lines[:20]:
        stripped = line.strip()
        if stripped.startswith(("- ", "---", "...")):
            yamlish += 1
            continue
        if re.match(r"^[A-Za-z0-9_.-]+:\s+.+$", stripped):
            yamlish += 1
    return yamlish >= 2
