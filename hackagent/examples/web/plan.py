# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Build a ``web`` target for a URL and let an LLM pick the attack strategy.

Planning is pure LLM reasoning — it does NOT touch the target (the browser only
runs when the chosen plan is executed). The planner defaults to a local Ollama
model (no API key); pull it once with
``ollama pull hf.co/huihui-ai/Huihui-gemma-4-12B-it-qat-q4_0-unquantized-abliterated-GGUF``.

Usage:
    python plan.py https://www.example.com
"""

import json
import sys

from hackagent.router.discovery import auto_plan, build_web_target


def main(argv):
    if len(argv) != 2:
        print("usage: python plan.py <website-url>", file=sys.stderr)
        return 2

    url = argv[1]
    agent_type, config = build_web_target(url)
    print("Router-ready target:")
    print(f"  agent_type = {agent_type!r}")
    print(json.dumps(config, indent=2))
    print()

    result = auto_plan(url)
    if result.plan is None:
        print("No plan was produced.")
        return 1
    print(result.plan.summary())
    print()
    print("attack_config:", json.dumps(result.plan.to_attack_config(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
