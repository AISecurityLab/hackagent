# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every example that needs nothing but Ollama is run, for real.

An example is a campaign file now, so running the examples *is* the
integration test. The one this was written for — Codex driven through
Ollama — resolved cleanly and could never reach its target, because
resolution builds a fake model and asks it nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hackagent import examples as examples_catalog
from hackagent.core.contracts import AgentType
from hackagent.orchestrator.campaign.preflight import campaign_models
from hackagent.orchestrator.campaign.spec import CampaignSpec

pytestmark = pytest.mark.live


def _needs_only_ollama(path: Path) -> bool:
    """Whether every model this example names is one Ollama serves."""
    try:
        spec = CampaignSpec.model_validate(yaml.safe_load(path.read_text()))
    except Exception:
        return False
    kinds = {config.connection.type for _where, config in campaign_models(spec)}
    return bool(kinds) and kinds == {AgentType.OLLAMA}


LOCAL_EXAMPLES = sorted(
    name
    for name, path in examples_catalog.campaign_files().items()
    if _needs_only_ollama(path)
)


def test_some_examples_need_nothing_but_ollama():
    """A filter that matched nothing would make the test below vacuous."""
    assert LOCAL_EXAMPLES


@pytest.mark.parametrize("name", LOCAL_EXAMPLES)
@pytest.mark.timeout(900)
def test_the_example_reaches_its_target(name, run_live, tmp_path, available_models):
    path = examples_catalog.campaign_files()[name]
    values = yaml.safe_load(path.read_text())

    missing = {
        config.name
        for _where, config in campaign_models(CampaignSpec.model_validate(values))
        if config.name not in available_models
    }
    if missing:
        pytest.skip(f"ollama pull {' '.join(sorted(missing))}")

    # Keep an example's own dataset size out of the test's runtime.
    values.setdefault("dataset", {}).setdefault("selection", {})["limit"] = 1
    values.setdefault("execution", {})["output"] = {"directory": str(tmp_path)}

    result = run_live(values)

    attempts = [a for outcome in result.attacks for a in outcome.attempts]
    assert attempts, f"{name}: the run recorded no attempts at all"
    # The point of the whole suite: the target answered.
    unreachable = [a.error for a in attempts if a.error]
    assert not unreachable, f"{name}: target never answered — {unreachable[:2]}"
