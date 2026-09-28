# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Hand-written docs stay aligned with the P0 first-run claims."""

from pathlib import Path

_DOCS = Path(__file__).resolve().parents[3] / "docs" / "docs"


def _read(*parts: str) -> str:
    return (_DOCS.joinpath(*parts)).read_text(encoding="utf-8")


def test_config_page_ranks_environment_above_the_file():
    text = _read("cli", "config.md")
    assert "2. **Config file**" not in text
    assert "args → env → file → defaults" in text
    assert "Verbosity." in text
    assert "Ollama fields are env-only." in text
    assert "HACKAGENT_DB_PATH" in text


def test_attack_page_does_not_claim_cli_json_stdout():
    text = _read("cli", "attack.mdx")
    assert "> results.json" not in text
    assert "> test_results.json" not in text
    assert "json.dump" in text
    assert "not a JSON document" in text


def test_quickstart_splits_tui_and_ollama_example():
    text = _read("getting-started", "quick-start.mdx")
    assert "FlipAttack TUI" in text
    assert "not a FlipAttack TUI" in text
    assert "headless h4rm3l" in text
    assert "Settings.resolve()" in text
    assert "hackagent tui" in text
    assert "hackagent examples ollama" in text
    assert "hackagent[hf,rag]" in text
    assert "hackagent[tui]" in text
    assert "harmbench_variant" in text
    assert "does not call `hackagent/examples/ollama/demo.py`" in text


def test_bare_install_does_not_start_the_cli_and_hf_hub_stays_accurate():
    text = _read("getting-started", "installation.mdx")
    assert "A bare install does not start the CLI" in text
    assert "enough for the SDK, the CLI" not in text
    assert "Hugging Face `datasets`, for presets and Hub datasets" in text
