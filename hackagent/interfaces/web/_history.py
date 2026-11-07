# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Local campaign investigation views, separate from the hosted API contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flask import Blueprint, jsonify, request

from hackagent.attacks.techniques.registry import attack_family
from hackagent.orchestrator.campaign.spec import redacted
from hackagent.storage.buckets import result_bucket
from hackagent.storage.records import CampaignRunRecord, ResultRecord, RunRecord

from . import _serializers as ser
from ._local_api import _not_found, _page_args, _slice, _uuid
from ._history_summary import (
    GoalSummary,
    category_summaries,
    outcome_counts as _outcome_counts,
    summarize_goals as _goals,
)
from ._dashboard_cache import DashboardCache, VERSION
from ._judge_agreement import judge_agreement


def _read_all(read: Callable[..., Any], **kwargs: Any) -> list[Any]:
    records: list[Any] = []
    page = 1
    while True:
        listing = read(page=page, page_size=1000, **kwargs)
        records.extend(listing.items)
        if not listing.items or len(records) >= listing.total:
            return records
        page += 1


@dataclass
class HistoryReader:
    children: Callable[[UUID], list[RunRecord]]
    records: Callable[..., list[ResultRecord]]
    load: Callable[[str], CampaignRunRecord | None]
    names: Callable[[], dict[str, str]]
    detail: Callable[[CampaignRunRecord, str | None], dict[str, Any]]
    goals: Callable[..., list[GoalSummary]]


def create_history_reader(client: Any) -> HistoryReader:
    def children(campaign_id: UUID) -> list[RunRecord]:
        return [
            run for run in _read_all(client.runs) if run.campaign_run_id == campaign_id
        ]

    def scoped(runs: list[RunRecord], run_id: str | None) -> list[RunRecord]:
        return [run for run in runs if str(run.id) == run_id] if run_id else runs

    def records(
        runs: list[RunRecord],
        *,
        goal_index: int | None = None,
        full: bool = False,
    ) -> list[ResultRecord]:
        results = client.campaign_results(
            [run.id for run in runs], goal_index=goal_index, full=full
        )
        by_run: dict[UUID, list[ResultRecord]] = {run.id: [] for run in runs}
        for result in results:
            by_run[result.run_id].append(result)
        return [result for run in runs for result in by_run[run.id]]

    def summary(
        campaign: CampaignRunRecord,
        runs: list[RunRecord],
        results: list[ResultRecord],
        names: dict[str, str],
        goals: list[GoalSummary] | None = None,
    ) -> dict[str, Any]:
        completed = campaign.status == "COMPLETED" and all(
            run.status == "COMPLETED" for run in runs
        )
        if goals is None:
            goals = _goals(results, completed)
        return {
            "id": str(campaign.id),
            "name": campaign.name,
            "target": names.get(str(campaign.agent_id), str(campaign.agent_id)),
            "status": campaign.status,
            "created_at": campaign.created_at.isoformat(),
            "updated_at": campaign.updated_at.isoformat(),
            "attack_runs": len(runs),
            **_outcome_counts(goals),
            "attempts": len(results),
        }

    def load(campaign_id: str):
        parsed = _uuid(campaign_id)
        if parsed is None:
            return None
        try:
            return client.campaign_run(parsed)
        except RuntimeError:
            return None

    def names() -> dict[str, str]:
        return {str(a.id): a.name for a in _read_all(client.agents)}

    def detail(campaign: CampaignRunRecord, run_id: str | None) -> dict[str, Any]:
        runs = children(campaign.id)
        selected = scoped(runs, run_id)
        results = records(selected)
        category_goals = _goals(
            results,
            bool(run_id)
            or (
                campaign.status == "COMPLETED"
                and all(run.status == "COMPLETED" for run in selected)
            ),
        )
        payload = summary(campaign, selected, results, names(), category_goals)
        by_run: dict[UUID, list[ResultRecord]] = {run.id: [] for run in selected}
        for result in results:
            by_run[result.run_id].append(result)
        goals_by_run = {
            # The runner records attempts after the attack finishes that goal,
            # not after the attack has finished every goal in the dataset.
            run.id: _goals(by_run[run.id], True)
            for run in selected
        }
        categories = category_summaries(category_goals)
        attacks = {str(a.id): a for a in _read_all(client.attacks)}
        types = {key: attack.type for key, attack in attacks.items()}
        technique_runs: dict[str, list[RunRecord]] = {}
        for run in selected:
            technique = types.get(str(run.attack_id), "Unknown")
            technique_runs.setdefault(technique, []).append(run)
        technique_outcomes = []
        for technique, group in sorted(technique_runs.items()):
            attempts = [result for run in group for result in by_run[run.id]]
            goals = (
                goals_by_run[group[0].id] if len(group) == 1 else _goals(attempts, True)
            )
            technique_outcomes.append(
                {
                    "technique": technique,
                    **_outcome_counts(goals),
                    "attempts": len(attempts),
                }
            )
        labels_by_goal = {
            goal["index"]: (goal["category"], goal["subcategory"] or "Unspecified")
            for goal in category_goals
        }
        attack_categories = []
        for run in selected:
            goals = goals_by_run[run.id]
            for category in categories:
                category_name = category["category"]
                group = [
                    goal
                    for goal in goals
                    if labels_by_goal[goal["index"]][0] == category_name
                ]
                attack_categories.append(
                    {
                        "run_id": str(run.id),
                        "category": category_name,
                        **_outcome_counts(group),
                        "subcategories": [
                            {
                                "name": subcategory["name"],
                                **_outcome_counts(
                                    [
                                        g
                                        for g in group
                                        if labels_by_goal[g["index"]][1]
                                        == subcategory["name"]
                                    ]
                                ),
                            }
                            for subcategory in sorted(
                                category["subcategories"], key=lambda item: item["name"]
                            )
                        ],
                    }
                )
        payload.update(
            {
                "judge_agreement": judge_agreement(
                    client.backend.panel_vote_rows([run.id for run in selected])
                ),
                "attack_category_outcomes": attack_categories,
                "technique_outcomes": technique_outcomes,
                "category_outcomes": categories,
                "scope_run_id": run_id,
                "configuration": campaign.campaign_config,
                "audit": campaign.audit,
                "notes": campaign.run_notes,
                "runs": [
                    {
                        "id": str(run.id),
                        "attack_id": str(run.attack_id),
                        "technique": types.get(str(run.attack_id), "Unknown"),
                        "family": attack_family(types.get(str(run.attack_id), "")),
                        "status": run.status,
                        "notes": run.run_notes,
                        "created_at": run.created_at.isoformat(),
                        "configuration": run.run_config,
                        # The parameters and roles this attack actually ran
                        # with, defaults included, as recorded at the time.
                        "attack_configuration": redacted(
                            attacks[str(run.attack_id)].configuration
                        )
                        if str(run.attack_id) in attacks
                        else None,
                        "outcomes": summary(
                            campaign,
                            [run],
                            by_run[run.id],
                            {},
                            goals_by_run[run.id],
                        )
                        if run in selected
                        else None,
                    }
                    for run in sorted(
                        runs, key=lambda run: (run.created_at, str(run.id))
                    )
                ],
            }
        )
        return payload

    def goals(
        campaign: CampaignRunRecord,
        run_id: str | None = None,
        goal_index: int | None = None,
    ) -> list[GoalSummary]:
        runs = scoped(children(campaign.id), run_id)
        completed = bool(run_id) or (
            campaign.status == "COMPLETED"
            and all(run.status == "COMPLETED" for run in runs)
        )
        results = records(runs, goal_index=goal_index)
        items = _goals(results, completed)
        by_run: dict[UUID, list[ResultRecord]] = {run.id: [] for run in runs}
        for result in results:
            by_run[result.run_id].append(result)
        per_run = {
            str(run.id): {goal["index"]: goal for goal in _goals(by_run[run.id], True)}
            for run in runs
        }
        for goal in items:
            goal["attack_outcomes"] = [
                {
                    "run_id": run_id,
                    "verdict": "error"
                    if recorded["errors"] == recorded["attempts"]
                    else recorded["verdict"],
                    "attempts": recorded["attempts"],
                }
                for run_id, run_goals in per_run.items()
                if (recorded := run_goals.get(goal["index"])) is not None
            ]
        return items

    return HistoryReader(children, records, load, names, detail, goals)


def create_history_api(client: Any, cache: DashboardCache | None = None) -> Blueprint:
    bp = Blueprint("local_history", __name__)
    reader = create_history_reader(client)
    children, records, load = reader.children, reader.records, reader.load

    def preparing():
        if cache is not None and cache.error:
            return jsonify({"detail": cache.error}), 503
        return (
            jsonify({"preparing": True, "detail": "Preparing dashboard summaries."}),
            202,
            {"Retry-After": "2"},
        )

    @bp.get("")
    def history():
        page, page_size = _page_args()
        listing = client.campaign_runs(page=page, page_size=page_size)
        if cache is not None:
            snapshots = cache.read([campaign.id for campaign in listing.items])
            progressive = request.args.get("progressive") == "1"
            if len(snapshots) != len(listing.items) and not progressive:
                return preparing()
            items = [
                snapshots[str(campaign.id)]["summary"]
                for campaign in listing.items
                if str(campaign.id) in snapshots
            ]
            payload = ser.paginate(items, listing.total, page, page_size)
            if progressive:
                positions = {
                    str(campaign.id): index
                    for index, campaign in enumerate(listing.items)
                }
                items = [
                    {**item, "page_position": positions[item["id"]]} for item in items
                ]
                payload = ser.paginate(items, listing.total, page, page_size)
                payload["preparing_campaigns"] = [
                    {
                        "id": str(campaign.id),
                        "name": campaign.name,
                        "status": campaign.status,
                        "created_at": campaign.created_at.isoformat(),
                        "page_position": index,
                    }
                    for index, campaign in enumerate(listing.items)
                    if str(campaign.id) not in snapshots
                ]
                payload["refresh_error"] = cache.error
                payload["upgrading_campaigns"] = sum(
                    snapshot["version"] < VERSION for snapshot in snapshots.values()
                )
            if snapshots:
                payload["dashboard_snapshot"] = cache.metadata(
                    min(item["generated_at"] for item in snapshots.values()),
                    min(item["version"] for item in snapshots.values()),
                )
            return jsonify(payload)
        outcomes = client.campaign_outcomes([campaign.id for campaign in listing.items])
        agent_names = reader.names()
        items = [
            {
                "id": str(campaign.id),
                "name": campaign.name,
                "target": agent_names.get(
                    str(campaign.agent_id), str(campaign.agent_id)
                ),
                "status": campaign.status,
                "created_at": campaign.created_at.isoformat(),
                "updated_at": campaign.updated_at.isoformat(),
                **outcomes[str(campaign.id)],
            }
            for campaign in listing.items
        ]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.delete("")
    def delete_selected():
        body = request.get_json(silent=True)
        ids = body.get("ids") if isinstance(body, dict) else None
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 100
            or any(not isinstance(ident, str) or _uuid(ident) is None for ident in ids)
        ):
            return jsonify({"detail": "Provide 1 to 100 valid campaign IDs."}), 400
        try:
            client.delete_campaign_runs(ids)
        except NotImplementedError as exc:
            return jsonify({"detail": str(exc)}), 501
        except ValueError as exc:
            return jsonify({"detail": str(exc)}), 409
        except RuntimeError:
            return _not_found("Campaign execution")
        return "", 204

    @bp.delete("/<campaign_id>")
    def delete(campaign_id: str):
        parsed = _uuid(campaign_id)
        if parsed is None:
            return _not_found("Campaign execution")
        try:
            client.delete_campaign_run(parsed)
        except NotImplementedError as exc:
            return jsonify({"detail": str(exc)}), 501
        except ValueError as exc:
            return jsonify({"detail": str(exc)}), 409
        except RuntimeError:
            return _not_found("Campaign execution")
        return "", 204

    @bp.get("/<campaign_id>")
    def detail(campaign_id: str):
        campaign = load(campaign_id)
        if campaign is None:
            return _not_found("Campaign execution")
        run_id = request.args.get("run_id")
        if cache is not None and not run_id and request.args.get("fresh") != "1":
            snapshot = cache.read([campaign.id]).get(str(campaign.id))
            if snapshot is None:
                return preparing()
            return jsonify(
                {
                    **snapshot["detail"],
                    "dashboard_snapshot": cache.metadata(
                        snapshot["generated_at"], snapshot["version"]
                    ),
                }
            )
        if run_id and not any(str(run.id) == run_id for run in children(campaign.id)):
            return _not_found("Attack run")
        return jsonify(reader.detail(campaign, run_id))

    @bp.get("/<campaign_id>/goals")
    def goals(campaign_id: str):
        campaign = load(campaign_id)
        if campaign is None:
            return _not_found("Campaign execution")
        run_id = request.args.get("run_id")
        if run_id and not any(str(run.id) == run_id for run in children(campaign.id)):
            return _not_found("Attack run")
        index = None
        if "goal_index" in request.args:
            try:
                index = int(request.args["goal_index"])
                if index < 0:
                    raise ValueError
            except ValueError:
                return jsonify(
                    {"detail": "A non-negative goal_index is required."}
                ), 400
        snapshot = None
        if cache is not None and not run_id and request.args.get("fresh") != "1":
            snapshot = cache.read([campaign.id]).get(str(campaign.id))
            if snapshot is None:
                return preparing()
            items = snapshot["goals"]
            if index is not None:
                items = [goal for goal in items if goal["index"] == index]
        else:
            items = reader.goals(campaign, run_id, index)
        search = request.args.get("search", "").strip().casefold()
        verdict = request.args.get("verdict", "")
        category = request.args.get("category", "")
        subcategory = request.args.get("subcategory", "")
        if category:
            items = [g for g in items if g["category"] == category]
        if subcategory:
            items = [
                g for g in items if (g["subcategory"] or "Unspecified") == subcategory
            ]
        if search:
            items = [g for g in items if search in g["goal"].casefold()]
        if verdict:
            if verdict not in {"jailbroken", "mitigated", "unresolved"}:
                return jsonify({"detail": "Invalid goal verdict."}), 400
            items = [g for g in items if g["verdict"] == verdict]
        page, page_size = _page_args()
        payload = ser.paginate(
            _slice(items, page, page_size), len(items), page, page_size
        )
        if snapshot is not None:
            payload["dashboard_snapshot"] = cache.metadata(
                snapshot["generated_at"], snapshot["version"]
            )
        return jsonify(payload)

    @bp.get("/<campaign_id>/attempts")
    def attempts(campaign_id: str):
        campaign = load(campaign_id)
        if campaign is None:
            return _not_found("Campaign execution")
        try:
            index = int(request.args.get("goal_index", ""))
            if index < 0:
                raise ValueError
        except ValueError:
            return jsonify({"detail": "A non-negative goal_index is required."}), 400
        runs = children(campaign.id)
        run_filter = request.args.get("run_id")
        if run_filter:
            runs = [r for r in runs if str(r.id) == run_filter]
            if not runs:
                return _not_found("Attack run")
        page, page_size = _page_args()
        attempts = client.campaign_attempts(
            [run.id for run in runs], index, page=page, page_size=page_size
        )
        envelope = ser.paginate(attempts["items"], attempts["total"], page, page_size)
        envelope["first_success"] = attempts["first_success"]
        return jsonify(envelope)

    @bp.get("/<campaign_id>/costs")
    def costs(campaign_id: str):
        """What each attack spent: calls by role, target tokens and time."""
        campaign = load(campaign_id)
        if campaign is None:
            return _not_found("Campaign execution")
        if cache is not None and request.args.get("fresh") != "1":
            snapshot = cache.read([campaign.id]).get(str(campaign.id))
            if snapshot is None:
                return preparing()
            return jsonify(
                {
                    **snapshot["costs"],
                    "dashboard_snapshot": cache.metadata(
                        snapshot["generated_at"], snapshot["version"]
                    ),
                }
            )
        runs = children(campaign.id)
        aggregate = getattr(client, "run_costs", None)
        costs = aggregate([run.id for run in runs]) if callable(aggregate) else None
        if costs is None:
            return jsonify({"available": False, "runs": []})
        return jsonify(
            {
                "available": True,
                "runs": [
                    {"run_id": str(run.id), **costs[str(run.id)]}
                    for run in runs
                    if str(run.id) in costs
                ],
            }
        )

    @bp.get("/<campaign_id>/structure")
    def structure(campaign_id: str):
        """A whole goal's recorded search, including work with no result."""
        campaign = load(campaign_id)
        if campaign is None:
            return _not_found("Campaign execution")
        try:
            index = int(request.args.get("goal_index", ""))
            if index < 0:
                raise ValueError
        except ValueError:
            return jsonify({"detail": "A non-negative goal_index is required."}), 400
        run_id = request.args.get("run_id")
        runs = [r for r in children(campaign.id) if str(r.id) == run_id]
        if not runs:
            return _not_found("Attack run")
        items = records(runs, goal_index=index, full=True)
        items.sort(key=lambda r: (r.created_at, str(r.id)))
        return jsonify(
            {
                "attempts": [
                    {
                        "id": str(r.id),
                        "ordinal": ordinal,
                        "run_id": str(r.run_id),
                        "bucket": result_bucket(
                            r.evaluation_status, r.evaluation_notes
                        ),
                        "notes": r.evaluation_notes,
                        "created_at": r.created_at.isoformat(),
                        "metadata": r.metadata.get("attack_metadata", {}),
                    }
                    for ordinal, r in enumerate(items, start=1)
                ],
                "traces": [
                    ser.trace(trace) for r in items for trace in client.traces(r.id)
                ],
                "results": [ser.result(r) for r in items],
            }
        )

    return bp
