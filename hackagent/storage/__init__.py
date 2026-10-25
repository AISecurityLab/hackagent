# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Persistence of agents, attacks, runs, results and traces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hackagent.storage.remote import ClaimResult, ExecutorRejected, RunNotClaimable

#: Executor protocol types, loaded with the remote backend on first use so
#: that local storage never imports the HTTP client.
_REMOTE_EXPORTS = frozenset({"ClaimResult", "ExecutorRejected", "RunNotClaimable"})


def __getattr__(name: str) -> Any:
    if name in _REMOTE_EXPORTS:
        from hackagent.storage import remote

        return getattr(remote, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ClaimResult", "ExecutorRejected", "RunNotClaimable"]
