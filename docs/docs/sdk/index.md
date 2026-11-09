---
title: "Python SDK"
description: "Run campaigns and read results from Python, and the module reference generated from the docstrings."
sidebar_label: "Overview"
---

# Python SDK

The `hackagent` package is what the CLI, the terminal app and the dashboard
are built on. Use it from Python when a campaign is one step of something
larger: a test suite, a CI job, a notebook.

- **Guides** show how to do common tasks from Python, starting with the
  [Quickstart](./guides/quickstart.mdx).
- **Reference** documents every public module, generated from the source
  docstrings on every docs build, so it always matches the code.

## What is in the package

- **Client**: `hackagent.client`. `HackAgent(Settings)` reads what past runs
  recorded (campaigns, runs, results, agents) and carries the catalogs,
  `presets`, `plan_attack`, `doctor` and `check_connection`.
- **Orchestrator**: `hackagent.orchestrator`. `run_campaign(spec)` is the only
  way an attack runs: it resolves the goals, models and judges, then drives
  every attack over every goal.
- **Attacks**: `hackagent.attacks`. The base classes `StaticAttack` and
  `IterativeAttack`, each attack's parameter model, and the registry a
  campaign resolves attack names through.
- **Evaluation**: `hackagent.evaluation`. `Panel` scores a `Sample` into a
  `Verdict`; judges, pattern evaluators and verdict metrics live here.
- **Tracking**: `hackagent.tracking`. `Tracker` records every step of a run
  and writes it through a `RunSink`.
- **Reporting**: `hackagent.reporting`. Turns stored results into the run
  reports the dashboard shows.
- **Models, Datasets, Catalog, Storage, Core, Interfaces**: model
  connections, goal sources, the attack and risk catalogs, local and remote
  result storage, settings and contracts, and the CLI, terminal app and web
  interface.

Private modules are left out of the reference: `storage._http` and
`attacks._lib.legacy_seams`.

For the campaign format itself, see [Campaign files](../cli/campaign-files/index.md).
For what each attack does, see [Attacks](../attacks/index.mdx).
