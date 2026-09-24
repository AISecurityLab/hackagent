# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Composition root (depth 1).

The runner is the only place that wires catalog, attacks, models, storage,
evaluation, datasets and tracking into one run.
"""

from hackagent.orchestrator.chain import hack_chain
from hackagent.orchestrator.registry import ATTACK_REGISTRY, load_attack
from hackagent.orchestrator.run_spec import RunSpec
from hackagent.orchestrator.runner import run

__all__ = [
    "ATTACK_REGISTRY",
    "RunSpec",
    "hack_chain",
    "load_attack",
    "run",
]
