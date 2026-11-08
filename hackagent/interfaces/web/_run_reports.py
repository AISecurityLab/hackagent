# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Offline campaign run reports: the platform's ``/run`` report routes.

``/run/summary``, ``/run/delete`` and the detail actions ``summary``,
``report``, ``goals``, ``matrix``, ``attempts``, ``structure``, ``costs`` and
``compare`` of a campaign run, answered from the local store. The store reads
light rows (mostly its per-goal tallies) and :mod:`hackagent.reporting`
builds every response, as it does on the platform, so the dashboard gets the
same JSON from both.

Every ``GET`` carries a weak ``ETag`` computed from the revisions of the
campaign runs in the response, before the response is built: a matching
``If-None-Match`` is answered ``304`` without reading anything else.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterable, Optional

from flask import Blueprint, Response, jsonify, request

from hackagent.attacks.techniques.registry import attack_family
from hackagent.orchestrator.campaign.spec import redacted
from hackagent.reporting import (
    AttackRun,
    CampaignRun,
    attack_structure,
    attempt_page,
    campaign_run_costs,
    campaign_run_report,
    campaign_run_summaries,
    campaign_run_summary,
    compare_runs,
    goal_listing,
    goal_matrix,
    pick_previous,
    previous_summary,
)
from hackagent.reporting import http
from hackagent.reporting.report import scoped_runs


def register_run_reports(bp: Blueprint, client: Any) -> None:
    """Add the campaign run report routes to the offline ``bp``."""

    @bp.errorhandler(http.ReportError)
    def refused(exc: http.ReportError):
        return jsonify(exc.body()), exc.status

    def query() -> list[tuple[str, str]]:
        return list(request.args.items(multi=True))

    def conditional(tag: str, build: Callable[[], Any]) -> Response:
        """``build()`` as JSON, or ``304`` when the client holds ``tag``."""
        if http.etag_matches(request.headers.get("If-None-Match"), tag):
            response = Response(status=304)
        else:
            response = jsonify(build())
        response.headers["ETag"] = tag
        response.headers["Cache-Control"] = http.CACHE_CONTROL
        return response

    def campaign_run(campaign_run_id: str) -> CampaignRun:
        parsed = http.parse_uuid(campaign_run_id)
        record = client.report_campaign_run(parsed) if parsed else None
        if record is None:
            raise http.NotFound(http.CAMPAIGN_RUN_NOT_FOUND)
        return record

    def attack_runs(ids: Iterable[str], *, full: bool = False) -> list[AttackRun]:
        runs = client.report_attack_runs(list(ids), full=full)
        if not full:
            return runs
        # The registry and the redaction rules belong to the SDK's upper
        # layers, which the reporting rows cannot import.
        return [
            replace(
                run,
                family=attack_family(run.technique),
                attack_configuration=redacted(run.attack_configuration)
                if run.attack_configuration is not None
                else None,
            )
            for run in runs
        ]

    def previous_of(run: CampaignRun) -> Optional[CampaignRun]:
        return pick_previous(run, client.report_previous_candidates(run))

    def revisions(*runs: Optional[CampaignRun]) -> list[tuple[str, int]]:
        return [(run.id, run.revision) for run in runs if run is not None]

    @bp.get("/run/summary")
    def run_summaries():
        page, page_size = http.page_args(request.args, http.SUMMARY_PAGE)
        filters = {
            key: (http.parse_uuid(value) or "-") if key != "status" else value
            for key in ("campaign", "agent", "status")
            if (value := request.args.get(key))
        }
        listing = client.report_campaign_runs(**filters, page=page, page_size=page_size)
        tag = http.etag(
            "summary-list", query(), revisions(*listing.items), listing.total
        )

        def build() -> dict[str, Any]:
            ids = [run.id for run in listing.items]
            items = campaign_run_summaries(
                listing.items, attack_runs(ids), client.report_goal_totals(ids)
            )
            return http.paginate(items, listing.total, page, page_size)

        return conditional(tag, build)

    @bp.post("/run/delete")
    def run_delete_selected():
        ids = http.selection(request.get_json(silent=True))
        try:
            client.delete_campaign_runs(ids)
        except ValueError:
            raise http.Conflict(http.ACTIVE_CAMPAIGN_RUN) from None
        except RuntimeError:
            raise http.NotFound(http.CAMPAIGN_RUN_NOT_FOUND) from None
        return "", 204

    @bp.get("/run/<campaign_run_id>/summary")
    def run_summary(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        return conditional(
            http.etag("summary", query(), revisions(run)),
            lambda: campaign_run_summary(
                run, attack_runs([run.id]), client.report_goal_totals([run.id])
            ),
        )

    @bp.get("/run/<campaign_run_id>/report")
    def run_report(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        previous = previous_of(run)

        def build() -> dict[str, Any]:
            return campaign_run_report(
                run,
                attack_runs([run.id], full=True),
                client.report_goal_outcomes(run.id),
                scope_run_id=http.scope_arg(request.args),
                previous=previous_summary(
                    previous,
                    attack_runs([previous.id]),
                    client.report_goal_totals([previous.id]),
                )
                if previous is not None
                else None,
            )

        return conditional(
            http.etag("report", query(), revisions(run, previous)), build
        )

    @bp.get("/run/<campaign_run_id>/goals")
    def run_goals(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        filters = http.goal_filters(request.args)
        page, page_size = http.page_args(request.args, http.GOALS_PAGE)

        def build() -> dict[str, Any]:
            goals = goal_listing(
                run,
                attack_runs([run.id]),
                client.report_goal_outcomes(run.id),
                filters,
                scope_run_id=http.scope_arg(request.args),
            )
            return http.paginate(
                http.page_slice(goals, page, page_size), len(goals), page, page_size
            )

        return conditional(http.etag("goals", query(), revisions(run)), build)

    @bp.get("/run/<campaign_run_id>/matrix")
    def run_matrix(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        return conditional(
            http.etag("matrix", query(), revisions(run)),
            lambda: goal_matrix(
                run, attack_runs([run.id]), client.report_goal_outcomes(run.id)
            ),
        )

    @bp.get("/run/<campaign_run_id>/attempts")
    def run_attempts(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        index = http.goal_index_arg(request.args, required=True)
        page, page_size = http.page_args(request.args, http.ATTEMPTS_PAGE)

        def build() -> dict[str, Any]:
            _, selected = scoped_runs(
                run, attack_runs([run.id]), http.scope_arg(request.args)
            )
            rows, count, first = client.report_attempts(
                [item.id for item in selected],
                index,
                page=page,
                page_size=page_size,
            )
            return attempt_page(rows, count, page, page_size, first)

        return conditional(http.etag("attempts", query(), revisions(run)), build)

    @bp.get("/run/<campaign_run_id>/structure")
    def run_structure(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        index = http.goal_index_arg(request.args, required=True)
        scope = http.scope_arg(request.args)
        if scope is None:
            raise http.NotFound(http.ATTACK_RUN_NOT_FOUND)

        def build() -> dict[str, Any]:
            _, [selected] = scoped_runs(run, attack_runs([run.id]), scope)
            return attack_structure(*client.report_structure(selected.id, index))

        return conditional(http.etag("structure", query(), revisions(run)), build)

    @bp.get("/run/<campaign_run_id>/costs")
    def run_costs(campaign_run_id: str):
        run = campaign_run(campaign_run_id)

        def build() -> dict[str, Any]:
            runs = attack_runs([run.id])
            return campaign_run_costs(
                runs,
                client.report_goal_outcomes(run.id),
                client.report_goal_usage(run.id),
                client.report_latencies([item.id for item in runs]),
            )

        return conditional(http.etag("costs", query(), revisions(run)), build)

    @bp.get("/run/<campaign_run_id>/compare")
    def run_compare(campaign_run_id: str):
        run = campaign_run(campaign_run_id)
        baseline = campaign_run(http.baseline_arg(request.args, run.id))
        return conditional(
            http.etag("compare", query(), revisions(run, baseline)),
            lambda: compare_runs(
                run,
                attack_runs([run.id]),
                client.report_goal_outcomes(run.id),
                baseline,
                attack_runs([baseline.id]),
                client.report_goal_outcomes(baseline.id),
            ),
        )


__all__ = ["register_run_reports"]
