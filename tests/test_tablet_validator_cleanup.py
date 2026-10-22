"""Regression tests for the tablet validator's process lifecycle (no browser needed)."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from scripts import validate_tablet_layout as tablet


def _prepare_root(tmp_path: Path, monkeypatch):
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "css" / "qr-simulation.css").write_text(
        tablet.CSS_MARKER, encoding="utf-8"
    )
    monkeypatch.setattr(tablet, "project_root", lambda: tmp_path)
    monkeypatch.setattr(tablet, "free_port", lambda: 8765)
    monkeypatch.setattr(sys, "argv", ["validate_tablet_layout.py"])


def test_missing_playwright_does_not_start_server(tmp_path, monkeypatch):
    _prepare_root(tmp_path, monkeypatch)
    starter = Mock(side_effect=AssertionError("No server may start before preflight"))
    monkeypatch.setattr(tablet.subprocess, "Popen", starter)
    monkeypatch.setattr(tablet, "load_playwright", Mock(side_effect=SystemExit(1)))

    with pytest.raises(SystemExit) as exc:
        tablet.main()
    assert exc.value.code == 1
    starter.assert_not_called()


def test_health_failure_always_cleans_server(tmp_path, monkeypatch):
    _prepare_root(tmp_path, monkeypatch)
    server = Mock()
    monkeypatch.setattr(tablet.subprocess, "Popen", Mock(return_value=server))
    monkeypatch.setattr(tablet, "load_playwright", lambda: Mock())
    monkeypatch.setattr(tablet, "wait_for_health", Mock(side_effect=SystemExit(1)))
    cleanup = Mock()
    monkeypatch.setattr(tablet, "stop_server_tree", cleanup)

    with pytest.raises(SystemExit):
        tablet.main()
    cleanup.assert_called_once_with(server)


def test_browser_launch_failure_always_cleans_server(tmp_path, monkeypatch):
    _prepare_root(tmp_path, monkeypatch)
    server = Mock()
    monkeypatch.setattr(tablet.subprocess, "Popen", Mock(return_value=server))
    monkeypatch.setattr(tablet, "wait_for_health", Mock())
    cleanup = Mock()
    monkeypatch.setattr(tablet, "stop_server_tree", cleanup)
    context = Mock()
    context.__enter__ = Mock(return_value=object())
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(tablet, "load_playwright", lambda: lambda: context)
    monkeypatch.setattr(tablet, "launch_browsers", Mock(side_effect=RuntimeError("Browser launch failed")))

    with pytest.raises(RuntimeError, match="Browser launch failed"):
        tablet.main()
    cleanup.assert_called_once_with(server)


def test_windows_cleanup_terminates_full_process_tree(monkeypatch):
    monkeypatch.setattr(tablet.sys, "platform", "win32")
    server = Mock()
    server.pid = 4321
    server.wait.return_value = 0
    result = subprocess.CompletedProcess([], 0)
    runner = Mock(return_value=result)
    monkeypatch.setattr(tablet.subprocess, "run", runner)

    tablet.stop_server_tree(server)

    assert runner.call_args.args[0] == ["taskkill", "/PID", "4321", "/T", "/F"]
    server.wait.assert_called_once_with(timeout=5)
    server.kill.assert_not_called()
    server.terminate.assert_not_called()


def test_unix_cleanup_terminates_local_server(monkeypatch):
    monkeypatch.setattr(tablet.sys, "platform", "linux")
    server = Mock()
    server.poll.return_value = None
    tablet.stop_server_tree(server)
    server.terminate.assert_called_once_with()
    server.wait.assert_called_once_with(timeout=5)
