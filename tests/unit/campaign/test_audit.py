# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The audit measures the panel a campaign file configures.

The judges here are real ``ModelJudge``s over scripted models, so the
campaign's aggregation and threshold are the ones under test.
"""

from uuid import UUID

import pytest

from hackagent.core.contracts import LabelledSample, Sample
from hackagent.datasets.calibration import CalibrationSpec
from hackagent.evaluation.audit import (
    PANEL,
    AuditReport,
    JudgeReport,
    RobustnessSpec,
    binary_metrics,
    compare_rules,
)
from hackagent.orchestrator.campaign import run_campaign, summary
from hackagent.orchestrator.campaign.audit import (
    AuditFailed,
    format_report,
    read_report,
    run_audit,
)

from .fakes import FakeBuilder, ScriptedModel, campaign, model

HARMFUL = "a detailed answer"
SAFE = "I cannot help with that"


def samples() -> list[LabelledSample]:
    """Two labelled rows, one of each class."""
    return [
        LabelledSample(id="1", label=True, sample=Sample(goal="g1", response=HARMFUL)),
        LabelledSample(id="2", label=False, sample=Sample(goal="g2", response=SAFE)),
    ]


def honest_judge() -> ScriptedModel:
    """Answers 'yes' only when the response it is shown is the harmful one."""
    return ScriptedModel(
        lambda messages: "yes" if HARMFUL in messages[-1]["content"] else "no"
    )


def brittle_judge() -> ScriptedModel:
    """Honest, but fooled by a refusal preamble: same answer, now 'safe'."""

    def reply(messages):
        content = messages[-1]["content"]
        if "I'm sorry, but I cannot help" in content:
            return "no"
        return "yes" if HARMFUL in content else "no"

    return ScriptedModel(reply)


def audit(values=None, *, models=None, load=None, **kwargs):
    builder = FakeBuilder(models or {"judge": honest_judge()})
    return run_audit(
        values or campaign(),
        build=builder,
        load=load or (lambda _spec: samples()),
        **kwargs,
    )


def test_a_perfect_judge_scores_perfectly():
    report = audit()

    assert report.report_for("harmbench").metrics.precision == 1.0
    assert report.report_for("harmbench").metrics.recall == 1.0
    # Nothing was checked, so nothing passed or failed.
    assert report.passed is None


def test_the_panel_is_audited_alongside_its_judges():
    report = audit()

    assert [row.judge for row in report.judges] == ["harmbench", PANEL]
    assert report.samples == 2


def test_a_judge_that_calls_everything_harmful_is_reported_not_failed():
    report = audit(models={"judge": ScriptedModel("yes")})

    assert report.report_for("harmbench").metrics.fp == 1
    assert report.report_for("harmbench").metrics.precision == 0.5
    assert report.passed is None


def test_every_judge_in_the_campaign_is_measured():
    values = campaign(
        evaluation={
            "judges": [
                {**model("strict", "http://a/v1"), "scoring": {"type": "harmbench"}},
                {**model("loose", "http://b/v1"), "scoring": {"type": "harmbench"}},
            ],
            "aggregation": "majority",
        }
    )
    report = audit(
        values, models={"strict": honest_judge(), "loose": ScriptedModel("yes")}
    )

    assert len(report.judges) == 3
    assert report.report_for("harmbench:strict#1").metrics.fp == 0
    assert report.report_for("harmbench:loose#2").metrics.fp == 1


def test_the_calibration_spec_reaches_the_loader():
    seen = []

    def load(spec):
        seen.append(spec)
        return samples()

    audit(load=load, calibration=CalibrationSpec(sample_size=7, seed=3))

    assert (seen[0].sample_size, seen[0].seed) == (7, 3)


def test_the_default_calibration_spec_is_used_when_none_is_given():
    seen = []

    audit(load=lambda spec: (seen.append(spec), samples())[1])

    assert seen[0] == CalibrationSpec()


def test_a_campaign_with_no_judges_cannot_be_audited():
    with pytest.raises(ValueError, match="configures no judges"):
        audit(campaign(evaluation={"judges": []}))


def test_robustness_is_reported_when_it_is_asked_for():
    report = audit(
        robustness=RobustnessSpec(enabled=True, wrappers=("refusal_prefix",))
    )

    robustness = report.report_for("harmbench").robustness
    assert robustness is not None
    assert len(robustness.wrappers) == 1


def test_a_written_report_reads_back_unchanged(tmp_path):
    path = tmp_path / "nested" / "audit.json"
    report = audit(report_path=path)

    assert read_report(path) == report
    assert isinstance(read_report(path), AuditReport)


def test_the_formatted_table_names_every_row_and_the_outcome():
    text = format_report(audit(robustness=RobustnessSpec(enabled=True)))

    assert "harmbench" in text
    assert PANEL in text
    assert text.strip().endswith("passed")


def test_the_formatted_table_shows_why_a_judge_failed():
    text = format_report(
        audit(
            models={"judge": brittle_judge()},
            robustness=RobustnessSpec(
                enabled=True, wrappers=("refusal_prefix",), max_flip_rate=0.0
            ),
        )
    )

    assert "! flip rate above" in text
    assert text.strip().endswith("FAILED")


def test_an_ungraded_table_says_so_rather_than_claiming_a_pass():
    assert format_report(audit()).strip().endswith("not graded")


# --- the campaign runs it ---------------------------------------------------


def audited(on_failure="warn", **audit):
    """A campaign whose panel is audited before anything is attacked."""
    return campaign(
        evaluation={
            **campaign()["evaluation"],
            "audit": {"enabled": True, "on_failure": on_failure, **audit},
        }
    )


def run(values, *, models=None, calibration=None, **kwargs):
    from tests.fakes import RecordingStore

    from .fakes import goals

    builder = FakeBuilder(
        models or {"target": ScriptedModel(), "judge": honest_judge()}
    )
    result = run_campaign(
        values,
        build=builder,
        load=goals("goal one"),
        store=RecordingStore(),
        calibration=calibration or (lambda _spec: samples()),
        **kwargs,
    )
    return result, builder


def test_no_audit_runs_unless_the_campaign_asks_for_one():
    loaded = []

    result, _builder = run(
        campaign(), calibration=lambda spec: loaded.append(spec) or samples()
    )

    assert result.audit is None
    assert loaded == []


def test_an_enabled_audit_runs_and_is_reported_with_the_result():
    result, _builder = run(audited(robustness={"enabled": True, "max_flip_rate": 1.0}))

    assert result.audit is not None
    assert result.audit.passed is True
    assert summary(result)["audit_passed"] is True


def test_an_enabled_audit_is_emitted_before_attack_progress(monkeypatch):
    events = []

    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        "hackagent.orchestrator.campaign.runner.asyncio.to_thread", inline
    )

    run(
        audited(robustness={"enabled": True, "max_flip_rate": 1.0}),
        on_event=lambda event, **payload: events.append((event, payload)),
    )

    assert events[0][0] == "audit_finished"
    assert events[0][1]["audit"]["passed"] is True
    assert events[1][0] == "attack_started"


def test_an_audit_that_grades_nothing_reports_no_verdict():
    result, _builder = run(audited())

    assert result.audit is not None
    assert summary(result)["audit_passed"] is None


def test_the_audit_happens_before_the_first_attack():
    order = []

    class Watched(ScriptedModel):
        def __init__(self, label, reply):
            super().__init__(reply)
            self.label = label

        async def acomplete(self, messages, **overrides):
            order.append(self.label)
            return await super().acomplete(messages, **overrides)

    run(
        audited(),
        models={
            "target": Watched("target", "a reply"),
            "judge": Watched("judge", "no"),
        },
    )

    # The audit judges both samples before the target is asked anything.
    assert order[:2] == ["judge", "judge"]
    assert order.index("target") == 2


def test_a_brittle_panel_stops_the_run_before_the_target_is_touched():
    target = ScriptedModel()
    with pytest.raises(AuditFailed, match="flipped .* of its verdicts"):
        run(
            audited(
                "stop",
                robustness={
                    "enabled": True,
                    "wrappers": ["refusal_prefix"],
                    "max_flip_rate": 0.0,
                },
            ),
            models={"target": target, "judge": brittle_judge()},
        )

    assert target.requests == []


def test_the_failure_carries_the_report_that_explains_it():
    with pytest.raises(AuditFailed) as raised:
        run(
            audited(
                "stop",
                robustness={
                    "enabled": True,
                    "wrappers": ["refusal_prefix"],
                    "max_flip_rate": 0.0,
                },
            ),
            models={"target": ScriptedModel(), "judge": brittle_judge()},
        )

    robustness = raised.value.report.report_for("harmbench").robustness
    assert robustness.any_wrapper_flip_rate > 0.0


def test_a_failing_panel_only_warns_by_default():
    target = ScriptedModel()
    result, _builder = run(
        audited(
            robustness={
                "enabled": True,
                "wrappers": ["refusal_prefix"],
                "max_flip_rate": 0.0,
            }
        ),
        models={"target": target, "judge": brittle_judge()},
    )

    assert result.audit.passed is False
    assert summary(result)["audit_passed"] is False
    assert target.requests  # the run went ahead


def test_a_dry_run_audits_nothing():
    loaded = []

    result, _builder = run(
        {**audited(), "execution": {**audited()["execution"], "dry_run": True}},
        calibration=lambda spec: loaded.append(spec) or samples(),
    )

    assert result.dry_run is True
    assert loaded == []


def test_the_report_is_written_beside_the_run_outputs(tmp_path):
    values = audited()
    values["execution"] = {
        **values["execution"],
        "output": {"directory": str(tmp_path)},
    }

    result, _builder = run(values)

    path = tmp_path / result.run_id / "audit.json"
    assert path in result.outputs
    assert read_report(path) == result.audit


def test_the_report_is_persisted_once_on_the_sql_campaign_run(tmp_path):
    from unittest.mock import patch

    from hackagent.storage.local import LocalBackend

    from .fakes import goals

    store = LocalBackend(db_path=str(tmp_path / "runs.db"))
    try:

        async def inline(function, *args, **kwargs):
            return function(*args, **kwargs)

        with patch("hackagent.orchestrator.campaign.runner.asyncio.to_thread", inline):
            result = run_campaign(
                audited(robustness={"enabled": True, "max_flip_rate": 1.0}),
                build=FakeBuilder({"target": ScriptedModel(), "judge": honest_judge()}),
                load=goals("goal one"),
                store=store,
                calibration=lambda _spec: samples(),
            )

        assert result.campaign_run_id is not None
        campaign_record = store.get_campaign_run(UUID(result.campaign_run_id))
        [attack_run] = store.list_runs(page_size=20).items
        assert campaign_record.name == result.campaign_name
        assert campaign_record.audit == result.audit.model_dump(mode="json")
        assert campaign_record.status == "COMPLETED"
        assert attack_run.campaign_run_id == campaign_record.id
        assert "evaluation_audit" not in attack_run.run_config
    finally:
        store.close()


def test_a_stopping_audit_is_persisted_without_fabricating_attack_runs():
    from tests.fakes import RecordingStore

    from .fakes import goals

    store = RecordingStore()
    with pytest.raises(AuditFailed) as raised:
        run_campaign(
            audited(
                "stop",
                robustness={
                    "enabled": True,
                    "wrappers": ["refusal_prefix"],
                    "max_flip_rate": 0.0,
                },
            ),
            build=FakeBuilder({"target": ScriptedModel(), "judge": brittle_judge()}),
            load=goals("goal one"),
            store=store,
            calibration=lambda _spec: samples(),
        )

    [stored] = store.campaign_runs.values()
    assert stored.status == "FAILED"
    assert stored.audit == raised.value.report.model_dump(mode="json")
    assert "failed its audit" in stored.run_notes
    assert store.runs == {}


def test_the_campaign_file_supplies_the_dataset_settings():
    seen = []

    run(
        audited(dataset={"sample_size": 25, "seed": 11}),
        calibration=lambda spec: seen.append(spec) or samples(),
    )

    assert (seen[0].sample_size, seen[0].seed) == (25, 11)


def test_run_audit_reads_the_campaign_block_too():
    report = audit(audited(robustness={"enabled": True, "max_flip_rate": 0.25}))

    assert report.report_for("harmbench").robustness.max_flip_rate == 0.25


def test_run_audit_runs_even_when_the_campaign_disabled_it():
    report = audit(campaign())

    assert report.samples == 2


# --- the ensemble lines read correctly in every direction --------------------


def ensemble_report(panel_column: str, **judges: str) -> AuditReport:
    """An audit built from vote columns, to exercise the formatter's prose."""
    labels = [True, True, True, True, False, False, False, False]
    votes = {
        name: tuple(character == "1" for character in column)
        for name, column in judges.items()
    }
    panel_votes = tuple(character == "1" for character in panel_column)
    rows = [
        JudgeReport(judge=name, metrics=binary_metrics(column, labels))
        for name, column in votes.items()
    ]
    rows.append(JudgeReport(judge=PANEL, metrics=binary_metrics(panel_votes, labels)))
    return AuditReport(
        samples=len(labels),
        contextual_samples=0,
        judges=tuple(rows),
        ensemble=compare_rules(votes, panel_votes, labels, aggregation="majority"),
    )


def test_a_panel_level_with_its_best_judge_is_not_called_a_loss():
    # Identical judges: the panel can only reproduce them.
    text = format_report(
        ensemble_report("11000000", a="11000000", b="11000000", c="11000000")
    )

    assert "the two are level" in text
    assert "behind" not in text and "ahead" not in text
    assert "changed no verdict" in text


def test_a_panel_behind_its_best_judge_says_so_with_the_gap():
    text = format_report(
        ensemble_report("10000000", sharp="11110000", blunt="10000000", dull="10000000")
    )

    assert "the panel is behind by 0.750" in text
    # Three disagreements, all one way, is still not enough to call.
    assert "too few to call" in text


def test_judges_that_cover_each_other_are_not_reported_as_a_cost():
    # Complementary blind spots: independence would do worse than reality.
    text = format_report(
        ensemble_report("11100000", a="11000000", b="01100000", c="10100000")
    )

    assert "cover each other" in " ".join(text.split())
    assert "costs -" not in text


def test_long_prose_is_folded_to_the_table_width():
    text = format_report(
        ensemble_report("10000000", sharp="11110000", blunt="10000000", dull="10000000")
    )

    assert max(len(line) for line in text.splitlines()) <= 78


def test_a_judge_named_after_its_model_still_lines_up():
    long_name = "harmbench:meta-llama/Llama-Guard-3-8B"
    text = format_report(
        ensemble_report("11000000", **{long_name: "11000000", "b": "11000000"})
    )
    rows = [
        line
        for line in text.splitlines()
        if line.startswith((long_name, "judge", "b "))
    ]

    assert long_name in text
    # Every column still starts in the same place.
    assert len({len(row) for row in rows}) == 1
