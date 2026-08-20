"""Tests for runtime_errors collection (no live network)."""

from hermes_cli.runtime_errors import (
    AGENT_BROWSER_MISSING,
    NODE_MODULES_MISSING,
    PROGRAM_ROOT_MISSING,
    collect_runtime_plane_issues,
    format_runtime_issue,
)


def test_unmanaged_install_returns_no_issues(monkeypatch):
    monkeypatch.delenv("HERMES_MANAGED_INSTALL", raising=False)
    assert collect_runtime_plane_issues() == []


def test_format_runtime_issue_includes_repair_owner():
    from hermes_cli.runtime_errors import RuntimeIssue

    text = format_runtime_issue(
        RuntimeIssue(PROGRAM_ROOT_MISSING, "missing program root")
    )
    assert "HERMES_RUNTIME_001" in text
    assert "repair_owner=opsi" in text


def test_missing_node_modules_detected(tmp_path, monkeypatch):
    program = tmp_path / "program"
    node = program / "node"
    workspace = node / "hermes-agent"
    workspace.mkdir(parents=True)
    (workspace / "package.json").write_text("{}\n", encoding="utf-8")
    (node / "node.exe").write_text("", encoding="utf-8")
    (program / "python" / "python.exe").parent.mkdir(parents=True)
    (program / "python" / "python.exe").write_text("", encoding="utf-8")

    monkeypatch.setenv("HERMES_AGENT_ROOT", str(workspace))
    monkeypatch.setenv("HERMES_MANAGED_INSTALL", "1")

    import hermes_constants

    monkeypatch.setattr(hermes_constants, "node_tool_runnable", lambda path: True)

    codes = {issue.code for issue in collect_runtime_plane_issues()}
    assert NODE_MODULES_MISSING in codes
    assert AGENT_BROWSER_MISSING in codes
