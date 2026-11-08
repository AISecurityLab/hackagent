# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The reporting rules, on rows built by hand."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hackagent.reporting import (
    AttackRun,
    CampaignRun,
    GoalFilters,
    GoalTotal,
    Latency,
    ResultRow,
    TraceRow,
    add_trace,
    campaign_run_costs,
    campaign_run_report,
    campaign_run_summary,
    category_summaries,
    compare_runs,
    goal_listing,
    goal_matrix,
    goal_outcome,
    goal_usage,
    goal_verdict,
    pick_previous,
    result_bucket,
    summarize_goals,
    trace_coverage,
    trace_flags,
)
from hackagent.reporting import http
from hackagent.reporting.attempts import attack_structure, attempt_page
from hackagent.reporting.costs import latency_summary, quantile
from hackagent.reporting.rows import Attempt, FirstSuccess, StructureResult
from hackagent.reporting.tallies import TraceFlags

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
CR = "c0000000-0000-4000-8000-000000000001"


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def campaign(status="COMPLETED", **fields) -> CampaignRun:
    values = dict(
        id=CR,
        name="Sweep",
        campaign=None,
        agent="agent",
        target="bot",
        status=status,
        executor="cli",
        created_at=T0,
        updated_at=at(60),
        finished_at=at(60) if status == "COMPLETED" else None,
        revision=3,
    )
    values.update(fields)
    return CampaignRun(**values)


def attack_run(ident: str, status="COMPLETED", seconds=0, technique="tap") -> AttackRun:
    return AttackRun(
        id=ident,
        campaign_run=CR,
        status=status,
        created_at=at(seconds),
        technique=technique,
    )


def result(
    ident,
    status,
    *,
    goal="goal",
    seconds=0,
    category=None,
    sub=None,
    clock=None,
    notes=None,
):
    return ResultRow(
        id=ident,
        goal=goal,
        evaluation_status=status,
        evaluation_notes=notes,
        category=category,
        subcategory=sub,
        active_elapsed_s=clock,
        created_at=at(seconds),
        updated_at=at(seconds + 10),
    )


def outcome(run_id, index, *statuses, goal=None, category=None, sub=None):
    return goal_outcome(
        campaign_run_id=CR,
        run_id=run_id,
        goal_index=index,
        results=[
            result(
                f"{run_id}-{index}-{n}",
                status,
                goal=goal or f"goal {index}",
                seconds=n,
                category=category,
                sub=sub,
            )
            for n, status in enumerate(statuses)
        ],
    )


J, M, E, P = (
    "SUCCESSFUL_JAILBREAK",
    "FAILED_JAILBREAK",
    "ERROR_AGENT_RESPONSE",
    "NOT_EVALUATED",
)


class TestBuckets:
    @pytest.mark.parametrize(
        ("status", "notes", "bucket"),
        [
            (J, None, "jailbreak"),
            ("custom_SUCCESSFUL_JAILBREAK", None, "jailbreak"),
            (M, None, "mitigated"),
            ("PASSED_CRITERIA", None, "mitigated"),
            ("FAILED_CRITERIA", None, "error"),
            (E, None, "error"),
            (J, "Attack failed with exception: timeout", "error"),
            (P, None, "pending"),
            (None, "", "pending"),
        ],
    )
    def test_each_status_falls_in_one_bucket(self, status, notes, bucket):
        assert result_bucket(status, notes) == bucket


class TestGoalOutcome:
    def test_counts_order_and_first_jailbreak(self):
        row = goal_outcome(
            campaign_run_id=CR,
            run_id="r",
            goal_index=0,
            results=[
                result("b", J, seconds=1, clock=9),
                result("a", M, seconds=0),
                result("c", J, seconds=2, clock=3),
                result("d", P, seconds=3),
            ],
        )
        assert (row.attempts, row.jailbreak, row.mitigated, row.pending) == (4, 2, 1, 1)
        assert row.first_jailbreak_attempt == 2
        assert (row.min_jailbreak_elapsed_s, row.timed_jailbreaks) == (3, 2)
        assert (row.first_created_at, row.last_updated_at) == (at(0), at(13))

    def test_ties_on_creation_are_ordered_by_id(self):
        row = goal_outcome(
            campaign_run_id=CR,
            run_id="r",
            goal_index=0,
            results=[result("b", M), result("a", J)],
        )
        assert row.first_jailbreak_attempt == 1

    def test_labels_come_from_the_latest_attempt_that_has_them(self):
        row = goal_outcome(
            campaign_run_id=CR,
            run_id="r",
            goal_index=0,
            results=[
                result("a", M, goal="old text", category="Old", sub="One", seconds=0),
                result("b", M, goal="new text", category="New", seconds=1),
                result("c", M, goal="newest text", seconds=2),
            ],
        )
        assert (row.goal, row.category, row.subcategory) == ("newest text", "New", "")

    def test_a_goal_without_results_has_no_row(self):
        assert (
            goal_outcome(campaign_run_id=CR, run_id="r", goal_index=0, results=[])
            is None
        )

    def test_from_data_reads_only_numeric_clocks(self):
        row = ResultRow.from_data(
            id="a",
            goal="g",
            evaluation_status=J,
            evaluation_notes=None,
            agent_specific_data={
                "category": "",
                "subcategory": "Sub",
                "attack_metadata": {"goal_active_target_elapsed_s": "12"},
            },
            created_at=T0,
            updated_at=T0,
        )
        assert (row.category, row.subcategory, row.active_elapsed_s) == (
            None,
            "Sub",
            None,
        )


class TestTraceTallies:
    TRACES = [
        TraceRow.from_content("a", "TOOL_CALL", {"node": "call", "label": "attacker"}),
        TraceRow.from_content(
            "a",
            "TOOL_CALL",
            {
                "node": "call",
                "label": "target",
                "data": {"usage": {"prompt_tokens": 3, "completion_tokens": 4}},
            },
        ),
        TraceRow.from_content(
            "a",
            "interaction",
            {"response": {"usage": {"prompt_tokens": 9, "completion_tokens": 1}}},
        ),
        TraceRow.from_content(
            "b", "TOOL_CALL", {"node": "call", "label": "target", "scope": "goal"}
        ),
        TraceRow.from_content("b", "TOOL_CALL", {"node": "call"}),
        TraceRow.from_content("b", "OTHER", {"node": "phase", "label": "branch"}),
        TraceRow.from_content(
            "b", "interaction", {"response": {"usage": {"prompt_tokens": 2}}}
        ),
    ]

    def test_usage_rows_count_calls_by_label_and_interactions_under_empty(self):
        rows = {
            row.label: row
            for row in goal_usage(
                campaign_run_id=CR, run_id="r", goal_index=0, traces=self.TRACES
            )
        }
        assert set(rows) == {"", "attacker", "target"}
        assert (rows["target"].calls, rows["target"].goal_scoped_calls) == (2, 1)
        assert (rows["target"].prompt_tokens, rows["target"].usage_calls) == (3, 1)
        assert (rows[""].calls, rows[""].prompt_tokens, rows[""].usage_calls) == (
            2,
            11,
            1,
        )

    def test_data_usage_wins_over_response_usage(self):
        trace = TraceRow.from_content(
            "a",
            "interaction",
            {
                "data": {"usage": {"prompt_tokens": 1}},
                "response": {"usage": {"prompt_tokens": 5, "completion_tokens": 6}},
            },
        )
        assert (trace.prompt_tokens, trace.completion_tokens) == (1, 6)

    def test_coverage_counts_attempts_not_steps(self):
        coverage = trace_coverage(self.TRACES)
        assert coverage.labelled_call_attempts == 2
        assert coverage.target_call_attempts == 2
        assert coverage.interaction_attempts == 2

    def test_adding_steps_one_by_one_matches_the_full_recomputation(self):
        row = outcome("r", 0, M, M)
        usage: dict[str, object] = {}
        seen: dict[str, list[TraceRow]] = {}
        for trace in self.TRACES:
            before = trace_flags(seen.get(trace.result_id, []))
            label = trace.label if trace.node == "call" else ""
            if trace.step_type == "interaction":
                label = ""
            row, counted = add_trace(row, usage.get(label), trace, before)
            if counted is not None:
                usage[counted.label] = counted
            seen.setdefault(trace.result_id, []).append(trace)
        assert row.coverage == trace_coverage(self.TRACES)
        assert sorted(usage.values(), key=lambda item: item.label) == goal_usage(
            campaign_run_id=CR, run_id="r", goal_index=0, traces=self.TRACES
        )

    def test_flags_of_one_attempt(self):
        assert trace_flags(self.TRACES[:1]) == TraceFlags(True, False, False)
        assert trace_flags([]) == TraceFlags()


class TestVerdicts:
    def test_verdict_rule(self):
        assert (
            goal_verdict(attempts=2, jailbreak=1, mitigated=0, complete=False)
            == "jailbroken"
        )
        assert (
            goal_verdict(attempts=2, jailbreak=0, mitigated=2, complete=True)
            == "mitigated"
        )
        assert (
            goal_verdict(attempts=2, jailbreak=0, mitigated=2, complete=False)
            == "unresolved"
        )
        assert (
            goal_verdict(attempts=2, jailbreak=0, mitigated=1, complete=True)
            == "unresolved"
        )

    def test_summaries_merge_attack_runs_and_label_from_the_latest_run(self):
        runs = [attack_run("r1", seconds=0), attack_run("r2", seconds=1)]
        goals = summarize_goals(
            [
                outcome("r1", 0, M, goal="first", category="Old"),
                outcome("r2", 0, J, E, goal="second", category="New", sub="Sub"),
                outcome("r1", 1, E),
            ],
            True,
            runs,
        )
        assert [goal["index"] for goal in goals] == [0, 1]
        first = goals[0]
        assert (first["goal"], first["category"], first["subcategory"]) == (
            "second",
            "New",
            "Sub",
        )
        assert (
            first["verdict"],
            first["attempts"],
            first["successful_attempts"],
            first["errors"],
        ) == (
            "jailbroken",
            3,
            1,
            1,
        )
        assert first["run_ids"] == ["r1", "r2"]
        assert (
            goals[1]["category"],
            goals[1]["category_source"],
            goals[1]["verdict"],
        ) == (
            "Unknown",
            "unknown",
            "unresolved",
        )

    def test_category_order_sorted_and_subcategories_by_first_goal(self):
        goals = summarize_goals(
            [
                outcome("r", 0, M, category="Safety", sub="Zulu"),
                outcome("r", 1, M, category="Privacy"),
                outcome("r", 2, J, category="Safety", sub="Alpha"),
            ],
            True,
        )
        categories = category_summaries(goals)
        assert [item["category"] for item in categories] == ["Privacy", "Safety"]
        assert [item["name"] for item in categories[1]["subcategories"]] == [
            "Zulu",
            "Alpha",
        ]
        assert categories[0]["subcategories"][0]["name"] == "Unspecified"


class TestReports:
    def test_an_empty_campaign_run(self):
        run = campaign(status="CANCELLED")
        report = campaign_run_report(run, [], [])
        assert (
            report["attack_runs"],
            report["recorded_goals"],
            report["attempts"],
        ) == (0, 0, 0)
        assert (
            report["runs"]
            == report["technique_outcomes"]
            == report["category_outcomes"]
            == []
        )
        assert goal_matrix(run, [], []) == {
            "runs": [],
            "goals": [],
            "cells": [],
            "attempts": [],
        }
        assert campaign_run_costs([], [], [], []) == {"runs": []}
        assert campaign_run_summary(run, [], [])["recorded_goals"] == 0

    def test_a_running_campaign_mitigates_nothing_but_its_attacks_do(self):
        run = campaign(status="RUNNING")
        runs = [attack_run("r1", status="RUNNING")]
        rows = [outcome("r1", 0, M), outcome("r1", 1, P)]
        report = campaign_run_report(run, runs, rows)
        assert (report["mitigated"], report["unresolved"]) == (0, 2)
        assert report["runs"][0]["outcomes"]["mitigated"] == 1
        assert report["technique_outcomes"][0]["mitigated"] == 1
        scoped = campaign_run_report(run, runs, rows, scope_run_id="r1")
        assert scoped["mitigated"] == 1

    def test_an_all_error_goal_is_an_error_for_its_attack(self):
        run = campaign()
        runs = [attack_run("r1"), attack_run("r2", seconds=1)]
        rows = [outcome("r1", 0, E, E), outcome("r2", 0, M)]
        [goal] = goal_listing(run, runs, rows, GoalFilters())
        assert goal["verdict"] == "unresolved"
        assert [
            (item["run_id"], item["verdict"]) for item in goal["attack_outcomes"]
        ] == [
            ("r1", "error"),
            ("r2", "mitigated"),
        ]
        assert goal_matrix(run, runs, rows)["cells"] == [[2, 1]]

    def test_a_foreign_scope_is_not_found(self):
        with pytest.raises(http.NotFound):
            campaign_run_report(
                campaign(), [attack_run("r1")], [], scope_run_id="other"
            )

    def test_summary_counts_from_totals_match_the_report(self):
        run = campaign()
        runs = [attack_run("r1"), attack_run("r2", seconds=1)]
        rows = [outcome("r1", 0, M), outcome("r2", 0, M), outcome("r2", 1, J)]
        totals = [
            GoalTotal(CR, 0, 2, 0, 2, 0, 0),
            GoalTotal(CR, 1, 1, 1, 0, 0, 0),
        ]
        summary = campaign_run_summary(run, runs, totals)
        report = campaign_run_report(run, runs, rows)
        for key in (
            "recorded_goals",
            "jailbroken",
            "mitigated",
            "unresolved",
            "attempts",
        ):
            assert summary[key] == report[key]

    def test_previous_is_the_latest_completed_run_of_the_same_campaign(self):
        current = campaign(campaign="k", created_at=at(100), id="c-now")
        older = campaign(campaign="k", created_at=at(50), id="c-old")
        newest_before = campaign(campaign="k", created_at=at(80), id="c-recent")
        failed = campaign(
            campaign="k", created_at=at(90), id="c-failed", status="FAILED"
        )
        other = campaign(campaign="other", created_at=at(95), id="c-other")
        later = campaign(campaign="k", created_at=at(120), id="c-later")
        picked = pick_previous(
            current, [older, newest_before, failed, other, later, current]
        )
        assert picked is newest_before

    def test_previous_of_an_unsaved_campaign_matches_agent_and_name(self):
        current = campaign(created_at=at(100), id="c-now")
        same = campaign(created_at=at(10), id="c-same")
        renamed = campaign(created_at=at(20), id="c-renamed", name="Other")
        saved = campaign(created_at=at(30), id="c-saved", campaign="k")
        assert pick_previous(current, [same, renamed, saved]) is same
        assert pick_previous(current, []) is None

    def test_compare_orders_changes_and_merges_repeated_texts(self):
        current = campaign(id="c-now")
        baseline = campaign(id="c-then", created_at=at(-100))
        now = [
            outcome("n", 0, J, goal="a"),
            outcome("n", 1, M, goal="b"),
            outcome("n", 2, M, goal="c"),
            outcome("n", 3, M, goal="c"),
            outcome("n", 4, M, goal="new"),
        ]
        then = [
            outcome("t", 0, M, goal="a"),
            outcome("t", 1, J, goal="b"),
            outcome("t", 2, E, goal="c"),
            outcome("t", 3, M, goal="gone"),
        ]
        result = compare_runs(
            current,
            [AttackRun("n", "c-now", "COMPLETED", T0)],
            now,
            baseline,
            [AttackRun("t", "c-then", "COMPLETED", T0)],
            then,
        )
        assert [(goal["goal"], goal["change"]) for goal in result["goals"]] == [
            ("a", "regressed"),
            ("b", "fixed"),
            ("new", "new"),
            ("gone", "dropped"),
            ("c", "unchanged"),
        ]
        assert result["counts"] == {
            "regressed": 1,
            "fixed": 1,
            "unchanged": 1,
            "new": 1,
            "dropped": 1,
        }


class TestCosts:
    def test_quantiles_interpolate_and_a_single_sample_is_every_quantile(self):
        assert quantile([100.0, 200.0, 300.0], 0.5) == 200
        assert latency_summary([Latency("r", 420)]) == {
            "median": 420.0,
            "p90": 420.0,
            "samples": 1,
        }
        assert (
            latency_summary([Latency("r", 10, count=3), Latency("r", 20)])["median"]
            == 10
        )
        assert latency_summary([]) is None

    def test_missing_usage_makes_tokens_unknown(self):
        traces = [
            TraceRow.from_content("a", "TOOL_CALL", {"node": "call", "label": "target"})
        ]
        row = goal_outcome(
            campaign_run_id=CR,
            run_id="r",
            goal_index=0,
            results=[result("a", M)],
            coverage=trace_coverage(traces),
        )
        usage = goal_usage(campaign_run_id=CR, run_id="r", goal_index=0, traces=traces)
        [cost] = campaign_run_costs([attack_run("r")], [row], usage, [])["runs"]
        assert cost["target_tokens"] is None
        assert cost["goal_samples"][0]["target_tokens"] is None
        assert cost["goal_samples"][0]["calls"] == 1
        assert cost["calls"] == {"target": 1, "attacker": 0, "judge": 0}

    def test_untraced_runs_report_unknown_attacker_and_judge_calls(self):
        [cost] = campaign_run_costs([attack_run("r")], [outcome("r", 0, M)], [], [])[
            "runs"
        ]
        assert cost["calls"] == {"target": 0, "attacker": None, "judge": None}
        assert cost["calls_traced"] is False
        assert cost["target_tokens"] is None


class TestAttempts:
    def test_pages_number_attempts_and_locate_the_first_success(self):
        rows = [Attempt("x", "r", "mitigated", "", at(5))]
        page = attempt_page(rows, 3, 2, 1, FirstSuccess("y", 3))
        assert page["results"][0]["ordinal"] == 2
        assert page["results"][0]["notes"] is None
        assert page["first_success"] == {"id": "y", "page": 3}
        assert (page["next"] is not None, page["previous"] is not None) == (True, True)

    def test_structure_orders_attempts_and_reads_attack_metadata(self):
        results = [
            StructureResult(
                "b", "r", J, None, {}, {"attack_metadata": {"depth": 2}}, at(1)
            ),
            StructureResult("a", "r", M, "", None, None, at(0)),
        ]
        body = attack_structure(results, [])
        assert [item["id"] for item in body["attempts"]] == ["a", "b"]
        assert body["attempts"][0]["metadata"] == {}
        assert body["attempts"][1]["metadata"] == {"depth": 2}
        assert body["results"][0] == {
            "id": "a",
            "request_payload": None,
            "agent_specific_data": None,
            "evaluation_notes": None,
        }


class TestHttp:
    def test_page_args_fall_back_and_clamp(self):
        assert http.page_args({}, http.SUMMARY_PAGE) == (1, 20)
        assert http.page_args({"page": "x", "page_size": "500"}, http.SUMMARY_PAGE) == (
            1,
            100,
        )
        assert http.page_args({"page": "-3", "page_size": "0"}, http.GOALS_PAGE) == (
            1,
            1,
        )

    def test_goal_filters_refuse_bad_values(self):
        for args in ({"verdict": "bogus"}, {"goal_index": "-1"}, {"goal_index": "x"}):
            with pytest.raises(http.BadRequest):
                http.goal_filters(args)
        with pytest.raises(http.BadRequest):
            http.goal_index_arg({}, required=True)
        assert http.goal_filters(
            {"verdict": "mitigated", "goal_index": "2"}
        ) == GoalFilters(goal_index=2, verdict="mitigated")

    def test_selection_and_baseline(self):
        ident = "C0000000-0000-4000-8000-000000000001"
        assert http.selection({"ids": [ident, ident.lower()]}) == [ident.lower()]
        for body in (
            None,
            {},
            {"ids": []},
            {"ids": ["nope"]},
            {"ids": [4]},
            {"ids": [ident] * 101},
        ):
            with pytest.raises(http.BadRequest):
                http.selection(body)
        with pytest.raises(http.BadRequest):
            http.baseline_arg({"baseline": ident}, ident.lower())
        with pytest.raises(http.BadRequest):
            http.baseline_arg({}, "x")

    def test_etags_depend_on_route_query_and_revisions_only(self):
        tag = http.etag("report", [("b", "2"), ("a", "1")], [("x", 1)])
        assert tag == http.etag("report", [("a", "1"), ("b", "2")], [("x", 1)])
        assert tag.startswith('W/"') and len(tag) == 36
        assert tag != http.etag("report", [("a", "1"), ("b", "2")], [("x", 2)])
        assert tag != http.etag("matrix", [("a", "1"), ("b", "2")], [("x", 1)])
        assert http.etag_matches(f'"other", {tag}', tag)
        assert http.etag_matches(tag[2:], tag)
        assert http.etag_matches("*", tag)
        assert not http.etag_matches(None, tag)
        assert not http.etag_matches('W/"other"', tag)


def test_interaction_steps_are_one_value_in_the_runner_both_stores_and_the_rules():
    from hackagent.core.contracts import StepKind
    from hackagent.reporting.tallies import INTERACTION, INTERACTION_STEP, usage_label
    from hackagent.storage._http.api.models import StepTypeEnum

    assert StepKind.INTERACTION.value == INTERACTION_STEP
    assert StepTypeEnum(INTERACTION_STEP) is StepTypeEnum.INTERACTION
    step = TraceRow.from_content("r", StepTypeEnum.INTERACTION.value, {})
    assert usage_label(step) == INTERACTION
    assert trace_flags([step]).interaction
