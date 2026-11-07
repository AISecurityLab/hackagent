# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Persist the expensive dashboard read models outside HTTP requests."""

from __future__ import annotations

import logging
import os
import socket
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

from hackagent.storage.local import LocalBackend

logger = logging.getLogger(__name__)
VERSION = 11


class DashboardCache:
    def __init__(self, backend: LocalBackend) -> None:
        self.backend = backend
        self.owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="dashboard-summaries", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self.backend.release_dashboard_worker(self.owner)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.backend.dashboard_refresh_candidates(VERSION):
                    with self.backend.dashboard_writer() as writer:
                        self.refresh(writer)
                self.error = None
            except (sqlite3.Error, ValueError, RuntimeError):
                logger.exception(
                    "Dashboard summary refresh failed; keeping previous snapshots"
                )
                self.error = "Dashboard summary refresh failed. Previous data is retained; retrying."
            self._stop.wait(30)

    def refresh(self, writer: LocalBackend | None = None) -> None:
        store = writer if writer is not None else self.backend
        if not store.dashboard_refresh_candidates(VERSION):
            return
        now = time.time()
        if not store.claim_dashboard_worker(self.owner, now, now + 300):
            return
        try:
            generated_at = datetime.now(timezone.utc).isoformat()
            with store.dashboard_read_snapshot() as source:
                from hackagent import HackAgent, Settings
                from ._history import create_history_reader

                reader = create_history_reader(
                    HackAgent(
                        Settings.resolve(
                            backend="local", env={}, config_path="/nonexistent"
                        ),
                        backend=source,
                    )
                )
                candidates = source.dashboard_refresh_candidates(VERSION)
                for offset in range(0, len(candidates), 100):
                    batch = candidates[offset : offset + 100]
                    stored = source.dashboard_snapshots(batch)
                    for campaign_id in batch:
                        if self._stop.is_set():
                            return
                        campaign = source.get_campaign_run(campaign_id)
                        now = time.time()
                        if not store.claim_dashboard_worker(self.owner, now, now + 300):
                            return
                        revision = source.dashboard_revision(campaign.id)
                        finalized = source.dashboard_can_finalize(campaign.id)
                        previous = stored.get(str(campaign.id))
                        if (
                            previous
                            and previous["version"] == VERSION
                            and previous["source_revision"] == revision
                            and previous["finalized"] == finalized
                        ):
                            continue
                        run_ids = source.dashboard_run_ids(campaign.id)
                        counts = source.campaign_outcomes([campaign.id])[
                            str(campaign.id)
                        ]
                        costs = source.run_costs(run_ids)
                        summary = {
                            "id": str(campaign.id),
                            "name": campaign.name,
                            "target": source.get_agent(campaign.agent_id).name,
                            "status": campaign.status,
                            "created_at": campaign.created_at.isoformat(),
                            "updated_at": campaign.updated_at.isoformat(),
                            **counts,
                        }
                        store.save_dashboard_snapshot(
                            campaign.id,
                            VERSION,
                            revision,
                            generated_at,
                            summary,
                            {
                                "available": True,
                                "runs": [
                                    {"run_id": str(ident), **costs[str(ident)]}
                                    for ident in run_ids
                                    if str(ident) in costs
                                ],
                            },
                            finalized=finalized,
                            detail=reader.detail(campaign, None),
                            goals=reader.goals(campaign),
                        )
        finally:
            store.release_dashboard_worker(self.owner)

    def read(self, ids: list[uuid.UUID]) -> dict:
        return {
            ident: snapshot
            for ident, snapshot in self.backend.dashboard_snapshots(ids).items()
            if 2 <= snapshot["version"] <= VERSION
        }

    def metadata(self, generated_at: str, version: int = VERSION) -> dict:
        return {
            "generated_at": generated_at,
            "refresh_interval_s": 30,
            "refresh_error": self.error,
            "upgrading": version < VERSION,
        }
