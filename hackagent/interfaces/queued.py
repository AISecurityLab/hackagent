# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Runs queued from the dashboard for a local machine, run here: by
``hackagent run`` and by the TUI's Queued runs screen, with the same checks.

A queued run is refused (:class:`Refused`) before it is claimed when this
machine cannot run it: a key the server rejects, a run that is not queued
for a local machine or no longer queued, a campaign this version of
HackAgent cannot load, or model keys missing from the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

#: Exit codes of ``hackagent run`` when a run is refused.
REFUSED, INVALID_KEY = 1, 2


class Refused(Exception):
    """Why this machine will not run a queued run; ``code`` is the exit code
    ``hackagent run`` ends with, ``missing`` the variables to set."""

    def __init__(
        self, message: str, code: int = REFUSED, missing: tuple[str, ...] = ()
    ) -> None:
        super().__init__(message)
        self.code = code
        self.missing = missing


@dataclass
class Ready:
    """A queued run that passed the checks: its id and its campaign, and
    what is worth knowing before it starts."""

    run_id: UUID
    spec: Any
    warnings: list[str] = field(default_factory=list)


def connect(settings: Any) -> Any:
    """The remote store, its key checked."""
    from hackagent.storage import InvalidApiKey
    from hackagent.storage.remote import RemoteBackend

    store = RemoteBackend.connect(
        settings.base_url, settings.api_key, verify=settings.verify
    )
    try:
        store.check_key()
    except InvalidApiKey:
        store.close(close_client=True)
        raise Refused(
            "Your API key is not valid. Set one with: export HACKAGENT_API_KEY=<key>",
            INVALID_KEY,
        ) from None
    return store


def queued_runs(store: Any) -> list[dict[str, Any]]:
    """The runs queued for a local machine, newest first."""
    return store.list_queued_local_runs()


def prepare(store: Any, run_id: str, settings: Any) -> Ready:
    """The queued run ``run_id``, checked; :class:`Refused` when it cannot
    run here."""
    from hackagent.orchestrator.execution.execute import executable_spec

    try:
        run_uuid = UUID(str(run_id))
    except ValueError:
        raise Refused(f"'{run_id}' is not a run id.") from None
    detail = store.get_run_detail(run_uuid)
    _refuse_unless_runnable(detail)
    run_config = detail.get("run_config") or {}
    warnings = _sdk_warnings(run_config)
    try:
        spec = executable_spec(run_config["campaign_config"], settings.base_url)
    except Exception as exc:
        raise Refused(f"This run's campaign cannot be loaded: {exc}") from exc
    _check_environment(spec)
    return Ready(run_uuid, spec, warnings)


def execute(store: Any, ready: Ready, settings: Any) -> Any:
    """Claim the run and execute it here; its outcome. Raises
    :class:`~hackagent.storage.RunNotClaimable` when another machine was
    first."""
    from hackagent.orchestrator.execution import execute_run
    from hackagent.storage.remote import _local_executor

    return execute_run(
        store,
        ready.run_id,
        base_url=settings.base_url,
        gateway_key=settings.api_key,
        claimed_by=_local_executor(),
        settings=settings,
    )


def follow_url(settings: Any, run_id: UUID) -> Optional[str]:
    """Where the dashboard shows the run, when it is known."""
    if not settings.dashboard_url:
        return None
    return f"{settings.dashboard_url}/runs?run={run_id}"


def _refuse_unless_runnable(detail: dict[str, Any]) -> None:
    status = detail.get("status")
    if detail.get("executor") != "local":
        raise Refused(
            f"This run executes on '{detail.get('executor')}', not on a local "
            "machine, so it cannot be run here."
        )
    if status != "PENDING":
        raise Refused(
            f"This run is {status}; only a queued (PENDING) run can be started."
        )
    if detail.get("claimed_by"):
        raise Refused(f"This run was already claimed by {detail['claimed_by']}.")


def _sdk_warnings(run_config: dict[str, Any]) -> list[str]:
    from packaging.version import InvalidVersion, Version

    from hackagent._version import get_version

    needed = run_config.get("sdk_version")
    if not needed:
        return []
    try:
        have, want = Version(get_version()), Version(str(needed))
    except InvalidVersion:
        return []
    if have < want:
        raise Refused(
            f"This run needs hackagent {needed} or newer: pip install -U hackagent"
        )
    if have > want:
        return [f"This run was queued with hackagent {needed}; you have {have}."]
    return []


def _check_environment(spec: Any) -> None:
    from hackagent.orchestrator.campaign.gateway import key_envs

    missing = tuple(sorted(key_envs(spec) - os.environ.keys()))
    if missing:
        raise Refused(
            "Set these variables with your model keys, then run again:",
            missing=missing,
        )


__all__ = [
    "INVALID_KEY",
    "REFUSED",
    "Ready",
    "Refused",
    "connect",
    "execute",
    "follow_url",
    "prepare",
    "queued_runs",
]
