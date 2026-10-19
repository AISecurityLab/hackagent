# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Check that every model a campaign uses answers before it starts attacking.

Building a model validates its configuration but sends nothing, so a wrong
endpoint or a down server only shows up on the first real call — after the
run has started and partly recorded. When ``execution.preflight`` is on, every
model is checked first: the target, its guardrails, each attack's roles and
embedders, the judges and the goal classifier. How a model is checked is its
own business (:meth:`Model.is_reachable`); preflight only decides which ones,
checks each distinct model once, and reports every failure together.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from hackagent.core.logging import get_logger
from hackagent.models import Model, ModelConfig, Reachability, embedder_is_reachable
from hackagent.orchestrator.campaign.spec import CampaignSpec

if TYPE_CHECKING:
    from hackagent.orchestrator.campaign.resolve import ResolvedCampaign

logger = get_logger(__name__)


@dataclass(frozen=True)
class Probe:
    """One distinct model, every place the campaign uses it, and its check."""

    name: str
    uses: tuple[str, ...]
    check: Callable[[], Awaitable[Reachability]]
    timeout: float


class PreflightError(RuntimeError):
    """One or more of a campaign's models could not be reached."""

    def __init__(self, failures: list[str]) -> None:
        self.failures = failures
        joined = "; ".join(failures)
        super().__init__(f"Preflight failed: {joined}.")


def campaign_models(spec: CampaignSpec) -> Iterator[tuple[str, ModelConfig]]:
    """Yield ``(where, config)`` for every model ``spec`` uses."""
    yield "target", spec.target
    for side in ("before", "after"):
        guardrail = getattr(spec.guardrails, side)
        if guardrail is not None:
            yield f"guardrails.{side}", guardrail
    for index, attack in enumerate(spec.attacks):
        for role, model in attack.roles.items():
            yield f"attacks[{index}].{attack.name}.{role}", model
    for index, judge in enumerate(spec.evaluation.judges):
        yield f"evaluation.judges[{index}]", judge
    if spec.dataset.classifier is not None:
        yield "dataset.classifier", spec.dataset.classifier


def model_probes(
    spec: CampaignSpec,
    models: Mapping[int, Model],
    embedders: Mapping[int, Any],
) -> tuple[Probe, ...]:
    """One probe per distinct model, from what resolution built.

    ``models`` and ``embedders`` map ``id(config)`` to what was built from
    that config. A model the campaign uses in several places is checked once.
    """
    checks: dict[tuple[Any, ...], Probe] = {}
    uses: dict[tuple[Any, ...], list[str]] = {}
    for where, config in campaign_models(spec):
        key = id(config)
        if key in embedders:
            kind = "embed"
            check: Callable[[], Awaitable[Reachability]] = partial(
                embedder_is_reachable, embedders[key]
            )
        elif key in models:
            kind, check = "chat", models[key].is_reachable
        else:
            continue
        connection = config.connection
        identity = (kind, config.name, connection.type, connection.endpoint)
        checks.setdefault(identity, Probe(config.name, (), check, connection.timeout))
        uses.setdefault(identity, []).append(where)
    return tuple(
        Probe(probe.name, tuple(uses[identity]), probe.check, probe.timeout)
        for identity, probe in checks.items()
    )


async def preflight(resolved: "ResolvedCampaign") -> None:
    """Check every model; raise :class:`PreflightError` naming each failure."""
    probes = resolved.probes
    results = await asyncio.gather(*(_run(probe) for probe in probes))
    failures = [
        f"{probe.name} ({', '.join(probe.uses)}): {result.detail}"
        for probe, result in zip(probes, results)
        if not result
    ]
    if failures:
        raise PreflightError(failures)
    logger.info("preflight | %d model(s) reachable", len(results))


async def _run(probe: Probe) -> Reachability:
    try:
        return await asyncio.wait_for(probe.check(), timeout=probe.timeout)
    except asyncio.TimeoutError:
        return Reachability(False, f"no answer within {probe.timeout:g}s")


__all__ = ["PreflightError", "Probe", "campaign_models", "model_probes", "preflight"]
