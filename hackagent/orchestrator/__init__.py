# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Composition root (depth 1).

The runner is the only place that wires catalog, attacks, models, storage,
evaluation, datasets and tracking into one run.

- :mod:`~hackagent.orchestrator.execution`: run one attack or a chain,
  batch goals, build the run context
- :mod:`~hackagent.orchestrator.setup`: registry, role defaults, goals,
  preflight
- :mod:`~hackagent.orchestrator.results`: results to storage rows
- :mod:`~hackagent.orchestrator.planning`: the LLM attack planner
"""

from hackagent.orchestrator.execution.chain import hack_chain
from hackagent.orchestrator.setup.registry import ATTACK_REGISTRY, load_attack
from hackagent.orchestrator.execution.spec import RunSpec
from hackagent.orchestrator.execution.runner import run

__all__ = [
    "ATTACK_REGISTRY",
    "RunSpec",
    "hack_chain",
    "load_attack",
    "run",
]
