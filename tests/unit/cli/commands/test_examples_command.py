# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
from pathlib import Path
from types import SimpleNamespace

import click
from click.testing import CliRunner


def test_extract_ollama_models_from_judges_and_embedder():
    mod = importlib.import_module("hackagent.cli.commands.examples")

    cfg = {
        "agent": {"adapter_operational_config": {"name": "target-model"}},
        "attack_config": {
            "attacker": {"identifier": "attacker-model"},
            "judges": [{"identifier": "judge-model"}],
            "embedder": {"identifier": "embedder-model"},
        },
    }

    models = mod._extract_ollama_models_from_demo_cfg(cfg)

    assert models["target"] == "target-model"
    assert models["attacker"] == "attacker-model"
    assert models["judge"] == "judge-model"
    assert models["embedder"] == "embedder-model"


def test_normalize_aliases_and_presence_checks():
    mod = importlib.import_module("hackagent.cli.commands.examples")

    aliases = mod._normalize_ollama_model_aliases("gemma3:latest")
    assert "gemma3" in aliases

    assert mod._is_model_present("gemma3", {"gemma3:latest"}) is True
    assert mod._is_model_present("other", {"gemma3:latest"}) is False


def test_run_hackagent_cli_command_raises_on_failure(monkeypatch):
    mod = importlib.import_module("hackagent.cli.commands.examples")

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    try:
        mod._run_hackagent_cli_command(["scan", "https://example.com"])
        assert False, "expected click.ClickException"
    except click.ClickException as exc:
        assert "Command failed" in str(exc)


def test_resolve_example_dir_with_required_files(monkeypatch, tmp_path):
    mod = importlib.import_module("hackagent.cli.commands.examples")

    base = tmp_path / "repo"
    example_dir = base / "examples" / "openai_sdk" / "db_tool_sandbox"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.py").write_text("print('agent')\n", encoding="utf-8")
    (example_dir / "hack.py").write_text("print('hack')\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_get_repo_root", lambda: base)

    resolved = mod._resolve_example_dir(
        "openai_sdk/db_tool_sandbox", required_files=("agent.py", "hack.py")
    )
    assert resolved == example_dir


def test_db_tool_command_runs_and_sets_external_agent_flag(monkeypatch, tmp_path):
    mod = importlib.import_module("hackagent.cli.commands.examples")

    example_dir = tmp_path / "openai_sdk" / "db_tool_sandbox"
    example_dir.mkdir(parents=True)
    agent_script = example_dir / "agent.py"
    attack_script = example_dir / "hack.py"
    agent_script.write_text("print('agent')\n", encoding="utf-8")
    attack_script.write_text("print('hack')\n", encoding="utf-8")

    class _FakeProc:
        def poll(self):
            return None

    calls = {"stop": 0, "wait": 0, "run": 0}

    monkeypatch.setattr(
        mod, "_resolve_example_dir", lambda *args, **kwargs: example_dir
    )
    monkeypatch.setattr(
        mod, "_start_background_python", lambda *args, **kwargs: _FakeProc()
    )

    def _fake_wait(*args, **kwargs):
        calls["wait"] += 1

    def _fake_run(script_path, env=None):
        calls["run"] += 1
        assert Path(script_path) == attack_script
        assert env is not None
        assert env.get("HACKAGENT_DB_TOOL_EXTERNAL_AGENT") == "1"

    def _fake_stop(*args, **kwargs):
        calls["stop"] += 1

    monkeypatch.setattr(mod, "_wait_for_tcp_port", _fake_wait)
    monkeypatch.setattr(mod, "_run_python_script", _fake_run)
    monkeypatch.setattr(mod, "_stop_background_process", _fake_stop)

    runner = CliRunner()
    result = runner.invoke(mod.examples, ["db-tool"])

    assert result.exit_code == 0, result.output
    assert calls == {"stop": 1, "wait": 1, "run": 1}


def test_db_tool_command_stops_process_when_wait_fails(monkeypatch, tmp_path):
    mod = importlib.import_module("hackagent.cli.commands.examples")

    example_dir = tmp_path / "openai_sdk" / "db_tool_sandbox"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.py").write_text("print('agent')\n", encoding="utf-8")
    (example_dir / "hack.py").write_text("print('hack')\n", encoding="utf-8")

    class _FakeProc:
        def poll(self):
            return None

    calls = {"stop": 0}

    monkeypatch.setattr(
        mod, "_resolve_example_dir", lambda *args, **kwargs: example_dir
    )
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
    monkeypatch.setattr(mod, "_run_python_script", lambda *args, **kwargs: None)

    def _fake_stop(*args, **kwargs):
        calls["stop"] += 1

    monkeypatch.setattr(mod, "_stop_background_process", _fake_stop)

    runner = CliRunner()
    result = runner.invoke(mod.examples, ["db-tool"])

    assert result.exit_code != 0
    assert calls["stop"] == 1
