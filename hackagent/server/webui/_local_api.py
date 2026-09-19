# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Offline REST surface: the HackAgent API contract served from local SQLite.

When no API key is configured there is no remote to proxy to, so this blueprint
answers the same routes ``api.hackagent.dev`` exposes, reading from the
``LocalBackend`` the SDK writes its runs into. The bundled SPA therefore works
unchanged offline.

Scope is deliberately **read-only**. Launching an attack needs a generator, a
judge and credits, none of which exist offline, so the write routes answer 501
with a message pointing at the CLI rather than failing somewhere deeper.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from flask import Blueprint, jsonify, request

from hackagent.server.webui import _serializers as ser

logger = logging.getLogger("hackagent.server.webui.local")

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


def _read_only():
    return (
        jsonify(
            {
                "detail": (
                    "This HackAgent dashboard is running offline against the local "
                    "database and is read-only. Launch attacks with the CLI "
                    "(`hackagent attack`), or configure an API key to use the "
                    "hosted API."
                )
            }
        ),
        501,
    )


def create_local_api(backend) -> Blueprint:
    """Build the offline REST blueprint backed by ``backend``."""
    bp = Blueprint("local_api", __name__)

    def _org_id() -> UUID:
        return backend.get_context().org_id

    # ── Caches ───────────────────────────────────────────────────────────────
    # Run and attack payloads carry the agent's display name, so a page of runs
    # would otherwise issue one lookup per row.
    def _agent_names() -> Dict[str, str]:
        listing = backend.list_agents(page=1, page_size=_SCAN_PAGE_SIZE)
        return {str(a.id): a.name for a in listing.items}

    def _attack_types() -> Dict[str, str]:
        listing = backend.list_attacks(page=1, page_size=_SCAN_PAGE_SIZE)
        return {str(a.id): a.type for a in listing.items}

    def _all_runs() -> List[Any]:
        return backend.list_runs(page=1, page_size=_SCAN_PAGE_SIZE).items

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

    # ── Agents ───────────────────────────────────────────────────────────────
    @bp.get("/agent")
    def agent_list():
        page, page_size = _page_args()
        listing = backend.list_agents(page=page, page_size=page_size)
        items = [ser.agent(a) for a in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.get("/agent/<agent_id>")
    def agent_detail(agent_id: str):
        parsed = _uuid(agent_id)
        if parsed is None:
            return _not_found("Agent")
        try:
            return jsonify(ser.agent(backend.get_agent(parsed)))
        except RuntimeError:
            return _not_found("Agent")

    # ── Attacks ──────────────────────────────────────────────────────────────
    @bp.get("/attack")
    def attack_list():
        page, page_size = _page_args()
        listing = backend.list_attacks(page=page, page_size=page_size)
        names = _agent_names()
        items = [
            ser.attack(a, agent_name=names.get(str(a.agent_id))) for a in listing.items
        ]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.get("/attack/<attack_id>")
    def attack_detail(attack_id: str):
        names = _agent_names()
        for record in backend.list_attacks(page=1, page_size=_SCAN_PAGE_SIZE).items:
            if str(record.id) == attack_id:
                return jsonify(
                    ser.attack(record, agent_name=names.get(str(record.agent_id)))
                )
        return _not_found("Attack")

    # ── Runs ─────────────────────────────────────────────────────────────────
    @bp.get("/run")
    def run_list():
        page, page_size = _page_args()
        runs = _all_runs()

        agent_filter = request.args.get("agent")
        attack_filter = request.args.get("attack")
        status_filter = request.args.get("status")
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
        items = []
        for record in _slice(runs, page, page_size):
            results = backend.list_results(
                run_id=record.id, page=1, page_size=_SCAN_PAGE_SIZE
            ).items
            items.append(
                ser.run_summary(
                    record,
                    results,
                    agent_name=names.get(str(record.agent_id)),
                    attack_type=types.get(str(record.attack_id)),
                    org_id=org_id,
                )
            )
        return jsonify(ser.paginate(items, total, page, page_size))

    @bp.get("/run/<run_id>")
    def run_detail(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        try:
            record = backend.get_run(parsed)
        except RuntimeError:
            return _not_found("Run")
        results = backend.list_results(
            run_id=parsed, page=1, page_size=_SCAN_PAGE_SIZE
        ).items
        payload = ser.run(
            record,
            agent_name=_agent_names().get(str(record.agent_id)),
            org_id=_org_id(),
            results=[ser.result(r, traces=backend.list_traces(r.id)) for r in results],
        )
        return jsonify(payload)

    @bp.delete("/run/<run_id>")
    def run_delete(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        try:
            backend.delete_run(parsed)
        except RuntimeError:
            return _not_found("Run")
        return "", 204

    @bp.get("/run/<run_id>/result")
    def run_results(run_id: str):
        parsed = _uuid(run_id)
        if parsed is None:
            return _not_found("Run")
        page, page_size = _page_args()
        listing = backend.list_results(run_id=parsed, page=page, page_size=page_size)
        items = [ser.result(r) for r in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    # ── Results ──────────────────────────────────────────────────────────────
    @bp.get("/result")
    def result_list():
        page, page_size = _page_args()
        run_filter = _uuid(request.args.get("run", ""))
        status_filter = request.args.get("evaluation_status")

        if status_filter:
            # Filtering happens after the read, so the page must be cut here
            # rather than delegated to the backend's own pagination.
            everything = backend.list_results(
                run_id=run_filter, page=1, page_size=_SCAN_PAGE_SIZE
            ).items
            matching = [r for r in everything if r.evaluation_status == status_filter]
            items = [ser.result(r) for r in _slice(matching, page, page_size)]
            return jsonify(ser.paginate(items, len(matching), page, page_size))

        listing = backend.list_results(
            run_id=run_filter, page=page, page_size=page_size
        )
        items = [ser.result(r) for r in listing.items]
        return jsonify(ser.paginate(items, listing.total, page, page_size))

    @bp.get("/result/<result_id>")
    def result_detail(result_id: str):
        parsed = _uuid(result_id)
        if parsed is None:
            return _not_found("Result")
        try:
            record = backend.get_result(parsed)
        except RuntimeError:
            return _not_found("Result")
        return jsonify(ser.result(record, traces=backend.list_traces(parsed)))

    # ── Write routes ─────────────────────────────────────────────────────────
    for rule, methods in (
        ("/agent", ("POST",)),
        ("/agent/<agent_id>", ("PUT", "PATCH", "DELETE")),
        ("/attack", ("POST",)),
        ("/attack/<attack_id>", ("PUT", "PATCH", "DELETE")),
        ("/run", ("POST",)),
        ("/run/run_tests", ("POST",)),
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
