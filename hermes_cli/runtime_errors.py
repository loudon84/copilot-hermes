"""Structured runtime-plane error codes for SMC managed installs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HERMES_RUNTIME_001 = "HERMES_RUNTIME_001"
PROGRAM_ROOT_MISSING = HERMES_RUNTIME_001

HERMES_RUNTIME_002 = "HERMES_RUNTIME_002"
PYTHON_RUNTIME_MISSING = HERMES_RUNTIME_002

HERMES_RUNTIME_003 = "HERMES_RUNTIME_003"
NODE_RUNTIME_MISSING = HERMES_RUNTIME_003

HERMES_RUNTIME_004 = "HERMES_RUNTIME_004"
NODE_RUNTIME_DAMAGED = HERMES_RUNTIME_004

HERMES_RUNTIME_005 = "HERMES_RUNTIME_005"
NODE_VERSION_MISMATCH = HERMES_RUNTIME_005

HERMES_RUNTIME_006 = "HERMES_RUNTIME_006"
NODE_WORKSPACE_MISSING = HERMES_RUNTIME_006

HERMES_RUNTIME_007 = "HERMES_RUNTIME_007"
PACKAGE_JSON_MISSING = HERMES_RUNTIME_007

HERMES_RUNTIME_008 = "HERMES_RUNTIME_008"
NODE_MODULES_MISSING = HERMES_RUNTIME_008

HERMES_RUNTIME_009 = "HERMES_RUNTIME_009"
AGENT_BROWSER_MISSING = HERMES_RUNTIME_009

HERMES_RUNTIME_010 = "HERMES_RUNTIME_010"
MANAGED_RUNTIME_MUTATION_DENIED = HERMES_RUNTIME_010


@dataclass(frozen=True)
class RuntimeIssue:
    code: str
    message: str
    repair_required: bool = True
    repair_owner: str = "opsi"


def format_runtime_issue(issue: RuntimeIssue) -> str:
    parts = [f"[{issue.code}] {issue.message}"]
    if issue.repair_required:
        parts.append(f"repair_required=true repair_owner={issue.repair_owner}")
    return " ".join(parts)


def collect_runtime_plane_issues() -> list[RuntimeIssue]:
    """Return runtime-plane issues for the current managed layout."""
    import sys

    from hermes_constants import (
        get_managed_node_root,
        get_node_workspace_root,
        get_program_root,
        is_managed_install,
        node_tool_runnable,
    )

    if not is_managed_install():
        return []

    issues: list[RuntimeIssue] = []

    program_root = get_program_root()
    if program_root is None or not program_root.is_dir():
        issues.append(
            RuntimeIssue(
                PROGRAM_ROOT_MISSING,
                f"Program root missing: {program_root or '<unset>'}",
            )
        )
        return issues

    python_exe = program_root / "python" / ("python.exe" if sys.platform == "win32" else "python")
    if not python_exe.is_file():
        issues.append(
            RuntimeIssue(
                PYTHON_RUNTIME_MISSING,
                f"Python runtime missing: {python_exe}",
            )
        )

    node_root = get_managed_node_root()
    node_exe = node_root / ("node.exe" if sys.platform == "win32" else "bin/node")
    if not node_exe.is_file():
        issues.append(
            RuntimeIssue(
                NODE_RUNTIME_MISSING,
                f"Node runtime missing: {node_exe}",
            )
        )
    elif not node_tool_runnable(str(node_exe)):
        issues.append(
            RuntimeIssue(
                NODE_RUNTIME_DAMAGED,
                f"Node runtime not runnable: {node_exe}",
            )
        )

    workspace = get_node_workspace_root()
    if not workspace.is_dir():
        issues.append(
            RuntimeIssue(
                NODE_WORKSPACE_MISSING,
                f"Node workspace missing: {workspace}",
            )
        )
        return issues

    package_json = workspace / "package.json"
    if not package_json.is_file():
        issues.append(
            RuntimeIssue(
                PACKAGE_JSON_MISSING,
                f"package.json missing: {package_json}",
            )
        )

    node_modules = workspace / "node_modules"
    if not node_modules.is_dir():
        issues.append(
            RuntimeIssue(
                NODE_MODULES_MISSING,
                f"node_modules missing: {node_modules}",
            )
        )
    else:
        agent_browser = node_modules / "agent-browser"
        if not agent_browser.is_dir():
            issues.append(
                RuntimeIssue(
                    AGENT_BROWSER_MISSING,
                    f"agent-browser package missing: {agent_browser}",
                )
            )

    return issues


def runtime_issues_summary(issues: Iterable[RuntimeIssue]) -> list[str]:
    return [format_runtime_issue(issue) for issue in issues]
