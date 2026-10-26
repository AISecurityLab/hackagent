# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every example campaign must still resolve against the code it attacks.

Validating the YAML only checks its shape. Resolution is what catches an
attack parameter that was renamed, a role that became required, or a judge
type that no longer exists — the ways an example rots without anyone
noticing, because nobody runs the examples in CI.

Nothing is sent anywhere: the models are fakes and no goal is attacked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest
import yaml

from hackagent.core.contracts import Goal
from hackagent.models.model import Model
from hackagent.models.response import ModelResponse
from hackagent.orchestrator.campaign.resolve import resolve_campaign
from hackagent.orchestrator.campaign.spec import CampaignSpec

EXAMPLES = Path(__file__).resolve().parents[3] / "hackagent" / "examples"
CAMPAIGNS = sorted(EXAMPLES.rglob("*.yaml"))


class _Fake(Model):
    """Answers anything, reaches nothing."""

    def complete(self, messages: Sequence[Mapping[str, Any]], **_: Any):
        return ModelResponse(text="ok")

    async def acomplete(self, messages: Sequence[Mapping[str, Any]], **_: Any):
        return ModelResponse(text="ok")


@pytest.fixture(autouse=True)
def example_credentials(monkeypatch, tmp_path):
    """Load-only example checks use dummy credentials, never real providers."""
    monkeypatch.setattr(
        "hackagent.core.settings.DEFAULT_CONFIG_PATH", tmp_path / "config.json"
    )
    for name in (
        "HACKAGENT_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.setenv(name, "example-test-key")


def test_there_are_example_campaigns():
    """A glob that matches nothing would make every test below vacuous."""
    assert CAMPAIGNS


@pytest.mark.parametrize("path", CAMPAIGNS, ids=lambda p: p.stem)
def test_the_example_resolves(path: Path):
    spec = CampaignSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    resolved = resolve_campaign(
        spec,
        build=lambda config, retries=0: _Fake(),
        load=lambda _dataset: [Goal(index=0, text="goal")],
        build_embed=lambda _config: lambda texts: [[0.0] for _ in texts],
    )
    assert resolved.attacks, f"{path.name}: a campaign with no attack"


@pytest.mark.parametrize("path", CAMPAIGNS, ids=lambda p: p.stem)
def test_the_example_says_what_it_is(path: Path):
    """An example nobody can read is not an example."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert document["campaign"].get("description"), (
        f"{path.name}: give `campaign.description` a line saying what this attacks"
    )
    assert path.read_text(encoding="utf-8").lstrip().startswith("#"), (
        f"{path.name}: open with a comment covering prerequisites and how to run it"
    )


@pytest.mark.parametrize("path", CAMPAIGNS, ids=lambda p: p.stem)
def test_the_example_lets_ollama_be_where_it_is(path: Path):
    """An Ollama endpoint written down here pins everyone to that port.

    Left unset it resolves from ``OLLAMA_HOST``, so the example runs on a
    machine serving Ollama anywhere else without being edited. This is the
    only place the rule can be enforced: the campaign format allows an
    endpoint, and for a fixed server it is the right thing to write.
    """
    from hackagent.core.contracts import AgentType
    from hackagent.orchestrator.campaign.preflight import campaign_models

    spec = CampaignSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    pinned = [
        f"{where} ({config.connection.endpoint})"
        for where, config in campaign_models(spec)
        if config.connection.type is AgentType.OLLAMA and config.connection.endpoint
    ]
    assert pinned == [], (
        f"{path.name}: leave the endpoint out of these Ollama models so they "
        f"follow OLLAMA_HOST: {', '.join(pinned)}"
    )


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"OLLAMA_HOST": "gpu-box:9999"},
        {"OLLAMA_HOST": "127.0.0.1:11434"},
        {"OLLAMA_BASE_URL": "http://10.0.0.5:11434"},
    ],
    ids=["unset", "host-and-port", "loopback", "base-url"],
)
def test_ollama_follows_the_environment_everywhere(environment, monkeypatch):
    """Chat and embeddings must agree on where Ollama is.

    They resolve through different code, and did not always agree: one read
    the environment per call and the other a constant fixed at import.
    """
    from hackagent.core.settings import (
        OLLAMA_BASE_URL_ENV_VARS,
        resolve_ollama_base_url,
    )
    from hackagent.models.completions.litellm import normalise_ollama_endpoint
    from hackagent.models.embeddings import embedding_request_kwargs

    for name in OLLAMA_BASE_URL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    expected = resolve_ollama_base_url()
    assert normalise_ollama_endpoint(None) == expected
    assert (
        embedding_request_kwargs({"identifier": "e", "agent_type": "OLLAMA"})[
            "api_base"
        ]
        == f"{expected}/v1"
    )
