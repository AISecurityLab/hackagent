---
sidebar_position: 1
---

# Python SDK Reference

This section provides detailed documentation for all classes, methods, and functions
in the HackAgent Python SDK, auto-generated from source-code docstrings.

## What's Included

- **Core**: `HackAgent` agent class, errors, and utilities
- **Router**: Adapters for OpenAI, Ollama, LiteLLM, Google ADK, and call tracking
- **Attack Framework**: Base classes, objectives, evaluators, and techniques
  (AdvPrefix, PAIR, TAP, BON, FlipAttack, AutoDAN-Turbo, Baseline).
  The attack seam (`hackagent.attacks.ports`, `AttackConfig`, `BaseAttack`)
  is documented alongside `RunSpec` and `TargetParams`.
  Shared helpers live in `hackagent.attacks._lib` (transforms, scoring,
  templates, objectives, progress, inline-judge adapters, `ensure_graphviz`).
  Every shipped technique constructs as `BaseAttack(config, ctx)`.
  Compatibility shims remain at `attacks.shared`, `attacks.generator`,
  and `attacks.objectives`.
- **Datasets**: Built-in providers and dataset registry
- **Risks**: Risk profiles and vulnerability definitions for all OWASP LLM risk categories

For practical usage examples, see the [Python SDK Quickstart](./sdk/python-quickstart.md).

---

*Auto-generated from hackagent v0.12.0.*
