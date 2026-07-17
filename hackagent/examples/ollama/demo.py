# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Minimal h4rm3l demo for an Ollama target model.

Target / Judge:
    gemma3:4b running on Ollama (http://localhost:11434)

Prerequisites:
1. Install Ollama: https://ollama.ai
2. Pull required models:
     ollama pull gemma3:4b
3. Start Ollama:
     ollama serve

Usage:
    python demo.py
    python -m examples.ollama.demo
"""

from pathlib import Path
import sys

try:
    from hackagent import HackAgent
    from hackagent.router.types import AgentTypeEnum
except ModuleNotFoundError:
    # Support direct script execution without requiring editable install.
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from hackagent import HackAgent
    from hackagent.router.types import AgentTypeEnum

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
    """Return the canonical Ollama FlipAttack demo configuration.

    This single source is reused by standalone script execution and CLI/TUI
    entrypoints, so edits here are reflected everywhere.
    """

    return {
        "agent": {
            "name": "ollama-target",
            "endpoint": OLLAMA_ENDPOINT,
            "agent_type": AgentTypeEnum.OLLAMA,
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
                    "agent_type": AgentTypeEnum.OLLAMA,
                    "endpoint": OLLAMA_ENDPOINT,
                }
            ],
        },
    }


def run_ollama_demo() -> object:
    """Execute the Ollama FlipAttack demo and return results."""
    config = build_ollama_demo_config()
    agent = HackAgent(**config["agent"])
    return agent.hack(attack_config=config["attack_config"])


if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"  Running h4rm3l on {TARGET_MODEL}")
    print(f"{'=' * 60}")

    results = run_ollama_demo()

    if not results:
        print("\nNo results returned.")
    else:
        jailbroken = results[0].get("eval_hb", 0)

        print(f"\n{'=' * 60}")
        print(f"  h4rm3l Summary - {TARGET_MODEL}")
        print(f"{'=' * 60}")
        print(f"  Jailbroken      : {jailbroken}")
        print(f"{'=' * 60}\n")
