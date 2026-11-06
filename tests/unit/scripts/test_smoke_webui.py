# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The dashboard smoke fixture must seed the current storage contract."""

from hackagent.storage.local import LocalBackend
from scripts.smoke_webui import seed


def test_browser_smoke_seed_persists_results_and_traces(tmp_path):
    db = tmp_path / "smoke.db"
    seed(db)
    store = LocalBackend(str(db))
    try:
        [agent] = store.list_agents().items
        assert agent.name == "smoke-agent"
        [run] = store.list_runs().items
        assert run.status == "COMPLETED"
        campaign = store.get_campaign_run(run.campaign_run_id)
        assert campaign.name == "smoke-campaign"
        results = store.list_results(run_id=run.id).items
        assert len(results) == 4
        assert {r.evaluation_status for r in results} == {
            "SUCCESSFUL_JAILBREAK",
            "FAILED_JAILBREAK",
            "NOT_EVALUATED",
        }
        assert all(len(store.list_traces(r.id)) == 2 for r in results)
    finally:
        store.close()
