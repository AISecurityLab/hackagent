# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
from pathlib import Path
from types import SimpleNamespace

import click
from click.testing import CliRunner


def test_normalize_aliases_and_presence_checks():
    mod = importlib.import_module("hackagent.interfaces.cli.commands.examples")

    aliases = mod._normalize_ollama_model_aliases("gemma3:latest")
    assert "gemma3" in aliases

    assert mod._is_model_present("gemma3", {"gemma3:latest"}) is True
    assert mod._is_model_present("other", {"gemma3:latest"}) is False


def test_run_hackagent_cli_command_raises_on_failure(monkeypatch):
    mod = importlib.import_module("hackagent.interfaces.cli.commands.examples")

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    try:
        mod._run_hackagent_cli_command(["scan", "https://example.com"])
        assert False, "expected click.ClickException"
    except click.ClickException as exc:
        assert "Command failed" in str(exc)


def test_running_an_example_starts_its_agent_then_runs_the_campaign(monkeypatch):
    mod = importlib.import_module("hackagent.interfaces.cli.commands.examples")

    class _FakeProc:
        def poll(self):
            return None

    calls = {"stop": 0, "wait": 0, "run": 0}

    monkeypatch.setattr(
        mod, "_start_background_python", lambda *args, **kwargs: _FakeProc()
    )

    def _fake_wait(*args, **kwargs):
        calls["wait"] += 1

    def _fake_run(path):
        calls["run"] += 1
        assert Path(path).name == "flipattack-sqldesk.yaml"

    def _fake_stop(*args, **kwargs):
        calls["stop"] += 1

    monkeypatch.setattr(mod, "_wait_for_tcp_port", _fake_wait)
    monkeypatch.setattr(mod, "_run_campaign_file", _fake_run)
    monkeypatch.setattr(mod, "_stop_background_process", _fake_stop)

    runner = CliRunner()
    result = runner.invoke(
        mod.examples, ["run", "openai_sdk/db_tool_sandbox/flipattack-sqldesk"]
    )

    assert result.exit_code == 0, result.output
    assert calls == {"stop": 1, "wait": 1, "run": 1}


def test_its_agent_is_stopped_when_it_never_starts(monkeypatch):
    mod = importlib.import_module("hackagent.interfaces.cli.commands.examples")

    class _FakeProc:
        def poll(self):
            return None

    calls = {"stop": 0}

    monkeypatch.setattr(
        mod, "_start_background_python", lambda *args, **kwargs: _FakeProc()
    )
    monkeypatch.setattr(
        mod,
        "_wait_for_tcp_port",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            click.ClickException("not ready")
        ),
    )
    monkeypatch.setattr(mod, "_run_campaign_file", lambda *args, **kwargs: None)

    def _fake_stop(*args, **kwargs):
        calls["stop"] += 1

    monkeypatch.setattr(mod, "_stop_background_process", _fake_stop)

    runner = CliRunner()
    result = runner.invoke(
        mod.examples, ["run", "openai_sdk/db_tool_sandbox/flipattack-sqldesk"]
    )

    assert result.exit_code != 0
    assert calls["stop"] == 1
