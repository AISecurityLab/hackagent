# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Remote mode: run on this machine the campaigns the dashboard launches.

``hackagent web`` launches every campaign as a local run (``_proxy``), and
this process is the local machine: it claims and executes each run it
launched, the way ``hackagent run`` does, with this environment providing the
model keys. The dashboard follows the run live, as it follows a cloud run.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional
from uuid import UUID

from hackagent.core.settings import Settings

logger = logging.getLogger("hackagent.interfaces.web.remote_launcher")


def missing_environment(spec) -> Optional[str]:
    """Why this process cannot run ``spec``: model keys its environment lacks."""
    from hackagent.orchestrator.campaign.gateway import key_envs

    missing = sorted(key_envs(spec) - os.environ.keys())
    if not missing:
        return None
    return (
        f"Set {', '.join(missing)} in the environment of hackagent web, "
        "restart it and launch again."
    )


class RemoteLauncher:
    """Executes runs in the background, one thread per run.

    The threads are daemons: stopping ``hackagent web`` stops its runs, which
    the server then fails once their heartbeat stops.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def __call__(self, run_id: UUID) -> None:
        threading.Thread(
            target=self._run, args=(run_id,), name=f"run-{run_id}", daemon=True
        ).start()

    def _run(self, run_id: UUID) -> None:
        from hackagent.orchestrator.execution import execute_run
        from hackagent.storage import RunNotClaimable
        from hackagent.storage.remote import RemoteBackend, _local_executor

        settings = self._settings
        store = RemoteBackend.connect(
            settings.base_url, settings.api_key, verify=settings.verify
        )
        try:
            logger.info("Running %s on this machine", run_id)
            outcome = execute_run(
                store,
                run_id,
                base_url=settings.base_url,
                gateway_key=settings.api_key,
                claimed_by=_local_executor(),
                settings=settings,
                check=missing_environment,
            )
            logger.info("Run %s %s %s", run_id, outcome.status.lower(), outcome.note)
        except RunNotClaimable as exc:
            logger.warning("Run %s was not started: %s", run_id, exc.note)
        except Exception:
            logger.exception("Run %s could not be executed", run_id)
        finally:
            store.close(close_client=True)


__all__ = ["RemoteLauncher", "missing_environment"]
