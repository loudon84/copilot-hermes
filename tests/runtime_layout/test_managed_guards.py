"""Managed runtime protection guards."""

import pytest

import hermes_constants
from hermes_constants import bootstrap_hermes_managed_node, heal_hermes_managed_node


class TestManagedGuards:
    def test_heal_blocked(self, tmp_path, monkeypatch):
        home = tmp_path / "data"
        program = tmp_path / "program"
        workspace = program / "node" / "hermes-agent"
        home.mkdir()
        workspace.mkdir(parents=True)
        (program / "node" / "npm.cmd").write_text("@echo off\n", encoding="utf-8")

        monkeypatch.setenv("HERMES_HOME", str(home))
        monkeypatch.setenv("HERMES_AGENT_ROOT", str(workspace))
        monkeypatch.setenv("HERMES_MANAGED_INSTALL", "1")
        monkeypatch.setattr(hermes_constants, "_managed_node_heal_attempted", False)
        monkeypatch.setattr(
            hermes_constants,
            "hermes_managed_node_tree_present",
            lambda home=None: True,
        )

        assert heal_hermes_managed_node() is False

    def test_bootstrap_never_downloads(self, tmp_path, monkeypatch):
        workspace = tmp_path / "program" / "node" / "hermes-agent"
        workspace.mkdir(parents=True)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "data"))
        monkeypatch.setenv("HERMES_AGENT_ROOT", str(workspace))
        monkeypatch.setenv("HERMES_MANAGED_INSTALL", "1")
        monkeypatch.setattr(hermes_constants, "find_hermes_node_executable", lambda cmd: None)

        def _fail():
            raise AssertionError("must not download Node in managed mode")

        monkeypatch.setattr(hermes_constants, "_heal_managed_node_windows", _fail)
        assert bootstrap_hermes_managed_node() is None


class TestRuntimeIssueCollection:
    def test_missing_program_root(self, tmp_path, monkeypatch):
        from hermes_cli.runtime_errors import PROGRAM_ROOT_MISSING, collect_runtime_plane_issues

        monkeypatch.setenv("HERMES_MANAGED_INSTALL", "1")
        monkeypatch.delenv("HERMES_AGENT_ROOT", raising=False)
        issues = collect_runtime_plane_issues()
        assert any(issue.code == PROGRAM_ROOT_MISSING for issue in issues)

    def test_missing_agent_browser(self, tmp_path, monkeypatch):
        from hermes_cli.runtime_errors import AGENT_BROWSER_MISSING, collect_runtime_plane_issues

        program = tmp_path / "program"
        node = program / "node"
        workspace = node / "hermes-agent"
        workspace.mkdir(parents=True)
        (workspace / "package.json").write_text("{}\n", encoding="utf-8")
        (workspace / "node_modules").mkdir()
        (node / "node.exe").write_text("", encoding="utf-8")
        (program / "python" / "python.exe").parent.mkdir(parents=True)
        (program / "python" / "python.exe").write_text("", encoding="utf-8")

        monkeypatch.setenv("HERMES_AGENT_ROOT", str(workspace))
        monkeypatch.setenv("HERMES_MANAGED_INSTALL", "1")
        monkeypatch.setattr(hermes_constants, "node_tool_runnable", lambda path: True)

        issues = collect_runtime_plane_issues()
        assert any(issue.code == AGENT_BROWSER_MISSING for issue in issues)
        assert all(issue.repair_owner == "opsi" for issue in issues)
