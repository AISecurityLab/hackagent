# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Endpoint overrides and local-server readiness for running a campaign file.

A campaign file pins each model's endpoint, but the servers a run actually
reaches are often decided at launch (a SLURM job, a notebook, a one-off CLI
run). These helpers rewrite a campaign's model connections to point at the
servers given at run time, and wait for local servers to come up and serve the
models the campaign needs. They operate on the plain dict a
:class:`CampaignSpec` dumps to, so a caller can edit connections in place and
re-validate.

The CLI ``campaign`` command and ``scripts/run_campaign.py`` both build on
these; neither logic lives in the other.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterator, Optional
from urllib.error import HTTPError
from urllib.request import urlopen

from hackagent.core.contracts import AgentType


@dataclass(frozen=True)
class EndpointOverrides:
    """Run-time endpoints to point campaign models at.

    ``ollama`` repoints every (Ollama) model. The OpenAI-compatible overrides
    split by role: ``openai`` moves the target and the judges sharing its
    server, ``judge`` moves the other judges, ``attacker`` moves attack role
    models. ``ollama`` cannot be combined with the OpenAI-compatible ones.
    """

    ollama: Optional[str] = None
    openai: Optional[str] = None
    judge: Optional[str] = None
    attacker: Optional[str] = None

    def any_openai(self) -> bool:
        return bool(self.openai or self.judge or self.attacker)

    def any(self) -> bool:
        return bool(self.ollama) or self.any_openai()


@dataclass(frozen=True)
class ServerReadiness:
    """How long to wait for local servers, and the pids to watch."""

    wait_for_ollama: float = 0.0
    ollama_pid: Optional[int] = None
    wait_for_server: float = 0.0
    server_pid: Optional[int] = None
    judge_server_pid: Optional[int] = None
    attacker_server_pid: Optional[int] = None


def campaign_models(values: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(kind, model)`` for every model a campaign names.

    ``kind`` is ``target``, ``role`` or ``judge``. Models are the mutable
    dicts of ``values``, so callers can rewrite their connections in place.
    """
    yield "target", values["target"]
    for attack in values["attacks"]:
        for model in attack["roles"].values():
            yield "role", model
    for judge in values["evaluation"]["judges"]:
        yield "judge", judge
    # Placed like a judge: it follows the target when it shares its server.
    if values["dataset"].get("classifier"):
        yield "judge", values["dataset"]["classifier"]


def installed_models(
    endpoint: str,
    timeout: float,
    server_pid: int | None = None,
    *,
    provider: str = "ollama",
) -> set[str]:
    """Wait for readiness and return installed or served model identifiers."""
    ollama = provider == "ollama"
    label = "Ollama" if ollama else "OpenAI-compatible server"
    path = "/api/tags" if ollama else "/models"
    deadline = time.monotonic() + timeout
    while True:
        if server_pid is not None:
            try:
                os.kill(server_pid, 0)
            except ProcessLookupError as exc:
                raise RuntimeError(
                    f"{label} exited before becoming ready; inspect server logs"
                ) from exc
        try:
            with urlopen(f"{endpoint.rstrip('/')}{path}", timeout=3) as response:
                payload = json.load(response)
            return (
                {model["name"] for model in payload["models"]}
                if ollama
                else {model["id"] for model in payload["data"]}
            )
        except OSError as exc:
            if isinstance(exc, HTTPError) and exc.code == 500:
                raise RuntimeError(
                    f"{label} readiness request failed with HTTP 500 at "
                    f"{endpoint}; inspect server logs"
                ) from exc
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"{label} is not ready at {endpoint}: {exc}"
                ) from exc
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))


def apply_endpoint_overrides(
    values: dict[str, Any], overrides: EndpointOverrides
) -> None:
    """Point a campaign's models at ``overrides``' servers, in place.

    Raises:
        ValueError: if the overrides do not fit the campaign's model
            connections (wrong wire type, no role model to point at, or
            Ollama mixed with OpenAI-compatible overrides).
    """
    if overrides.ollama and overrides.any_openai():
        raise ValueError(
            "Ollama and OpenAI-compatible endpoint overrides cannot be combined"
        )
    models = list(campaign_models(values))
    if overrides.attacker and not any(kind == "role" for kind, _ in models):
        raise ValueError("an attacker endpoint requires an attack with a role model")
    if overrides.ollama:
        for _, model in models:
            if model["connection"]["type"].upper() != "OLLAMA":
                raise ValueError("an Ollama endpoint requires Ollama model connections")
            model["connection"]["endpoint"] = overrides.ollama
    if not overrides.any_openai():
        return
    target_endpoint = values["target"]["connection"]["endpoint"]
    for kind, model in models:
        connection = model["connection"]
        if AgentType.parse(connection["type"]) is not AgentType.OPENAI:
            raise ValueError(
                "OpenAI-compatible endpoint overrides require OPENAI connections"
            )
        if kind == "role":
            if overrides.attacker:
                connection["endpoint"] = overrides.attacker
        elif kind == "target" or connection["endpoint"] == target_endpoint:
            # Judges served by the target's server follow the target.
            if overrides.openai:
                connection["endpoint"] = overrides.openai
        elif overrides.judge:
            connection["endpoint"] = overrides.judge


def wait_for_servers(values: dict[str, Any], readiness: ServerReadiness) -> None:
    """Wait for every local server and check it serves the models it must.

    Raises:
        ValueError: if a local model has no endpoint.
        RuntimeError: if a server never becomes ready or lacks a model.
    """
    required: dict[tuple[str, str], set[str]] = {}
    kinds: dict[str, str] = {}
    for kind, model in campaign_models(values):
        connection = model["connection"]
        wire = AgentType.parse(connection["type"])
        if wire is AgentType.OLLAMA or (
            wire is AgentType.OPENAI and connection["provider"] == "vllm"
        ):
            wire = "ollama" if wire is AgentType.OLLAMA else "openai"
            endpoint = connection["endpoint"]
            if not endpoint:
                raise ValueError("local model servers require an explicit endpoint")
            required.setdefault((wire, endpoint), set()).add(model["name"])
            kinds.setdefault(endpoint, kind)
    pids = {
        "target": readiness.server_pid,
        "role": readiness.attacker_server_pid,
        "judge": readiness.judge_server_pid,
    }
    for (wire, endpoint), names in required.items():
        if wire == "ollama":
            available = installed_models(
                endpoint, readiness.wait_for_ollama, readiness.ollama_pid
            )
            label = "downloaded Ollama"
        else:
            available = installed_models(
                endpoint,
                readiness.wait_for_server,
                pids[kinds[endpoint]],
                provider="openai",
            )
            label = "served OpenAI-compatible"
        missing = names - available
        if missing:
            raise RuntimeError(
                f"Missing {label} models at {endpoint}: {', '.join(sorted(missing))}"
            )


__all__ = [
    "EndpointOverrides",
    "ServerReadiness",
    "apply_endpoint_overrides",
    "campaign_models",
    "installed_models",
    "wait_for_servers",
]
