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


def test_eval_page_does_not_claim_cli_json_stdout():
    text = _read("cli", "eval.mdx")
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


def test_bare_install_runs_version_and_help_and_hf_hub_stays_accurate():
    text = _read("getting-started", "installation.mdx")
    assert "`hackagent --version` and `hackagent --help` run from that install" in text
    assert "do not need `[rag]` or `[vision]`" in text
    assert "A bare install does not start the CLI" not in text
    assert "pip install 'hackagent[rag,vision]'" not in text
    assert "| `hf` | Hugging Face `datasets` | 25 of the 26 dataset presets" in text
    assert "pip install 'hackagent[tui]'" in text


def test_quickstart_does_not_require_rag_and_vision_for_version():
    text = _read("getting-started", "quick-start.mdx")
    assert "including `hackagent --version`" not in text
    assert "pip install 'hackagent[rag,vision]'" not in text
    assert "pip install 'hackagent[hf,rag,vision]'" not in text
    assert "pip install 'hackagent[tui,rag,vision]'" not in text
    assert "pip install 'hackagent[hf,rag]'" in text
    assert "pip install 'hackagent[tui]'" in text
    assert "pip install 'hackagent[tui,rag,hf]'" in text


def test_verbosity_flag_comments_match_the_level_table():
    text = _read("cli", "config.md")
    assert "# level 1, WARNING" in text
    assert "# level 2, INFO" in text
    assert "# level 3, DEBUG" in text
    assert "# Verbose (INFO)" not in text
    assert "# More verbose (DEBUG)" not in text
