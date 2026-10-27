# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Executing server-tracked runs on this machine.

- :mod:`.execute`: :func:`execute_run` and :func:`execute_spec`, shared by
  ``hackagent run``, ``hackagent campaign run`` and any other executor of
  a queued run, and the tracked run behind every campaign with remote
  storage
- :mod:`.adopted`: the store that runs a campaign inside an existing run
- :mod:`.credits`: stop a run on the gateway's first "out of credits" answer
- :mod:`.heartbeat`: the background heartbeat with cancel and rejection signals
"""

from hackagent.orchestrator.execution.adopted import AdoptedRunStore
from hackagent.orchestrator.execution.execute import (
    ExecutionOutcome,
    RunEnded,
    execute_run,
    execute_spec,
)
from hackagent.orchestrator.execution.heartbeat import RunHeartbeat

__all__ = [
    "AdoptedRunStore",
    "ExecutionOutcome",
    "RunEnded",
    "RunHeartbeat",
    "execute_run",
    "execute_spec",
]
