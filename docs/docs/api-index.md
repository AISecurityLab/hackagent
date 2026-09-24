---
sidebar_position: 1
---

# Python SDK Reference

This section provides detailed documentation for all classes, methods, and functions
in the HackAgent Python SDK, auto-generated from source-code docstrings.

## What's Included

- **Client**: Depth-2 `hackagent.client`. `HackAgent(Settings)` does not
  take a target. `.target(...).hack()` and `.hack_chain()` both take
  `on_event`. Reads, `catalog`, `presets`, `plan_attack`, `doctor`, and
  `check_connection` live on the session.
- **Interfaces**: Depth-3 `hackagent.interfaces` (CLI, TUI, web). They talk
  only to the facade. TUI forms come from technique JSON schema. The web UI
  is `hackagent.interfaces.web`.
- **Core**: Settings, contracts, errors, and utilities
- **Evaluation**: Depth-0 `hackagent.evaluation`. `Panel` scores a `Sample`
  into a `Verdict`. Judges, pattern evaluators, and verdict metrics live here.
- **Tracking**: Depth-0 `hackagent.tracking`. `Tracker` implements the
  `Events` port and writes through `RunSink`.
- **Orchestrator**: Depth-1 `hackagent.orchestrator`. `run(RunSpec)` and
  `hack_chain` compose one attack. `mapping` owns record `eval_*` columns.
  `AttackOrchestrator` and `hackagent.attacks.registry` are gone; there is
  no import shim.
- **Attack Framework**: Base classes, objectives, and techniques
  (AdvPrefix, PAIR, TAP, BON, FlipAttack, AutoDAN-Turbo, Baseline).
  The attack seam (`hackagent.attacks.ports`, `AttackConfig`, `BaseAttack`)
  is documented alongside `RunSpec` and `TargetParams`.
  Shared helpers live in `hackagent.attacks._lib` (transforms, scoring,
  templates, objectives, progress, inline-judge adapters, `ensure_graphviz`).
  Every shipped technique constructs as `BaseAttack(config, ctx)`.
  Private modules are omitted from these pages: `storage._http` and
  `attacks._lib.legacy_seams`.
- **Datasets**: Built-in providers and dataset registry
- **Risks**: Risk profiles and vulnerability definitions for all OWASP LLM risk categories

For practical usage examples, see the [Python SDK Quickstart](./sdk/python-quickstart.md).

---

*Auto-generated from hackagent v0.12.0.*
