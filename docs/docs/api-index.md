# Python SDK Reference

This section provides detailed documentation for all classes, methods, and functions
in the HackAgent Python SDK, auto-generated from source-code docstrings.

## What's Included

- **Client**: Depth-2 `hackagent.client`. `HackAgent(Settings)` reads what
  past runs recorded — campaigns, runs, results, agents — and carries the
  catalogs, `presets`, `plan_attack`, `doctor` and `check_connection`.
  Running an attack is a campaign: `hackagent.orchestrator.campaign.run_campaign`.
- **Interfaces**: Depth-3 `hackagent.interfaces` (CLI, TUI, web). They talk
  only to the facade. The web UI is `hackagent.interfaces.web`.
- **Core**: Settings, contracts, errors, and utilities
- **Evaluation**: Depth-0 `hackagent.evaluation`. `Panel` scores a `Sample`
  into a `Verdict`. Judges, pattern evaluators, and verdict metrics live here.
- **Tracking**: Depth-0 `hackagent.tracking`. `Tracker` implements the
  `Events` port and writes through `RunSink`.
- **Orchestrator**: Depth-1 `hackagent.orchestrator`. `run_campaign(spec)` is
  the only way an attack runs: it resolves the goals, models and judges, then
  drives every attack over every goal.
- **Attack Framework**: Base classes, objectives, and techniques
  (AdvPrefix, PAIR, TAP, BON, FlipAttack, AutoDAN-Turbo, Baseline).
  The attack seam is `hackagent.attacks.techniques`: `StaticAttack` and
  `IterativeAttack`, each attack's parameter model (its roles and
  defaults), and the `registry` a campaign resolves names through.
  Shared helpers live in `hackagent.attacks._lib` (transforms, scoring,
  templates, progress, inline-judge adapters, `ensure_graphviz`).
  Every shipped technique constructs as `BaseAttack(config, ctx)`.
  Private modules are omitted from these pages: `storage._http` and
  `attacks._lib.legacy_seams`.
- **Datasets**: Built-in providers and dataset registry
- **Risks**: Risk profiles and vulnerability definitions for all OWASP LLM risk categories

For a worked example, see [Your first campaign](./getting-started/first-campaign.md); for the campaign format itself, see the [Campaign reference](./reference/index.md).

---

*Auto-generated from hackagent v0.12.0.*
