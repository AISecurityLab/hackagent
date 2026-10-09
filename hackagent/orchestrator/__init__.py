# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Composition root (depth 1).

The runner is the only place that wires catalog, attacks, models, storage,
evaluation, datasets and tracking into one run.

- :mod:`~hackagent.orchestrator.chain`: the escalating attack chain
- :mod:`~hackagent.orchestrator.planning`: the LLM attack planner
"""

from hackagent.orchestrator.chain import hack_chain

__all__ = [
    "hack_chain",
]
