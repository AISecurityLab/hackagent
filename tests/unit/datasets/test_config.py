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


def test_range_is_exclusive_and_precedes_shuffle_and_limit():
    goals = load_goals(
        _inline(
            [str(n) for n in range(10)], start=3, end=7, shuffle=True, seed=2, limit=2
        )
    )
    assert len(goals) == 2
    assert {g.text for g in goals} <= {"3", "4", "5", "6"}
    assert [g.index for g in goals] == [0, 1]


@pytest.mark.parametrize(
    "selection", [{"start": -1}, {"start": 3, "end": 3}, {"start": 4, "end": 2}]
)
def test_invalid_ranges_are_rejected(selection):
    with pytest.raises(ValueError):
        _inline(["a", "b"], **selection)


def test_range_past_the_dataset_is_an_empty_selection():
    with pytest.raises(ValueError, match="no goals"):
        load_goals(_inline(["a"], start=2))


def test_provider_range_keeps_metadata_aligned(monkeypatch):
    import hackagent.datasets.config as config

    calls = []

    def load(provider_config):
        calls.append(provider_config)
        return ["a", "b", "c", "d"], {i: {"row": i} for i in range(4)}

    monkeypatch.setattr(config, "load_goals_and_extra_fields_from_config", load)
    spec = DatasetSpec.model_validate(
        {
            "source": {"type": "preset", "name": "harmbench"},
            "selection": {"start": 1, "end": 3, "limit": 1},
        }
    )
    goals = load_goals(spec)
    assert calls == [{"preset": "harmbench"}]
    assert [(goal.text, goal.index, goal.extra) for goal in goals] == [
        ("b", 0, {"row": 1})
    ]


def test_category_filter_precedes_range():
    from hackagent.core.contracts import Goal
    from hackagent.datasets.config import DatasetSelection, select_goals

    goals = [
        Goal(text=str(i), index=i, labels={"category": "E" if i % 2 else "A"})
        for i in range(6)
    ]
    selected = select_goals(
        goals, DatasetSelection(start=1, end=3, filters={"categories": ["E"]})
    )
    assert [goal.text for goal in selected] == ["3", "5"]
    assert [goal.index for goal in selected] == [0, 1]


def test_a_range_past_the_matching_goals_says_so():
    from hackagent.core.contracts import Goal
    from hackagent.datasets.config import DatasetSelection, select_goals

    goals = [Goal(text=str(i), index=i, labels={"category": "E"}) for i in range(2)]
    with pytest.raises(ValueError, match=r"range 2 to the end is past the 2 goal"):
        select_goals(goals, DatasetSelection(start=2, filters={"categories": ["E"]}))


def test_no_matching_goal_names_the_categories_not_the_range():
    from hackagent.core.contracts import Goal
    from hackagent.datasets.config import DatasetSelection, select_goals

    goals = [Goal(text=str(i), index=i, labels={"category": "A"}) for i in range(2)]
    with pytest.raises(ValueError, match=r"No goal is labelled with any of \['E'\]"):
        select_goals(goals, DatasetSelection(start=5, filters={"categories": ["E"]}))


def test_bundled_intents_load_without_dataset_provider(monkeypatch):
    from hackagent.datasets.intents import intent_catalog, intents_of

    def unavailable(*args, **kwargs):
        raise AssertionError("A bundled source must not load an external provider")

    monkeypatch.setattr(
        "hackagent.datasets.config.load_goals_and_extra_fields_from_config", unavailable
    )
    spec = DatasetSpec.model_validate(
        {
            "source": {
                "type": "intents",
                "selections": [
                    {
                        "category": "Cybersecurity Threats",
                        "subcategories": ["E2"],
                        "samples_per_subcategory": 3,
                    },
                    {"category": "B", "subcategories": ["B1"]},
                ],
            },
            "selection": {"start": 1, "end": 4, "shuffle": True, "seed": 2},
        }
    )
    goals = load_goals(spec)
    assert len(goals) == 3
    assert [goal.index for goal in goals] == [0, 1, 2]
    for goal in goals:
        code = goal.labels["subcategory"].split(".")[0]
        assert goal.text in intents_of(code)
    assert {goal.labels["subcategory"].split(".")[0] for goal in goals} == {"E2", "B1"}
    catalog = intent_catalog()
    assert len(catalog) == 10
    assert all(
        sub["count"] == len(intents_of(sub["code"])) > 0
        for category in catalog
        for sub in category["subcategories"]
    )


def test_bundled_intents_category_defaults_and_label_filter():
    from hackagent.datasets.config import select_goals
    from hackagent.datasets import taxonomy
    from hackagent.orchestrator.campaign.spec import (
        CampaignDatasetSpec,
        campaign_json_schema,
    )

    spec = CampaignDatasetSpec.model_validate(
        {
            "source": {"selections": [{"category": "A"}]},
            "selection": {"filters": {"categories": ["A2"]}},
        }
    )
    assert spec.classifier is None
    assert len(load_goals(spec)) == len(taxonomy.subcategories("A"))
    goals = select_goals(load_goals(spec), spec.selection)
    assert len(goals) == 1
    assert goals[0].labels == taxonomy.labels("A2")
    assert campaign_json_schema()["x-hackagent-intent-categories"][0]["code"] == "A"


@pytest.mark.parametrize(
    "selections",
    [
        [],
        [{"category": "unknown"}],
        [{"category": "A", "subcategories": []}],
        [{"category": "A", "subcategories": ["B1"]}],
        [{"category": "A", "subcategories": ["A1", "Bias and Discrimination"]}],
        [{"category": "A"}, {"category": "Ethical and Social Risks"}],
    ]
    + [
        [{"category": "A", "samples_per_subcategory": count}]
        for count in [0, -1, 1.5, True]
    ],
)
def test_invalid_bundled_intent_selections(selections):
    with pytest.raises(ValueError):
        DatasetSpec.model_validate(
            {"source": {"type": "intents", "selections": selections}}
        )
