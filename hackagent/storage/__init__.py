# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Persistence of agents, attacks, runs, results and traces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hackagent.storage.remote import ClaimResult as ClaimResult
    from hackagent.storage.remote import ExecutorRejected as ExecutorRejected
    from hackagent.storage.remote import InvalidApiKey as InvalidApiKey
    from hackagent.storage.remote import RunNotClaimable as RunNotClaimable

#: Executor protocol types, loaded with the remote backend on first use so
#: that local storage never imports the HTTP client. They are left out of
#: ``__all__`` so that a star import stays local too.
_REMOTE_EXPORTS = frozenset(
    {"ClaimResult", "ExecutorRejected", "InvalidApiKey", "RunNotClaimable"}
)


def __getattr__(name: str) -> Any:
    if name in _REMOTE_EXPORTS:
        from hackagent.storage import remote

        return getattr(remote, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
