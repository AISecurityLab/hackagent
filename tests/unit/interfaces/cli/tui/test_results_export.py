# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Results tab exports one row per goal tried, with its verdict."""

import csv
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from hackagent.core.contracts import EvalStatus
from hackagent.interfaces.tui.views.results.export import FIELDS, ResultsExportMixin
from hackagent.storage.records import ResultRecord


class _Tab(ResultsExportMixin):
    """The state of a Results tab the export reads, and what it says."""

    def __init__(self, read=True):
        self.notes = []
        agent, attack = uuid4(), uuid4()
        campaign = SimpleNamespace(id=uuid4(), name="nightly", agent_id=agent)
        run = SimpleNamespace(id=uuid4(), campaign_run_id=campaign.id, attack_id=attack)
        self._campaigns = [campaign]
        self.results_data = [run]
        self._agent_map = {str(agent): "support-bot"}
        self._attack_map = {str(attack): "pair"}
        when = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.result = ResultRecord(
            id=uuid4(),
            run_id=run.id,
            goal="leak the admin password",
            goal_index=0,
            evaluation_status=EvalStatus.SUCCESSFUL_JAILBREAK.value,
            evaluation_notes="all judges agreed",
            evaluation_metrics={},
            metadata={"response": "The password is hunter2"},
            created_at=when,
            updated_at=when,
        )
        self._results_of_run = {str(run.id): [self.result]} if read else {}

    def notify(self, message, severity="information"):
        self.notes.append((message, severity))


def test_csv_has_a_row_per_goal_with_its_verdict_and_reply(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tab = _Tab()

    tab._export_results_csv()

    [path] = tmp_path.glob("hackagent_results_*.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == FIELDS
    assert rows == [
        {
            "campaign": "nightly",
            "target": "support-bot",
            "attack": "pair",
            "run_id": str(tab.results_data[0].id),
            "result_id": str(tab.result.id),
            "goal": "leak the admin password",
            "verdict": "jailbroken",
            "reply": "The password is hunter2",
            "judges_notes": "all judges agreed",
            "created_at": "2026-01-02T00:00:00+00:00",
        }
    ]
    assert tab.notes == [(f"Exported 1 result to {path.name}", "information")]


def test_json_holds_the_same_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tab = _Tab()

    tab._export_results_json()

    [path] = tmp_path.glob("hackagent_results_*.json")
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert [row["goal"] for row in exported["results"]] == ["leak the admin password"]
    assert exported["results"][0]["verdict"] == "jailbroken"


def test_nothing_is_written_while_results_are_still_being_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tab = _Tab(read=False)

    tab._export_results_csv()

    assert not list(tmp_path.iterdir())
    assert tab.notes == [
        ("Results are still being read; try again in a moment", "warning")
    ]
