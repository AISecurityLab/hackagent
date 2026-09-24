# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack techniques module.

Techniques define HOW we generate attacks. Each technique is a complete
implementation that can target different objectives.

Techniques are grouped by category, the same grouping the docs use:

- static/: fixed transforms, no attacker refinement loop (baseline,
  static_template, flipattack, cipherchat, h4rm3l, mml, fc/tfc)
- adaptive/: independent attempts that refine or search (pair, tap, pap,
  bon, advprefix, autodan_turbo)
- multi_turn/: one growing conversation with the target (crescendo)
- indirect/: payload delivered through retrieved content or tool output
  (rag, tool_output_ipi)

The folder follows :mod:`hackagent.catalog.taxonomy`: the ``indirect`` tag
decides first, otherwise the primary category does.

Architecture pattern for a technique package:
    1. attack.py - Main BaseAttack subclass
    2. config.py - Default configuration + dataclasses
    3. generation.py - Attack generation/execution logic
    4. [other].py - Additional pipeline stages as needed

The orchestrator loads a technique with ``load_attack`` and runs it as
``BaseAttack(config, ctx)``.
"""

__all__ = []
