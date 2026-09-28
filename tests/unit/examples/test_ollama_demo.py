# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Ollama example is a headless h4rm3l run through the client facade."""

import importlib.util
import inspect
from pathlib import Path

from hackagent.attacks.techniques.static.h4rm3l.decorators import (
    program_uses_llm_assisted_decorators,
)

_ROOT = Path(__file__).resolve().parents[3]
_DEMO_PATH = _ROOT / "hackagent" / "examples" / "ollama" / "demo.py"


def _load_demo():
    spec = importlib.util.spec_from_file_location("ollama_demo_under_test", _DEMO_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_config_is_h4rm3l_on_harmbench_without_an_attacker():
    demo = _load_demo()
    config = demo.build_ollama_demo_config()
    attack = config["attack_config"]

    assert attack["attack_type"] == "h4rm3l"
    assert attack["dataset"]["preset"] == "harmbench"
    assert "attacker" not in attack
    program = attack["h4rm3l_params"]["program"]
    assert (
        program_uses_llm_assisted_decorators(
            program, attack["h4rm3l_params"]["syntax_version"]
        )
        is False
    )
    assert attack["judges"][0]["type"] == "harmbench_variant"
    assert attack["judges"][0]["identifier"] == "gemma3:4b"
    assert config["agent"]["adapter_operational_config"]["name"] == "gemma3:4b"


def test_run_ollama_demo_uses_settings_target_and_hack(monkeypatch):
    demo = _load_demo()
    resolved = object()
    seen = {}

    class Session:
        def __init__(self, settings=None, **kwargs):
            seen["settings"] = settings

        def target(self, endpoint, agent_type, **kwargs):
            seen["endpoint"] = endpoint
            seen["agent_type"] = agent_type
            seen["target_kwargs"] = kwargs
            return self

        def hack(self, attack_config):
            seen["attack_type"] = attack_config["attack_type"]
            return [{"goal": "g", "success": True}, {"goal": "h", "success": False}]

        def close(self):
            seen["closed"] = True

    monkeypatch.setattr(demo, "HackAgent", Session)
    monkeypatch.setattr(demo.Settings, "resolve", classmethod(lambda cls: resolved))

    results = demo.run_ollama_demo()

    assert seen["settings"] is resolved
    assert seen["endpoint"] == "http://localhost:11434"
    assert seen["target_kwargs"]["name"] == "ollama-target"
    assert seen["target_kwargs"]["adapter_operational_config"]["name"] == "gemma3:4b"
    assert seen["attack_type"] == "h4rm3l"
    assert seen["closed"] is True
    assert results[0]["success"] is True
    source = inspect.getsource(demo.run_ollama_demo)
    assert "HackAgent(**" not in source
    assert ".target(" in source
    assert ".hack(" in source


def test_tui_and_ollama_example_are_separate_entrypoints():
    examples = (
        _ROOT / "hackagent" / "interfaces" / "cli" / "commands" / "examples.py"
    ).read_text(encoding="utf-8")
    ollama_fn = examples.split("def ollama(", 1)[1].split("\ndef ", 1)[0]
    assert "run_ollama_demo" in ollama_fn
    assert "HackAgentTUI" not in ollama_fn
    assert "launch_tui" not in ollama_fn
    main = (_ROOT / "hackagent" / "interfaces" / "cli" / "main.py").read_text(
        encoding="utf-8"
    )
    tui_fn = main.split("def tui(", 1)[1].split("\ndef ", 1)[0]
    assert "HackAgentTUI" in tui_fn
    bootstrap = (_ROOT / "hackagent" / "interfaces" / "cli" / "bootstrap.py").read_text(
        encoding="utf-8"
    )
    assert "HackAgentTUI" in bootstrap.split("def _launch_tui_default(", 1)[1]
