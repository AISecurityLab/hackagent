# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Offline REST surface: the HackAgent API contract served from local SQLite.

With the local backend selected, this blueprint answers dashboard requests
from the SQLite store through the facade. Local is the default backend.

``DELETE /run/<id>`` deletes a local run. Campaigns are saved to the local
store and launched on this machine: a launch runs the campaign in this process
(see :mod:`._launcher`), and its parent run and attack runs are served like any
other while their results land. The other write routes (agents, keys, the
account) return 501: they belong to the hosted service. The technique catalogue
and campaign schema need no account either.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from flask import Blueprint, jsonify, request

from hackagent.interfaces.web import _serializers as ser
from hackagent.interfaces.web._launcher import LaunchRefused, LocalLauncher, launch_spec
from hackagent.orchestrator.campaign.loader import load_stored_campaign

logger = logging.getLogger("hackagent.interfaces.web.local")

#: Page size used when the blueprint has to read a table in full to filter or
#: aggregate it. Local databases are single-user and small; the alternative is
#: pushing predicates down into LocalBackend, which would widen the storage
#: protocol for the benefit of one caller.
_SCAN_PAGE_SIZE = 10_000

_DEFAULT_PAGE_SIZE = 10


def _page_args() -> tuple[int, int]:
    """Return the requested ``(page, page_size)``, clamped to sane bounds."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get("page_size", _DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = _DEFAULT_PAGE_SIZE
    return page, max(1, min(page_size, 1000))


def _slice(items: List[Any], page: int, page_size: int) -> List[Any]:
    start = (page - 1) * page_size
    return items[start : start + page_size]


def _uuid(value: str) -> Optional[UUID]:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _not_found(what: str):
    return jsonify({"detail": f"{what} not found."}), 404


def _read_only(**_route_args):
    return (
        jsonify(
            {
                "detail": (
                    "This HackAgent dashboard is running offline against the local "
                    "database: agents, keys and the account belong to the hosted "
                    "service. A campaign run registers its target as an agent here; "
                    "configure an API key to manage them in the hosted API."
                )
            }
        ),
        501,
    )


#: Keys a saved campaign leaves to the launch: the target comes from the agent.
_SERVER_KEYS = ("target", "execution")

_CLOUD_UNAVAILABLE = {
    "code": "CLOUD_UNAVAILABLE",
    "message": "Cloud runs need a HackAgent account. Run it on this machine.",
    "details": {},
}


def _bad_request(errors: Dict[str, Any]):
    return jsonify(errors), 400


def create_local_api(client) -> Blueprint:
    """Build the offline REST blueprint backed by a facade ``client``."""
    bp = Blueprint("local_api", __name__)
    launcher = LocalLauncher(client)

    def _org_id() -> UUID:
        return client.context().org_id

    # ── Caches ───────────────────────────────────────────────────────────────
    # Run and attack payloads carry the agent's display name, so a page of runs
    # would otherwise issue one lookup per row.
    def _agent_names() -> Dict[str, str]:
        listing = client.agents(page=1, page_size=_SCAN_PAGE_SIZE)
        return {str(a.id): a.name for a in listing.items}

    def _attack_types() -> Dict[str, str]:
        listing = client.attacks(page=1, page_size=_SCAN_PAGE_SIZE)
        return {str(a.id): a.type for a in listing.items}

    def _all_runs() -> List[Any]:
        return client.runs(page=1, page_size=_SCAN_PAGE_SIZE).items

    def _launched_parents() -> set[str]:
        """Campaign runs the dashboard launched, whose attack runs ran here."""
        listing = client.campaign_runs(page=1, page_size=_SCAN_PAGE_SIZE)
        return {str(c.id) for c in listing.items if c.campaign_id is not None}

    def _executor(record: Any, launched: set[str]) -> str:
        parent = getattr(record, "campaign_run_id", None)
        return "local" if parent is not None and str(parent) in launched else "cli"

    def _child_runs(campaign_run_id: UUID) -> List[Any]:
        return [r for r in _all_runs() if r.campaign_run_id == campaign_run_id]

    def _results_of(run_id: Optional[UUID]) -> Optional[List[Any]]:
        """Every result of a campaign run (its attack runs' results), or None
        when ``run_id`` is not a campaign run."""
        if run_id is None:
            return None
        try:
            client.campaign_run(run_id)
        except RuntimeError:
            return None
        return [
            result
            for child in _child_runs(run_id)
            for result in client.results(
                run_id=child.id, page=1, page_size=_SCAN_PAGE_SIZE
            ).items
        ]

    def _campaign_run_payload(record: Any) -> Dict[str, Any]:
        return ser.campaign_run(
            record,
            agent_name=_agent_names().get(str(record.agent_id)),
            org_id=_org_id(),
            cancel_requested_at=launcher.cancel_requested_at(record.id),
        )

    # ── Identity ─────────────────────────────────────────────────────────────
    @bp.get("/user/me")
    def user_me():
        return jsonify(ser.user_profile(_org_id()))

    @bp.get("/user")
    def user_list():
        page, page_size = _page_args()
        return jsonify(ser.paginate([ser.user_profile(_org_id())], 1, page, page_size))

    @bp.get("/organization/me")
    def organization_me():
        return jsonify(ser.organization(_org_id()))

    @bp.get("/organization")
    def organization_list():
        page, page_size = _page_args()
        return jsonify(ser.paginate([ser.organization(_org_id())], 1, page, page_size))

    @bp.get("/key/context")
    def key_context():
        org_id = _org_id()
        return jsonify(
            {
                "user_id": ser.LOCAL_USER_ID,
                "username": ser.LOCAL_USERNAME,
                "organization_id": str(org_id),
                "organization_name": ser.LOCAL_ORG_NAME,
            }
        )

    # API keys and billing logs are properties of the hosted service; offline
    # there are none, and an empty page renders correctly.
    @bp.get("/key")
    @bp.get("/apilogs")
    def empty_list():
        page, page_size = _page_args()
        return jsonify(ser.paginate([], 0, page, page_size))

    @bp.get("/apilogs/summary")
    def apilogs_summary():
        """Pre-aggregated usage, which offline is always empty.

        The UI treats a failure here as "endpoint unavailable" and falls back to
        paging the full log, so answering with an empty summary is both correct
        and cheaper than letting it 404 and retry.
        """
        return jsonify({"timezone": request.args.get("tz", "UTC"), "days": []})

    # ── Agents ───────────────────────────────────────────────────────────────
    @bp.get("/agent")
    def agent_list():
        page, page_size = _page_args()
        listing = client.agents(page=page, page_size=page_size)
        items = [ser.agent(a) for a in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.get("/agent/<agent_id>")
    def agent_detail(agent_id: str):
        parsed = _uuid(agent_id)
        if parsed is None:
            return _not_found("Agent")
        try:
            return jsonify(ser.agent(client.agent(parsed)))
        except RuntimeError:
            return _not_found("Agent")

    # ── Attacks ──────────────────────────────────────────────────────────────
    @bp.get("/attack")
    def attack_list():
        page, page_size = _page_args()
        listing = client.attacks(page=page, page_size=page_size)
        names = _agent_names()
        items = [
            ser.attack(a, agent_name=names.get(str(a.agent_id))) for a in listing.items
        ]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.get("/attack/<attack_id>")
    def attack_detail(attack_id: str):
        names = _agent_names()
        for record in client.attacks(page=1, page_size=_SCAN_PAGE_SIZE).items:
            if str(record.id) == attack_id:
                return jsonify(
                    ser.attack(record, agent_name=names.get(str(record.agent_id)))
                )
        return _not_found("Attack")

    # ── Runs ─────────────────────────────────────────────────────────────────
    def _parent_list(page: int, page_size: int):
        """Campaign runs as parent runs, newest first, with their results counted."""
        parents = client.campaign_runs(page=1, page_size=_SCAN_PAGE_SIZE).items
        campaign_filter = request.args.get("campaign")
        if campaign_filter:
            parents = [c for c in parents if str(c.campaign_id) == campaign_filter]
        children: Dict[str, List[Any]] = {}
        for record in _all_runs():
            if record.campaign_run_id is not None:
                children.setdefault(str(record.campaign_run_id), []).append(record)
        items = []
        for parent in _slice(parents, page, page_size):
            results = [
                result
                for child in children.get(str(parent.id), [])
                for result in client.results(
                    run_id=child.id, page=1, page_size=_SCAN_PAGE_SIZE
                ).items
            ]
            items.append(
                {
                    **_campaign_run_payload(parent),
                    **ser.result_counts(results),
                    "attack_type": None,
                }
            )
        return jsonify(ser.paginate(items, len(parents), page, page_size))

    @bp.get("/run")
    def run_list():
        page, page_size = _page_args()
        if request.args.get("parent__isnull") == "true" or request.args.get("campaign"):
            return _parent_list(page, page_size)
        runs = _all_runs()

        agent_filter = request.args.get("agent")
        attack_filter = request.args.get("attack")
        status_filter = request.args.get("status")
        parent_filter = request.args.get("parent")
        if parent_filter:
            runs = [r for r in runs if str(r.campaign_run_id) == parent_filter]
        if agent_filter:
            runs = [r for r in runs if str(r.agent_id) == agent_filter]
        if attack_filter:
            runs = [r for r in runs if str(r.attack_id) == attack_filter]
        if status_filter:
            runs = [r for r in runs if r.status == status_filter]

        total = len(runs)
        org_id = _org_id()
        names = _agent_names()
        types = _attack_types()
        launched = _launched_parents()
        items = []
        for record in _slice(runs, page, page_size):
            results = client.results(
                run_id=record.id, page=1, page_size=_SCAN_PAGE_SIZE
            ).items
            items.append(
                ser.run_summary(
                    record,
                    results,
                    agent_name=names.get(str(record.agent_id)),
                    attack_type=types.get(str(record.attack_id)),
                    org_id=org_id,
                    executor=_executor(record, launched),
                )
            )
        return jsonify(ser.paginate(items, total, page, page_size))

    @bp.get("/run/<run_id>")
    def run_detail(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        try:
            record = client.run(parsed)
        except RuntimeError:
            # Not an attack run: a campaign run is the parent of attack runs.
            try:
                parent = client.campaign_run(parsed)
            except RuntimeError:
                return _not_found("Run")
            return jsonify(
                {
                    **_campaign_run_payload(parent),
                    **ser.result_counts(_results_of(parsed)),
                }
            )
        results = client.results(run_id=parsed, page=1, page_size=_SCAN_PAGE_SIZE).items
        payload = ser.run(
            record,
            agent_name=_agent_names().get(str(record.agent_id)),
            org_id=_org_id(),
            results=[ser.result(r, traces=client.traces(r.id)) for r in results],
            executor=_executor(record, _launched_parents()),
        )
        return jsonify(payload)

    @bp.post("/run/<run_id>/cancel")
    def run_cancel(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        try:
            record = client.campaign_run(parsed)
        except RuntimeError:
            return _not_found("Run")
        refusal = launcher.cancel(parsed)
        if refusal:
            return jsonify({"detail": refusal}), 400
        return jsonify(_campaign_run_payload(record))

    @bp.delete("/run/<run_id>")
    def run_delete(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        try:
            client.delete_run(parsed)
        except RuntimeError:
            return _not_found("Run")
        return "", 204

    @bp.get("/run/<run_id>/result")
    def run_results(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        page, page_size = _page_args()
        combined = _results_of(parsed)
        if combined is not None:
            items = [ser.result(r) for r in _slice(combined, page, page_size)]
            return jsonify(ser.paginate(items, len(combined), page, page_size))
        listing = client.results(run_id=parsed, page=page, page_size=page_size)
        items = [ser.result(r) for r in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    # ── Results ──────────────────────────────────────────────────────────────
    @bp.get("/result")
    def result_list():
        page, page_size = _page_args()
        run_filter = _uuid(request.args.get("run", ""))
        status_filter = request.args.get("evaluation_status")
        # A campaign run's results are those of its attack runs.
        combined = _results_of(run_filter)

        if status_filter or combined is not None:
            # Filtering happens after the read, so the page must be cut here
            # rather than delegated to the backend's own pagination.
            everything = (
                combined
                if combined is not None
                else client.results(
                    run_id=run_filter, page=1, page_size=_SCAN_PAGE_SIZE
                ).items
            )
            if not status_filter:
                items = [ser.result(r) for r in _slice(everything, page, page_size)]
                return jsonify(ser.paginate(items, len(everything), page, page_size))
            matching = [r for r in everything if r.evaluation_status == status_filter]
            items = [ser.result(r) for r in _slice(matching, page, page_size)]
            return jsonify(ser.paginate(items, len(matching), page, page_size))

        listing = client.results(run_id=run_filter, page=page, page_size=page_size)
        items = [ser.result(r) for r in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.get("/result/<result_id>")
    def result_detail(result_id: str):
        parsed = _uuid(result_id)
        if parsed is None:
            return _not_found("Result")
        try:
            record = client.result(parsed)
        except RuntimeError:
            return _not_found("Result")
        return jsonify(ser.result(record, traces=client.traces(parsed)))

    # ── Campaigns ────────────────────────────────────────────────────────────
    # Saved in the local store and launched on this machine.
    def _campaign_or_none(campaign_id: str) -> Optional[Any]:
        parsed = _uuid(campaign_id)
        if parsed is None:
            return None
        try:
            return client.campaign(parsed)
        except RuntimeError:
            return None

    def _campaign_errors(body: Any) -> tuple[Dict[str, Any], Optional[Any]]:
        """The errors of a campaign payload and, when it has none, its agent."""
        if not isinstance(body, dict):
            return {"detail": "Expected a JSON object."}, None
        errors: Dict[str, Any] = {}
        if not str(body.get("name") or "").strip():
            errors["name"] = ["This field is required."]
        agent = None
        agent_id = _uuid(str(body.get("agent") or ""))
        if agent_id is not None:
            try:
                agent = client.agent(agent_id)
            except RuntimeError:
                agent = None
        if agent is None:
            errors["agent"] = ["Agent not found."]
        spec = body.get("spec")
        if not isinstance(spec, dict):
            errors["spec"] = {"spec": "spec must be an object"}
        elif any(key in spec for key in _SERVER_KEYS):
            errors["spec"] = {
                key: "set by the server" for key in _SERVER_KEYS if key in spec
            }
        elif agent is not None:
            # Validated as it will launch: the agent as target, the name filled in.
            meta = {"name": str(body.get("name") or "campaign")}
            meta.update(spec.get("campaign") or {})
            try:
                load_stored_campaign(
                    {**spec, "campaign": meta, "target": agent.metadata}
                )
            except Exception as exc:
                errors["spec"] = {"spec": str(exc)}
        return errors, agent

    def _save(body: Dict[str, Any], campaign_id: Optional[UUID] = None):
        errors, agent = _campaign_errors(body)
        if errors:
            return _bad_request(errors)
        record = client.save_campaign(
            name=str(body["name"]).strip(),
            description=str(body.get("description") or ""),
            agent_id=agent.id,
            spec=body["spec"],
            campaign_id=campaign_id,
        )
        return jsonify(ser.campaign(record, org_id=_org_id())), (
            201 if campaign_id is None else 200
        )

    def _launch(campaign: Any, executor: Any):
        # Left out, the deployment decides; offline, that is this machine.
        if executor not in (None, "local"):
            return jsonify({"problems": [_CLOUD_UNAVAILABLE]}), 400
        try:
            record = launcher.launch(campaign)
        except LaunchRefused as exc:
            problem = {"code": "LAUNCH_REFUSED", "message": str(exc), "details": {}}
            return jsonify({"problems": [problem]}), 400
        return jsonify(_campaign_run_payload(record)), 201

    @bp.get("/campaign")
    def campaign_list():
        page, page_size = _page_args()
        listing = client.campaigns(page=page, page_size=page_size)
        items = [ser.campaign(c, org_id=_org_id()) for c in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.post("/campaign")
    def campaign_create():
        return _save(request.get_json(silent=True))

    @bp.post("/campaign/launch")
    def campaign_launch_adhoc():
        body = request.get_json(silent=True)
        response, status = _save(body)
        if status != 201:
            return response, status
        campaign = client.campaign(UUID(response.get_json()["id"]))
        return _launch(campaign, body.get("executor"))

    @bp.get("/campaign/<campaign_id>")
    def campaign_detail(campaign_id: str):
        campaign = _campaign_or_none(campaign_id)
        if campaign is None:
            return _not_found("Campaign")
        return jsonify(ser.campaign(campaign, org_id=_org_id()))

    @bp.route("/campaign/<campaign_id>", methods=["PUT", "PATCH"])
    def campaign_update(campaign_id: str):
        campaign = _campaign_or_none(campaign_id)
        if campaign is None:
            return _not_found("Campaign")
        body = request.get_json(silent=True)
        if request.method == "PATCH" and isinstance(body, dict):
            body = {
                "name": campaign.name,
                "description": campaign.description,
                "agent": str(campaign.agent_id),
                "spec": campaign.spec,
                **body,
            }
        return _save(body, campaign_id=campaign.id)

    @bp.delete("/campaign/<campaign_id>")
    def campaign_delete(campaign_id: str):
        campaign = _campaign_or_none(campaign_id)
        if campaign is None:
            return _not_found("Campaign")
        client.delete_campaign(campaign.id)
        return "", 204

    @bp.get("/campaign/<campaign_id>/preflight")
    def campaign_preflight(campaign_id: str):
        campaign = _campaign_or_none(campaign_id)
        if campaign is None:
            return _not_found("Campaign")
        executor = request.args.get("executor", "local")
        if executor != "local":
            return jsonify(
                {"executor": executor, "ok": False, "problems": [_CLOUD_UNAVAILABLE]}
            )
        try:
            load_stored_campaign(
                launch_spec(campaign, client.agent(campaign.agent_id), Path("."))
            )
        except Exception as exc:
            problem = {"code": "LAUNCH_REFUSED", "message": str(exc), "details": {}}
            return jsonify({"executor": executor, "ok": False, "problems": [problem]})
        return jsonify({"executor": executor, "ok": True, "problems": []})

    @bp.post("/campaign/<campaign_id>/launch")
    def campaign_launch(campaign_id: str):
        campaign = _campaign_or_none(campaign_id)
        if campaign is None:
            return _not_found("Campaign")
        body = request.get_json(silent=True) or {}
        return _launch(campaign, body.get("executor"))

    @bp.get("/campaign/techniques")
    def campaign_techniques():
        from hackagent.client import technique_catalog

        return jsonify(technique_catalog())

    @bp.get("/campaign/schema")
    def campaign_schema():
        from hackagent.datasets.presets import list_presets
        from hackagent.orchestrator.campaign.spec import campaign_json_schema

        presets = [
            {"name": name, "description": description}
            for name, description in sorted(list_presets().items())
        ]
        return jsonify({"schema": campaign_json_schema(), "dataset_presets": presets})

    # ── Write routes ─────────────────────────────────────────────────────────
    for rule, methods in (
        ("/agent", ("POST",)),
        ("/agent/<agent_id>", ("PUT", "PATCH", "DELETE")),
        ("/attack", ("POST",)),
        ("/attack/<attack_id>", ("PUT", "PATCH", "DELETE")),
        ("/run", ("POST",)),
        ("/result", ("POST",)),
        ("/key", ("POST",)),
        ("/credits/request", ("POST",)),
        ("/user/me", ("PUT", "PATCH")),
        ("/organization/<org_id>", ("PUT", "PATCH")),
    ):
        bp.add_url_rule(
            rule,
            endpoint=f"read_only_{rule}_{'_'.join(methods)}",
            view_func=_read_only,
            methods=list(methods),
        )

    return bp


__all__ = ["create_local_api"]
