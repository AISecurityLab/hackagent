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
    goals = load_goals(
        _inline([str(n) for n in range(10)], limit=3, shuffle=True, seed=1)
    )
    assert len(goals) == 3
    assert {g.index for g in goals} == {0, 1, 2}  # renumbered from 0


def test_an_inline_source_requires_goals():
    # The variant declares `goals`, so the error names that field directly.
    with pytest.raises(ValueError, match="source.inline.goals"):
        DatasetSpec.model_validate({"source": {"type": "inline"}})


def test_an_empty_inline_selection_raises():
    with pytest.raises(ValueError, match="no goals"):
        load_goals(_inline(["   "]))


def test_preset_still_requires_a_preset_name():
    with pytest.raises(ValueError, match="source.preset.name"):
        DatasetSpec.model_validate({"source": {"type": "preset"}})


def test_the_older_preset_field_name_still_loads():
    """`type: preset` already says what it is, so the field is now `name`."""
    spec = DatasetSpec.model_validate(
        {"source": {"type": "preset", "preset": "xstest"}}
    )
    assert spec.source.name == "xstest"


def test_a_field_from_another_source_type_is_rejected():
    """The whole point of the split: an inline source has no `preset`."""
    with pytest.raises(ValueError, match="preset"):
        DatasetSpec.model_validate(
            {"source": {"type": "inline", "goals": ["g"], "preset": "harmbench"}}
        )


def test_the_older_top_level_preset_still_loads():
    """Campaign files that named the preset beside the source keep working."""
    spec = DatasetSpec.model_validate({"preset": "harmbench"})
    assert spec.preset == "harmbench"
    assert spec.source.type == "preset"


def test_a_source_without_a_tag_is_read_rather_than_refused():
    """The fields present say which kind of source it is."""
    assert (
        type(
            DatasetSpec.model_validate({"source": {"name": "harmbench"}}).source
        ).__name__
        == "PresetSource"
    )
    assert (
        type(DatasetSpec.model_validate({"source": {"goals": ["g"]}}).source).__name__
        == "InlineSource"
    )
    assert (
        type(
            DatasetSpec.model_validate(
                {"source": {"provider": "file", "path": "x"}}
            ).source
        ).__name__
        == "ProviderSource"
    )
