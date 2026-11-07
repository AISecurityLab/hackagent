# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Launch saved campaigns from the offline dashboard, in this process.

Offline there is no server to queue a run for a worker, and the machine
serving the dashboard is the one whose targets and models the campaign uses.
So a launch runs the campaign right here, in a background thread, recording
into the dashboard's own store: the run pages follow it as its results land.

The thread lives as long as ``hackagent web``; stopping the server ends any
run still going.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from hackagent.orchestrator.campaign import (
    CampaignCancelled,
    resolve_campaign,
    run_campaign,
)
from hackagent.orchestrator.campaign.loader import load_stored_campaign

logger = logging.getLogger("hackagent.interfaces.web.launcher")

#: How long a launch waits for the run to be recorded before giving up on it.
_START_TIMEOUT_S = 60.0


class LaunchRefused(Exception):
    """The campaign cannot be launched; the message says why."""


class _Cancelled(CampaignCancelled):
    """Raised from the event callback when the dashboard cancels the run."""


class _RecordingStore:
    """The dashboard's store, reporting the campaign run the runner starts."""

    def __init__(self, backend: Any, on_start) -> None:
        self._backend = backend
        self._on_start = on_start

    def start_campaign(self, agent_id: UUID, spec: Dict[str, Any]) -> Any:
        record = self._backend.start_campaign(agent_id, spec)
        self._on_start(record)
        return record

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)


def launch_spec(campaign: Any, agent: Any, output_root: Path) -> Dict[str, Any]:
    """The full spec a saved campaign runs with: the agent's config as target,
    local storage, and run files under ``output_root``."""
    spec = {
        **campaign.spec,
        "target": agent.metadata,
        "execution": {"output": {"directory": str(output_root)}},
    }
    meta = dict(spec.get("campaign") or {})
    meta.setdefault("name", campaign.name)
    spec["campaign"] = meta
    return spec


class LocalLauncher:
    """Runs launched campaigns and cancels them on request."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._cancels: Dict[UUID, threading.Event] = {}
        self._cancel_requested: Dict[UUID, datetime] = {}
        self._lock = threading.Lock()

    def _output_root(self) -> Path:
        db_path = self._client.settings.db_path
        base = (
            Path.cwd() if db_path == ":memory:" else Path(db_path).expanduser().parent
        )
        return base / "runs"

    def launch(self, campaign: Any) -> Any:
        """Start ``campaign`` and return its campaign run once it is recorded.

        Raises :class:`LaunchRefused` when the campaign does not validate or
        its goals and models cannot be resolved; nothing is recorded then.
        """
        try:
            agent = self._client.agent(campaign.agent_id)
        except RuntimeError:
            raise LaunchRefused("The campaign's target agent no longer exists.")
        try:
            spec = load_stored_campaign(
                launch_spec(campaign, agent, self._output_root())
            )
            resolved = resolve_campaign(spec, settings=self._client.settings)
        except Exception as exc:
            raise LaunchRefused(str(exc)) from None

        started = threading.Event()
        cancel = threading.Event()
        state: Dict[str, Any] = {}

        def on_start(record: Any) -> None:
            state["record"] = record
            with self._lock:
                self._cancels[record.id] = cancel
            started.set()

        def on_event(event_type: str, **payload: Any) -> None:
            if cancel.is_set():
                raise _Cancelled("Cancelled from the dashboard")

        def work() -> None:
            try:
                run_campaign(
                    spec,
                    store=_RecordingStore(self._client.backend, on_start),
                    settings=self._client.settings,
                    resolved=resolved,
                    on_event=on_event,
                )
            except BaseException as exc:  # recorded on the run by the runner
                state.setdefault("error", exc)
                logger.warning("campaign %s ended: %s", campaign.name, exc)
            finally:
                started.set()
                record = state.get("record")
                if record is not None:
                    with self._lock:
                        self._cancels.pop(record.id, None)

        threading.Thread(
            target=work, name=f"campaign-{campaign.id}", daemon=True
        ).start()
        if not started.wait(_START_TIMEOUT_S) or "record" not in state:
            raise LaunchRefused(
                str(state.get("error") or "The campaign did not start in time.")
            )
        record = state["record"]
        self._client.backend.link_campaign_run(record.id, campaign.id)
        return self._client.campaign_run(record.id)

    def cancel_requested_at(self, campaign_run_id: UUID) -> Optional[datetime]:
        with self._lock:
            return self._cancel_requested.get(campaign_run_id)

    def cancel(self, campaign_run_id: UUID) -> Optional[str]:
        """Ask a run to stop at its next step; returns why it cannot, or None."""
        with self._lock:
            cancel = self._cancels.get(campaign_run_id)
            if cancel is None:
                return "This run is not running in this dashboard."
            self._cancel_requested.setdefault(
                campaign_run_id, datetime.now(timezone.utc)
            )
        cancel.set()
        return None


__all__ = ["LaunchRefused", "LocalLauncher", "launch_spec"]
