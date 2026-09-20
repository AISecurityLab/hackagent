# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output indirect prompt injection (InjecAgent / OPI family).

Injects adversarial instructions into simulated (or live) tool observations
so a tool-using agent may follow a malicious goal after a benign user task.
"""

from __future__ import annotations

from .attack import ToolOutputIPIAttack

__all__ = ["ToolOutputIPIAttack"]


def _register_taxonomy_entry() -> None:
    """Register adaptive+indirect when taxonomy module exists (#603).

    ``hackagent.attacks.taxonomy`` is introduced by PR #603
    (``feat/attack-category-taxonomy``). Until that lands on main this is a
    no-op. After #603 merges, prefer adding a permanent line in
    ``ATTACK_TAXONOMY``; this helper remains as a safety net so TUI/CLI
    discovery does not fail if the permanent entry is temporarily missing.
    """
    try:
        from hackagent.attacks.taxonomy import (
            ATTACK_TAXONOMY,
            AttackCategory,
            AttackTag,
            AttackTaxonomy,
            try_get_attack_taxonomy,
        )
    except ImportError:
        return

    if try_get_attack_taxonomy("tool_output_ipi") is not None:
        return

    entry = AttackTaxonomy(
        category=AttackCategory.ADAPTIVE,
        tags=(AttackTag.INDIRECT,),
    )
    # ATTACK_TAXONOMY is declared Mapping but constructed as a plain dict.
    if isinstance(ATTACK_TAXONOMY, dict):
        ATTACK_TAXONOMY["tool_output_ipi"] = entry


_register_taxonomy_entry()
