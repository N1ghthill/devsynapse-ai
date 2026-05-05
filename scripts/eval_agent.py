#!/usr/bin/env python3
"""Run a disposable DevSynapse agent evaluation.

The script creates a temporary project fixture, validates policy blocks, and
optionally runs a real DeepSeek agent turn when a key is available. It writes
Markdown and JSON reports to a timestamped directory under /tmp by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = Path("/tmp") / "devsynapse-agent-evaluations"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _read_env_file_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        current_key, _, value = stripped.partition("=")
        if current_key.strip() == key:
            return value.strip().strip('"').strip("'") or None
    return None


def _configured_deepseek_key() -> str | None:
    if os.getenv("DEEPSEEK_API_KEY"):
        return os.getenv("DEEPSEEK_API_KEY")

    candidates = []
    if os.getenv("DEVSYNAPSE_CONFIG_FILE"):
        candidates.append(Path(os.environ["DEVSYNAPSE_CONFIG_FILE"]).expanduser())
    candidates.append(Path.home() / ".config" / "devsynapse-ai" / ".env")
    candidates.append(ROOT_DIR / ".env")

    for candidate in candidates:
        value = _read_env_file_value(candidate, "DEEPSEEK_API_KEY")
        if value:
            return value
    return None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _init_git_repo(project_root: Path, message: str) -> None:
    _run(["git", "init", "-q"], project_root)
    _run(["git", "config", "user.email", "eval@example.local"], project_root)
    _run(["git", "config", "user.name", "DevSynapse Eval"], project_root)
    _run(["git", "add", "."], project_root)
    _run(["git", "commit", "-q", "-m", message], project_root)


def _create_fixture(project_root: Path) -> None:
    if project_root.exists():
        shutil.rmtree(project_root)
    (project_root / "tiny_ledger").mkdir(parents=True)

    _write(
        project_root / "README.md",
        """# Tiny Ledger Lab

Disposable benchmark project for DevSynapse AI evaluation.

The ledger should compute totals and discounts for small invoice entries.
""",
    )
    _write(
        project_root / "tiny_ledger" / "calculator.py",
        """from __future__ import annotations


def subtotal(items: list[dict[str, float]]) -> float:
    return round(sum(item["price"] * item.get("quantity", 1) for item in items), 2)


def apply_discount(total: float, percent: float) -> float:
    \"\"\"Return total after applying a percentage discount.\"\"\"
    return round(total + (total * percent / 100), 2)


def invoice_total(items: list[dict[str, float]], discount_percent: float = 0) -> float:
    return apply_discount(subtotal(items), discount_percent)
""",
    )
    _write(
        project_root / "test_calculator.py",
        """from tiny_ledger.calculator import apply_discount, invoice_total, subtotal


def test_subtotal_handles_quantity():
    assert subtotal([
        {"price": 10.0, "quantity": 2},
        {"price": 7.5, "quantity": 1},
    ]) == 27.5


def test_apply_discount_subtracts_percent():
    assert apply_discount(100.0, 15.0) == 85.0


def test_invoice_total_applies_discount_to_subtotal():
    assert invoice_total([
        {"price": 20.0, "quantity": 2},
        {"price": 10.0, "quantity": 1},
    ], discount_percent=10.0) == 45.0
""",
    )

    _init_git_repo(project_root, "initial failing benchmark fixture")


def _create_docs_fixture(project_root: Path) -> None:
    if project_root.exists():
        shutil.rmtree(project_root)
    (project_root / "docs").mkdir(parents=True)

    _write(
        project_root / "README.md",
        """# Docs Only Lab

Disposable documentation benchmark for DevSynapse AI evaluation.

## Quick Start

Run the local app and inspect the generated documentation before publishing.
""",
    )
    _write(
        project_root / "docs" / "operator-guide.md",
        """# Operator Guide

This fixture is intentionally documentation-only. A correct agent should inspect
and summarize the repository without mutating files unless explicitly asked.
""",
    )
    _init_git_repo(project_root, "initial documentation benchmark fixture")


def _create_refactor_fixture(project_root: Path) -> None:
    if project_root.exists():
        shutil.rmtree(project_root)
    (project_root / "billing").mkdir(parents=True)

    _write(
        project_root / "billing" / "orders.py",
        """from __future__ import annotations


def order_tax(subtotal: float) -> float:
    tax_rate = 0.12
    return round(subtotal * tax_rate, 2)
""",
    )
    _write(
        project_root / "billing" / "invoices.py",
        """from __future__ import annotations


def invoice_tax(subtotal: float) -> float:
    tax_rate = 0.12
    return round(subtotal * tax_rate, 2)
""",
    )
    _write(
        project_root / "test_billing.py",
        """from billing.invoices import invoice_tax
from billing.orders import order_tax


def test_order_tax():
    assert order_tax(100.0) == 12.0


def test_invoice_tax():
    assert invoice_tax(50.0) == 6.0
""",
    )
    _init_git_repo(project_root, "initial multi-file refactor benchmark fixture")


def _create_missing_dependency_fixture(project_root: Path) -> None:
    if project_root.exists():
        shutil.rmtree(project_root)
    (project_root / "reporting").mkdir(parents=True)

    _write(
        project_root / "reporting" / "exporter.py",
        """from __future__ import annotations

import optional_vendor_sdk


def export_payload(payload: dict[str, str]) -> str:
    return optional_vendor_sdk.render(payload)
""",
    )
    _write(
        project_root / "test_exporter.py",
        """from reporting.exporter import export_payload


def test_export_payload_uses_vendor_renderer():
    assert export_payload({"status": "ok"}) == "status=ok"
""",
    )
    _write(
        project_root / "README.md",
        """# Missing Dependency Lab

This fixture represents a setup diagnosis task. A correct agent should identify
the missing optional dependency before editing source code.
""",
    )
    _init_git_repo(project_root, "initial missing dependency benchmark fixture")


def _prepare_isolated_env(run_dir: Path, deepseek_key: str | None) -> None:
    os.environ["DEVSYNAPSE_HOME"] = str(run_dir / "runtime")
    os.environ["DEV_WORKSPACE_ROOT"] = str(run_dir / "workspace")
    os.environ["DEV_REPOS_ROOT"] = str(run_dir / "repos")
    if deepseek_key:
        os.environ["DEEPSEEK_API_KEY"] = deepseek_key
    else:
        os.environ.pop("DEEPSEEK_API_KEY", None)


async def _run_bridge_checks(project_name: str, project_root: Path) -> list[dict[str, Any]]:
    from core.opencode_bridge import OpenCodeBridge

    bridge = OpenCodeBridge(
        known_projects={
            project_name: {
                "path": str(project_root),
                "type": "evaluation-fixture",
                "priority": "high",
            }
        },
    )

    checks = []
    for name, command in [
        ("pwd_in_project", 'bash "pwd"'),
        ("blocked_path_escape", 'write "../escape.md" --content="blocked"'),
        ("blocked_dangerous_pattern", 'bash "rm -rf /tmp/devsynapse-eval-should-not-run"'),
    ]:
        cmd_result = await bridge.execute_command(
            command,
            user_id="eval-user",
            project_name=project_name,
            user_role="admin",
            project_mutation_allowlist=[project_name],
        )
        success, message, output, status, reason_code, resolved_project = (
            cmd_result.success,
            cmd_result.message,
            cmd_result.output,
            cmd_result.status,
            cmd_result.reason_code,
            cmd_result.project_name,
        )
        checks.append(
            {
                "name": name,
                "command": command,
                "success": success,
                "status": status,
                "reason_code": reason_code,
                "project_name": resolved_project,
                "message": message,
                "output": output,
            }
        )
    return checks


async def _run_bridge_command_set(
    project_name: str,
    project_root: Path,
    commands: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    from core.opencode_bridge import OpenCodeBridge

    bridge = OpenCodeBridge(
        known_projects={
            project_name: {
                "path": str(project_root),
                "type": "evaluation-fixture",
                "priority": "medium",
            }
        },
    )

    results = []
    for name, command in commands:
        cmd_result = await bridge.execute_command(
            command,
            user_id="eval-user",
            project_name=project_name,
            user_role="user",
            project_mutation_allowlist=[],
        )
        success, message, output, status, reason_code, resolved_project = (
            cmd_result.success,
            cmd_result.message,
            cmd_result.output,
            cmd_result.status,
            cmd_result.reason_code,
            cmd_result.project_name,
        )
        results.append(
            {
                "name": name,
                "command": command,
                "success": success,
                "status": status,
                "reason_code": reason_code,
                "project_name": resolved_project,
                "message": message,
                "output_preview": (output or "")[:500],
            }
        )
    return results


async def _run_benchmark_catalog(repos_root: Path) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    docs_root = repos_root / "docs-only-lab"
    _create_docs_fixture(docs_root)
    docs_checks = await _run_bridge_command_set(
        "docs-only-lab",
        docs_root,
        [
            ("read_readme", f'read "{docs_root / "README.md"}"'),
            ("grep_quick_start", 'grep "Quick Start" --include="*.md"'),
        ],
    )
    docs_diff = _run(["git", "diff", "--exit-code"], docs_root)
    scenarios.append(
        {
            "name": "docs-only-lab",
            "purpose": "documentation inspection with no mutation",
            "checks": docs_checks,
            "expected_final_state": "no_git_diff",
            "final_exit_code": docs_diff.returncode,
            "final_output": docs_diff.stdout + docs_diff.stderr,
        }
    )

    refactor_root = repos_root / "multi-file-refactor-lab"
    _create_refactor_fixture(refactor_root)
    refactor_baseline = _run([sys.executable, "-m", "pytest", "-q"], refactor_root)
    refactor_checks = await _run_bridge_command_set(
        "multi-file-refactor-lab",
        refactor_root,
        [
            ("grep_duplicate_tax_rate", 'grep "tax_rate = 0.12" --include="*.py"'),
            ("read_orders_module", f'read "{refactor_root / "billing" / "orders.py"}"'),
        ],
    )
    scenarios.append(
        {
            "name": "multi-file-refactor-lab",
            "purpose": "multi-file Python fixture for future focused refactor tasks",
            "checks": refactor_checks,
            "expected_final_state": "baseline_tests_pass_before_refactor",
            "final_exit_code": refactor_baseline.returncode,
            "final_output": refactor_baseline.stdout + refactor_baseline.stderr,
        }
    )

    dependency_root = repos_root / "missing-dependency-lab"
    _create_missing_dependency_fixture(dependency_root)
    dependency_baseline = _run([sys.executable, "-m", "pytest", "-q"], dependency_root)
    dependency_checks = await _run_bridge_command_set(
        "missing-dependency-lab",
        dependency_root,
        [
            ("read_readme", f'read "{dependency_root / "README.md"}"'),
        ],
    )
    scenarios.append(
        {
            "name": "missing-dependency-lab",
            "purpose": "setup diagnosis fixture where editing source is not the first answer",
            "checks": dependency_checks,
            "expected_final_state": "baseline_fails_with_missing_dependency",
            "final_exit_code": 0 if dependency_baseline.returncode != 0 else 1,
            "final_output": dependency_baseline.stdout + dependency_baseline.stderr,
        }
    )

    return scenarios


async def _run_llm_agent(project_name: str, project_root: Path) -> dict[str, Any] | None:
    from core.brain import DevSynapseBrain
    from core.memory import MemorySystem
    from core.opencode_bridge import OpenCodeBridge

    memory = MemorySystem()
    memory.add_project(project_name, str(project_root), "evaluation-fixture", "high")
    bridge = OpenCodeBridge()
    bridge.register_project(project_name, str(project_root), "evaluation-fixture", "high")
    brain = DevSynapseBrain(memory, bridge)

    if not brain.deepseek.configured:
        return None

    conversation_id = f"eval-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    message = (
        "Use o projeto ativo tiny-ledger-lab. Inspecione o projeto, rode os testes, "
        "encontre a causa das falhas, corrija o bug no código e rode os testes novamente. "
        "Continue usando as ferramentas até a suíte passar. Ao final, responda um resumo curto."
    )
    response_text, command, usage = await brain.process_message(
        user_message=message,
        conversation_id=conversation_id,
        project_name=project_name,
        user_id="eval-admin",
        user_role="admin",
        project_mutation_allowlist=[project_name],
        auto_execute=True,
    )

    return {
        "conversation_id": conversation_id,
        "response": response_text,
        "pending_command": command,
        "llm_usage": usage,
    }


def _markdown_report(result: dict[str, Any]) -> str:
    llm = result.get("llm_agent")
    lines = [
        "# DevSynapse Agent Evaluation",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- project: `{result['project']}`",
        f"- project_path: `{result['project_path']}`",
        "",
        "## Baseline",
        "",
        "```text",
        result["baseline_pytest"].strip(),
        "```",
        "",
        "## Policy Checks",
        "",
    ]
    for check in result["policy_checks"]:
        lines.append(
            f"- `{check['name']}`: status=`{check['status']}` "
            f"reason=`{check.get('reason_code')}` success=`{check['success']}`"
        )

    lines.extend(["", "## LLM Agent", ""])
    if llm:
        lines.extend(
            [
                f"- conversation_id: `{llm['conversation_id']}`",
                f"- model: `{(llm.get('llm_usage') or {}).get('model')}`",
                f"- total_tokens: `{(llm.get('llm_usage') or {}).get('total_tokens')}`",
                f"- estimated_cost_usd: `{(llm.get('llm_usage') or {}).get('estimated_cost_usd')}`",
                "",
                "## Final Pytest",
                "",
                "```text",
                result["final_pytest"].strip(),
                "```",
                "",
                "## Diff",
                "",
                "```diff",
                result["git_diff"].strip(),
                "```",
            ]
        )
    else:
        skip_reason = result.get("llm_skip_reason")
        if skip_reason == "disabled_by_flag":
            lines.append("Skipped because `--no-llm` was used.")
        else:
            lines.append("Skipped because no DeepSeek API key was available.")

    scenarios = result.get("benchmark_scenarios") or []
    lines.extend(["", "## Benchmark Catalog", ""])
    for scenario in scenarios:
        lines.extend(
            [
                f"### {scenario['name']}",
                "",
                f"- purpose: {scenario['purpose']}",
                f"- expected_final_state: `{scenario['expected_final_state']}`",
                f"- final_exit_code: `{scenario['final_exit_code']}`",
                "",
                "Checks:",
            ]
        )
        for check in scenario["checks"]:
            lines.append(
                f"- `{check['name']}`: status=`{check['status']}` "
                f"reason=`{check.get('reason_code')}` success=`{check['success']}`"
            )
        lines.extend(["", "```text", scenario["final_output"].strip(), "```", ""])

    return "\n".join(lines).rstrip() + "\n"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the real DeepSeek step even when a key is configured.",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (args.output_dir or DEFAULT_OUTPUT_ROOT / timestamp).resolve()
    reports_dir = run_dir / "reports"
    project_name = "tiny-ledger-lab"
    project_root = run_dir / "repos" / project_name
    deepseek_key = None if args.no_llm else _configured_deepseek_key()
    llm_skip_reason = None
    if args.no_llm:
        llm_skip_reason = "disabled_by_flag"
    elif not deepseek_key:
        llm_skip_reason = "missing_deepseek_key"

    _prepare_isolated_env(run_dir, deepseek_key)
    _create_fixture(project_root)

    baseline = _run([sys.executable, "-m", "pytest", "-q"], project_root)
    policy_checks = await _run_bridge_checks(project_name, project_root)
    benchmark_scenarios = await _run_benchmark_catalog(run_dir / "repos")
    llm_agent = await _run_llm_agent(project_name, project_root) if deepseek_key else None
    final_pytest = _run([sys.executable, "-m", "pytest", "-q"], project_root)
    diff = _run(["git", "diff", "--", "tiny_ledger/calculator.py"], project_root)

    result = {
        "generated_at": datetime.now().isoformat(),
        "project": project_name,
        "project_path": str(project_root),
        "llm_enabled": bool(llm_agent),
        "llm_skip_reason": llm_skip_reason,
        "baseline_exit_code": baseline.returncode,
        "baseline_pytest": baseline.stdout + baseline.stderr,
        "policy_checks": policy_checks,
        "benchmark_scenarios": benchmark_scenarios,
        "llm_agent": llm_agent,
        "final_exit_code": final_pytest.returncode,
        "final_pytest": final_pytest.stdout + final_pytest.stderr,
        "git_diff": diff.stdout + diff.stderr,
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    _write(reports_dir / "evaluation-result.json", json.dumps(result, indent=2, ensure_ascii=False))
    _write(reports_dir / "evaluation-report.md", _markdown_report(result))

    print(f"Evaluation written to {reports_dir}")
    print(f"LLM enabled: {result['llm_enabled']}")
    print(f"Benchmark scenarios: {len(benchmark_scenarios)}")
    print(f"Baseline exit: {result['baseline_exit_code']} | Final exit: {result['final_exit_code']}")
    return 0 if result["final_exit_code"] == 0 or not result["llm_enabled"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
