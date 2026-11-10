# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Real campaign execution, settings and SQLite shared by boundary tests."""

from types import SimpleNamespace
import pytest
from hackagent import Settings
from hackagent.orchestrator.campaign import arun_campaign
from hackagent.storage.local import LocalBackend


@pytest.fixture
def execution(campaign_values, tmp_path, isolated_campaign_env):
    store = LocalBackend(str(tmp_path / "boundary.db"))
    settings = Settings.resolve(
        env=isolated_campaign_env, config_path=tmp_path / "no-config.json"
    )

    def run(**kwargs):
        return arun_campaign(campaign_values, store=store, settings=settings, **kwargs)

    yield SimpleNamespace(
        values=campaign_values, store=store, run=run, directory=tmp_path / "runs"
    )
    store.close()
