"""Runtime layout path resolution (SMC managed install / developer fallback)."""

import os
from pathlib import Path

import pytest

import hermes_constants
from hermes_constants import (
    bootstrap_hermes_managed_node,
    get_managed_node_root,
    get_node_workspace_root,
    get_program_root,
    heal_hermes_managed_node,
    is_managed_install,
    iter_hermes_node_dirs,
    set_hermes_home_override,
    reset_hermes_home_override,
)


@pytest.fixture
def smc_layout(tmp_path, monkeypatch):
    """Simulate SMC Data + Program plane without hardcoded D:/C: paths."""
    data_home = tmp_path / "data"
    program_root = tmp_path / "program"
    node_root = program_root / "node"
    workspace = node_root / "hermes-agent"
    data_home.mkdir()
    node_root.mkdir(parents=True)
    workspace.mkdir()

    monkeypatch.setenv("HERMES_HOME", str(data_home))
    monkeypatch.setenv("HERMES_AGENT_ROOT", str(workspace))
    monkeypatch.setenv("HERMES_MANAGED_INSTALL", "1")
    return {
        "data_home": data_home,
        "program_root": program_root,
        "node_root": node_root,
        "workspace": workspace,
    }


class TestManagedInstallDetection:
    def test_managed_install_true_values(self, monkeypatch):
        for value in ("1", "true", "yes", "on", "TRUE"):
            monkeypatch.setenv("HERMES_MANAGED_INSTALL", value)
            assert is_managed_install() is True

    def test_managed_install_false_when_unset(self, monkeypatch):
        monkeypatch.delenv("HERMES_MANAGED_INSTALL", raising=False)
        assert is_managed_install() is False


class TestNodeWorkspaceRoot:
    def test_uses_hermes_agent_root_when_set(self, smc_layout):
        assert get_node_workspace_root() == smc_layout["workspace"].resolve()

    def test_unset_falls_back_to_repo_root(self, monkeypatch):
        monkeypatch.delenv("HERMES_AGENT_ROOT", raising=False)
        assert get_node_workspace_root() == Path(hermes_constants.__file__).resolve().parent

    def test_profile_override_does_not_change_workspace(self, smc_layout, monkeypatch):
        profile_home = smc_layout["data_home"] / "profiles" / "writer"
        profile_home.mkdir(parents=True)
        monkeypatch.setenv("HERMES_HOME", str(profile_home))
        assert get_node_workspace_root() == smc_layout["workspace"].resolve()

    def test_ignores_profile_local_hermes_agent_dir(self, smc_layout, monkeypatch):
        """Negative test: profile-scoped hermes-agent must not become workspace."""
        profile_home = smc_layout["data_home"] / "profiles" / "writer"
        wrong_workspace = profile_home / "hermes-agent"
        wrong_workspace.mkdir(parents=True)
        (wrong_workspace / "package.json").write_text("{}\n", encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(profile_home))

        assert get_node_workspace_root() == smc_layout["workspace"].resolve()
        assert get_node_workspace_root() != wrong_workspace.resolve()


class TestManagedNodeRoot:
    def test_derives_from_agent_root_parent(self, smc_layout):
        assert get_managed_node_root() == smc_layout["node_root"].resolve()

    def test_profile_home_does_not_change_node_root(self, smc_layout, monkeypatch):
        profile_home = smc_layout["data_home"] / "profiles" / "finance"
        profile_home.mkdir(parents=True)
        monkeypatch.setenv("HERMES_HOME", str(profile_home))
        assert get_managed_node_root() == smc_layout["node_root"].resolve()

    def test_developer_fallback_uses_hermes_home_node(self, tmp_path, monkeypatch):
        home = tmp_path / "hermes"
        home.mkdir()
        monkeypatch.delenv("HERMES_AGENT_ROOT", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(home))
        assert get_managed_node_root() == home / "node"

    def test_context_override_home_only_affects_fallback(self, tmp_path, monkeypatch):
        default_home = tmp_path / "default"
        profile_home = tmp_path / "profiles" / "writer"
        default_home.mkdir()
        profile_home.mkdir(parents=True)
        monkeypatch.delenv("HERMES_AGENT_ROOT", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(default_home))

        token = set_hermes_home_override(profile_home)
        try:
            assert get_managed_node_root() == profile_home / "node"
        finally:
            reset_hermes_home_override(token)


class TestProgramRoot:
    def test_program_root_from_agent_root(self, smc_layout):
        assert get_program_root() == smc_layout["program_root"].resolve()

    def test_program_root_none_without_agent_root(self, monkeypatch):
        monkeypatch.delenv("HERMES_AGENT_ROOT", raising=False)
        assert get_program_root() is None


class TestIterHermesNodeDirs:
    def test_smc_managed_windows_order(self, smc_layout, monkeypatch):
        monkeypatch.setattr(hermes_constants.sys, "platform", "win32")
        node_dir = smc_layout["node_root"]
        bin_dir = node_dir / "bin"
        assert iter_hermes_node_dirs() == [node_dir, bin_dir]

    def test_smc_managed_posix_order(self, smc_layout, monkeypatch):
        monkeypatch.setattr(hermes_constants.sys, "platform", "linux")
        node_dir = smc_layout["node_root"]
        bin_dir = node_dir / "bin"
        assert iter_hermes_node_dirs() == [bin_dir, node_dir]


class TestManagedNodeHealGuard:
    def test_heal_blocked_in_managed_install(self, smc_layout, monkeypatch):
        monkeypatch.setattr(
            hermes_constants,
            "hermes_managed_node_tree_present",
            lambda home=None: True,
        )
        monkeypatch.setattr(hermes_constants, "_managed_node_heal_attempted", False)
        assert heal_hermes_managed_node() is False

    def test_bootstrap_does_not_download_in_managed_install(self, smc_layout, monkeypatch):
        def _fail_download():
            raise AssertionError("bootstrap must not download Node in managed mode")

        monkeypatch.setattr(hermes_constants, "find_hermes_node_executable", lambda cmd: None)
        monkeypatch.setattr(hermes_constants, "_heal_managed_node_windows", _fail_download)
        assert bootstrap_hermes_managed_node() is None
