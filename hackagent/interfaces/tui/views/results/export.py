# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CSV / JSON export actions for the results tab: one row per goal tried."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from hackagent.interfaces.results import verdict_of

#: The columns of an export, in order: where the goal was tried, then what
#: came of it and the evidence for it.
FIELDS = (
    "campaign",
    "target",
    "attack",
    "run_id",
    "result_id",
    "goal",
    "verdict",
    "reply",
    "judges_notes",
    "created_at",
)


class ResultsExportMixin:
    """Export helpers for :class:`~hackagent.interfaces.tui.views.results.tab.ResultsTab`."""

    def _export_rows(self) -> tuple[list[dict[str, Any]], int]:
        """A row for each result read so far, and how many attack runs are
        still being read."""
        campaigns = {str(campaign.id): campaign for campaign in self._campaigns}
        rows: list[dict[str, Any]] = []
        pending = 0
        for run in self.results_data:
            items = self._results_of_run.get(str(run.id))
            if items is None:
                pending += 1
                continue
            campaign = campaigns.get(str(getattr(run, "campaign_run_id", "")))
            for result in items:
                metadata = getattr(result, "metadata", None) or {}
                created = getattr(result, "created_at", None)
                rows.append(
                    {
                        "campaign": getattr(campaign, "name", "") or "",
                        "target": self._agent_map.get(
                            str(getattr(campaign, "agent_id", "")), ""
                        ),
                        "attack": self._attack_map.get(
                            str(getattr(run, "attack_id", "")), ""
                        ),
                        "run_id": str(run.id),
                        "result_id": str(result.id),
                        "goal": getattr(result, "goal", "") or "",
                        "verdict": verdict_of(result),
                        "reply": str(metadata.get("response") or ""),
                        "judges_notes": getattr(result, "evaluation_notes", "") or "",
                        "created_at": created.isoformat()
                        if isinstance(created, datetime)
                        else str(created or ""),
                    }
                )
        return rows, pending

    def _export(self, suffix: str) -> None:
        rows, pending = self._export_rows()
        if not rows:
            self.notify(
                "Results are still being read; try again in a moment"
                if pending
                else "No results to export",
                severity="warning",
            )
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path.cwd() / f"hackagent_results_{stamp}.{suffix}"
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                if suffix == "csv":
                    writer = csv.DictWriter(handle, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    json.dump(
                        {"exported_at": datetime.now().isoformat(), "results": rows},
                        handle,
                        indent=2,
                    )
        except OSError as error:
            self.notify(f"Export failed: {error}", severity="error")
            return
        said = f"Exported {len(rows)} {'result' if len(rows) == 1 else 'results'} to {path.name}"
        if pending:
            said += f" ({pending} attack runs still being read are not in it)"
        self.notify(said, severity="information")

    def _export_results_csv(self) -> None:
        """Export every goal tried, with its verdict and reply, to CSV."""
        self._export("csv")

    def _export_results_json(self) -> None:
        """The same as :meth:`_export_results_csv`, as JSON."""
        self._export("json")
