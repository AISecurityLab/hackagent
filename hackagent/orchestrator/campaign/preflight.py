# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Check that a campaign's models answer before it starts attacking.

Building a model validates its configuration but sends nothing, so a wrong
endpoint or a down server only shows up on the first real call — after the
run has started and partly recorded. When ``execution.preflight`` is on, the
target and every judge are pinged first, and an unreachable one stops the
run with a message naming it rather than a wall of mid-run errors.

Roles and embedders are not pinged: they sit behind the per-attack
completion callables, and their first use surfaces the same error. The
target and the panel are what every attack and every verdict depend on, so
they are the ones worth a check up front.
"""

from __future__ import annotations

import asyncio

from hackagent.core.contracts import Sample
from hackagent.core.logging import get_logger
from hackagent.models import Model
from hackagent.orchestrator.campaign.resolve import ResolvedCampaign

logger = get_logger(__name__)

#: The smallest prompt that still exercises the request path.
_PING = [{"role": "user", "content": "ping"}]
_PING_SAMPLE = Sample(goal="ping", prompt="ping", response="ping")


class PreflightError(RuntimeError):
    """One or more of a campaign's models could not be reached."""

    def __init__(self, failures: list[str]) -> None:
        self.failures = failures
        joined = "; ".join(failures)
        super().__init__(f"Preflight failed: {joined}.")


async def preflight(resolved: ResolvedCampaign) -> None:
    """Ping the target and judges; raise :class:`PreflightError` on any failure."""
    checks = [_reach_target(resolved.target)]
    panel = resolved.panel
    if panel is not None:
        checks += [_reach_judge(judge) for judge in panel.judges]

    results = await asyncio.gather(*checks)
    failures = [message for message in results if message is not None]
    if failures:
        raise PreflightError(failures)
    logger.info("preflight | %d model(s) reachable", len(results))


async def _reach_target(target: Model) -> str | None:
    try:
        response = await target.acomplete(_PING)
    except Exception as exc:
        return f"target unreachable ({type(exc).__name__}: {exc})"
    if response.error is not None:
        return f"target error ({response.error.category}): {response.error.message}"
    return None


async def _reach_judge(judge: object) -> str | None:
    """A judge never raises: an unreachable one abstains with the reason.

    Abstention is normal for an *ambiguous* reply, but on the ``ping`` sample
    it means the classifier could not be reached, which is what preflight is
    for.
    """
    name = getattr(judge, "name", "judge")
    try:
        vote = await judge.avote(_PING_SAMPLE)  # type: ignore[attr-defined]
    except Exception as exc:
        return f"judge {name!r} unreachable ({type(exc).__name__}: {exc})"
    if vote.abstained:
        return f"judge {name!r} unreachable ({vote.error})"
    return None


__all__ = ["PreflightError", "preflight"]
