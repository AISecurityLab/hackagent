# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Minimal h4rm3l demo for an Ollama target model.

Target / Judge:
    gemma3:4b running on Ollama (http://localhost:11434)

The decorator program does not call an attacker model.

Prerequisites:
1. ``pip install 'hackagent[hf,rag]'`` — HarmBench is a Hub dataset, and
   h4rm3l imports NumPy from the ``rag`` extra. The TUI extra is not required.
2. Install Ollama: https://ollama.ai
3. Pull the target and judge model:
     ollama pull gemma3:4b
4. Start Ollama:
     ollama serve

Usage:
    python hackagent/examples/ollama/demo.py
    hackagent examples ollama

``hackagent examples ollama`` runs this demo headless. It does not open the
terminal UI. ``hackagent`` and ``hackagent tui`` are a separate path.
"""

from pathlib import Path
import sys

try:
    from hackagent import HackAgent, Settings
    from hackagent.core.contracts import AgentType
except ModuleNotFoundError:
    # Support direct script execution without requiring editable install.
    # hackagent/examples/ollama/demo.py → repo root is parents[3].
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from hackagent import HackAgent, Settings
    from hackagent.core.contracts import AgentType

# ---------------------------------------------------------------------------
# Target agent (victim)
# ---------------------------------------------------------------------------
TARGET_MODEL = "gemma3:4b"
OLLAMA_ENDPOINT = "http://localhost:11434"
JUDGE_MODEL = "gemma3:4b"
# ---------------------------------------------------------------------------
# Small benchmark slice for a quick demo run
# ---------------------------------------------------------------------------
DATASET = {
    "preset": "harmbench",
    "limit": 5,
    "shuffle": False,
    "seed": 42,
}


def build_ollama_demo_config() -> dict:
    """Return the canonical Ollama h4rm3l demo configuration.

    The standalone script and ``hackagent examples ollama`` both call this.
    The terminal UI does not.
    """

    return {
        "agent": {
            "name": "ollama-target",
            "endpoint": OLLAMA_ENDPOINT,
            "agent_type": AgentType.OLLAMA,
            "adapter_operational_config": {
                "name": TARGET_MODEL,
            },
        },
        "attack_config": {
            "attack_type": "h4rm3l",
            "dataset": DATASET,
            "goal_batch_size": 1,
            "goal_batch_workers": 1,
            "max_tokens": 400,
            "h4rm3l_params": {
                "program": (
                    "DANDecorator().then(RefusalSuppressionDecorator())"
                    ".then(StyleInjectionShortDecorator())"
                ),
                "syntax_version": 2,
            },
            "judges": [
                {
                    "identifier": JUDGE_MODEL,
                    "type": "harmbench_variant",
                    "agent_type": AgentType.OLLAMA,
                    "endpoint": OLLAMA_ENDPOINT,
                }
            ],
        },
    }


def run_ollama_demo() -> object:
    """Run the Ollama h4rm3l demo through the client facade.

    Settings come from :meth:`Settings.resolve`. The victim is bound with
    :meth:`HackAgent.target`. The attack runs with :meth:`Target.hack`.
    """
    config = build_ollama_demo_config()
    agent_cfg = config["agent"]
    session = HackAgent(Settings.resolve())
    try:
        target = session.target(
            agent_cfg["endpoint"],
            agent_cfg["agent_type"],
            name=agent_cfg.get("name"),
            adapter_operational_config=agent_cfg.get("adapter_operational_config"),
        )
        return target.hack(attack_config=config["attack_config"])
    finally:
        session.close()


if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"  Running h4rm3l on {TARGET_MODEL}")
    print(f"{'=' * 60}")

    results = run_ollama_demo()
    rows = results if isinstance(results, list) else []
    successes = sum(
        1 for row in rows if isinstance(row, dict) and row.get("success") is True
    )

    print(f"\n{'=' * 60}")
    print(f"  h4rm3l Summary - {TARGET_MODEL}")
    print(f"{'=' * 60}")
    print(f"  Goals tested    : {len(rows)}")
    print(f"  Successful      : {successes}")
    print(f"{'=' * 60}\n")
