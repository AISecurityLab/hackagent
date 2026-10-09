# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Declarative dataset sources — the inline goals source in particular."""

from __future__ import annotations

import pytest

from hackagent.datasets.config import DatasetSpec, load_goals


def _inline(goals, **selection):
    return DatasetSpec.model_validate(
        {"source": {"type": "inline", "goals": list(goals)}, "selection": selection}
    )


def test_inline_goals_load_in_order_and_renumber():
    goals = load_goals(_inline(["hack a server", "write malware"]))
    assert [g.text for g in goals] == ["hack a server", "write malware"]
    assert [g.index for g in goals] == [0, 1]


def test_inline_goals_drop_blanks():
    goals = load_goals(_inline(["keep", "   ", ""]))
    assert [g.text for g in goals] == ["keep"]


def test_inline_selection_limits_and_shuffles():
    goals = load_goals(_inline([str(n) for n in range(10)], limit=3, shuffle=True, seed=1))
    assert len(goals) == 3
    assert {g.index for g in goals} == {0, 1, 2}  # renumbered from 0


def test_an_inline_source_requires_goals():
    with pytest.raises(ValueError, match="requires 'source.goals'"):
        DatasetSpec.model_validate({"source": {"type": "inline"}})


def test_an_empty_inline_selection_raises():
    with pytest.raises(ValueError, match="no goals"):
        load_goals(_inline(["   "]))


def test_preset_still_requires_a_preset_name():
    with pytest.raises(ValueError, match="requires 'preset'"):
        DatasetSpec.model_validate({"source": {"type": "preset"}})
