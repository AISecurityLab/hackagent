# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``build_context`` wires judge, events, workspace and the run sink."""

from uuid import uuid4

import pytest

from hackagent.core.contracts import Sample
from hackagent.evaluation.panel import Panel
from hackagent.orchestrator.execution.context import (
    DEFAULT_JUDGE_AGGREGATION,
    build_context,
)
from hackagent.tracking.tracker import UNKNOWN_CATEGORY, Tracker
from tests.fakes.context import FakeLLMFactory
from tests.fakes.llm import FakeLLM


class _Bus:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def emit(self, event_type, **payload) -> None:
        self.events.append((event_type, payload))


class _OfflineFactory(FakeLLMFactory):
    def for_role(self, spec):
        raise RuntimeError(f"offline: {spec.identifier}")


def _build(tmp_path, **overrides):
    llm = overrides.pop("llm", FakeLLM(default="yes"))
    models = overrides.pop("models", FakeLLMFactory(llm))
    sink = overrides.pop("sink", object())
    bus = overrides.pop("bus", _Bus())
    config = overrides.pop("config", {})
    run_id = overrides.pop("run_id", str(uuid4()))
    target = overrides.pop("target", FakeLLM())
    ctx = build_context(
        run_id=run_id,
        target=target,
        models=models,
        config=config,
        sink=sink,
        attack_type=overrides.pop("attack_type", "baseline"),
        output_dir=str(tmp_path),
        goal_labels=overrides.pop("goal_labels", None),
        event_bus=bus,
    )
    return ctx, llm, sink, bus, target


def test_build_context_wires_a_panel_from_the_judge_config(tmp_path):
    ctx, llm, sink, bus, target = _build(
        tmp_path,
        config={
            "judge": {
                "identifier": "fake-judge",
                "type": "harmbench",
                "system_prompt": "be strict",
            },
            "jailbreak_threshold": 8,
        },
        goal_labels={
            0: {"category": "privacy", "subcategory": "pii"},
            1: {"category": "missing-subcategory"},
        },
    )

    assert ctx.target is target
    assert isinstance(ctx.judge, Panel)
    assert ctx.judge.threshold == 8
    assert getattr(ctx.judge, "available", True) is True
    assert ctx.judge.judges[0].llm is llm
    assert ctx.judge.judges[0].system_prompt == "be strict"
    assert llm.requests == []

    verdict = ctx.judge.evaluate(Sample(goal="g", prompt="p", response="bad"))
    assert verdict.success is True
    assert verdict.score == 10.0
    assert len(llm.requests) == 1
    messages = llm.requests[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "be strict"
    assert "bad" in messages[-1]["content"]

    assert isinstance(ctx.events, Tracker)
    assert ctx.events.sink is sink
    assert ctx.events.run_id == ctx.run_id
    assert ctx.events.attack_type == "baseline"
    assert ctx.events.event_bus is bus
    assert ctx.events._classify_goal_labels("g", 0) == {
        "category": "privacy",
        "subcategory": "pii",
    }
    assert ctx.events._classify_goal_labels("g", 1)["category"] == UNKNOWN_CATEGORY

    ctx.events.log("wired")
    assert bus.events[-1][0] == "log"
    assert bus.events[-1][1]["message"] == "wired"

    assert ctx.workspace.root == tmp_path / ctx.run_id
    nested = ctx.workspace.path("plots", "out.txt")
    assert nested.parent.is_dir()
    cache = ctx.workspace.cache("steps")
    cache["n"] = 1
    assert ctx.workspace.cache("steps")["n"] == 1


def test_build_context_skips_empty_judge_entries_and_ignores_a_bad_threshold(
    tmp_path,
):
    ctx, llm, *_rest = _build(
        tmp_path,
        config={
            "judges": [{}, {"identifier": "fake-judge", "type": "harmbench"}],
            "jailbreak_threshold": "nope",
        },
    )
    assert isinstance(ctx.judge, Panel)
    assert len(ctx.judge.judges) == 1
    assert ctx.judge.judges[0].llm is llm
    assert ctx.judge.threshold == 7.0
    assert ctx.judge.judges[0].threshold == 7.0


def test_a_judge_that_cannot_be_built_fails_instead_of_shrinking_the_panel(
    tmp_path,
):
    with pytest.raises(ValueError, match="missing-identifier"):
        _build(
            tmp_path,
            config={
                "judges": [
                    {"model": "missing-identifier", "type": "harmbench"},
                    {"identifier": "fake-judge", "type": "harmbench"},
                ]
            },
        )


def test_panel_defaults_to_majority_and_reads_judge_aggregation(tmp_path):
    ctx, *_rest = _build(tmp_path, config={"judge": {"identifier": "fake-judge"}})
    assert ctx.judge.aggregation == DEFAULT_JUDGE_AGGREGATION == "majority"

    ctx, *_rest = _build(
        tmp_path,
        config={
            "judge": {"identifier": "fake-judge"},
            "judge_aggregation": " Mean ",
            "jailbreak_threshold": 6,
        },
    )
    assert ctx.judge.aggregation == "mean"
    assert ctx.judge.judges[0].threshold == 6.0


def test_unknown_judge_aggregation_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="judge_aggregation"):
        _build(
            tmp_path,
            config={"judge": {"identifier": "fake-judge"}, "judge_aggregation": "vote"},
        )


def test_judges_of_one_type_get_distinct_names(tmp_path):
    ctx, *_rest = _build(
        tmp_path,
        config={
            "judges": [
                {"identifier": "model-a", "type": "harmbench"},
                {"identifier": "model-b", "type": "harmbench"},
                {"identifier": "model-b", "type": "harmbench"},
                {"identifier": "model-c", "type": "jailbreakbench"},
            ]
        },
    )
    assert [judge.name for judge in ctx.judge.judges] == [
        "harmbench:model-a",
        "harmbench:model-b",
        "harmbench:model-b#2",
        "jailbreakbench",
    ]


def test_missing_judge_config_is_unavailable(tmp_path):
    ctx, llm, *_rest = _build(tmp_path, config={})
    assert ctx.judge.available is False
    assert llm.requests == []
    with pytest.raises(ValueError, match="no judge"):
        ctx.judge.evaluate(Sample(goal="g", response="r"))
    with pytest.raises(ValueError, match="no judge"):
        ctx.judge.score(Sample(goal="g", response="r"))


def test_unconnectable_judge_fails_the_context(tmp_path):
    with pytest.raises(ValueError, match="could not be connected: offline"):
        _build(
            tmp_path,
            models=_OfflineFactory(),
            config={"judge": {"identifier": "fake-judge"}},
        )
