# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CSV / JSON export actions for the results tab."""

from datetime import datetime
import json


class ResultsExportMixin:
    """Export helpers for :class:`~hackagent.cli.tui.views.results.tab.ResultsTab`."""

    def _export_results_csv(self) -> None:
        """Export results to CSV file."""
        try:
            import csv
            from pathlib import Path

            if not self.results_data:
                self.notify("No results to export", severity="warning")
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hackagent_results_{timestamp}.csv"
            filepath = Path.cwd() / filename

            # Write CSV
            with open(filepath, "w", newline="") as csvfile:
                fieldnames = [
                    "ID",
                    "Agent",
                    "Attack Type",
                    "Status",
                    "Created",
                    "Duration",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for result in self.results_data:
                    # Get status
                    status = "Unknown"
                    if hasattr(result, "evaluation_status"):
                        status_val = result.evaluation_status
                        status = (
                            status_val.value
                            if hasattr(status_val, "value")
                            else str(status_val)
                        )

                    # Get created date
                    created = "Unknown"
                    if hasattr(result, "created_at") and result.created_at:
                        created = str(result.created_at)

                    # Calculate duration
                    duration = "N/A"
                    if hasattr(result, "run") and result.run:
                        run = result.run
                        if (
                            hasattr(run, "started_at")
                            and run.started_at
                            and hasattr(run, "completed_at")
                            and run.completed_at
                        ):
                            try:
                                if isinstance(run.started_at, datetime) and isinstance(
                                    run.completed_at, datetime
                                ):
                                    delta = run.completed_at - run.started_at
                                    duration = f"{delta.total_seconds():.1f}s"
                            except Exception:
                                pass

                    writer.writerow(
                        {
                            "ID": str(result.id),
                            "Agent": getattr(result, "agent_name", "Unknown"),
                            "Attack Type": getattr(result, "attack_type", "Unknown"),
                            "Status": status,
                            "Created": created,
                            "Duration": duration,
                        }
                    )

            self.notify(
                f"✅ Exported {len(self.results_data)} results to {filename}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"❌ Export failed: {str(e)}", severity="error")

    def _export_results_json(self) -> None:
        """Export results to JSON file."""
        try:
            from pathlib import Path

            if not self.results_data:
                self.notify("No results to export", severity="warning")
                return

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hackagent_results_{timestamp}.json"
            filepath = Path.cwd() / filename

            # Convert results to dict
            results_list = []
            for result in self.results_data:
                result_dict = {
                    "id": str(result.id),
                    "agent_name": getattr(result, "agent_name", None),
                    "attack_type": getattr(result, "attack_type", None),
                    "created_at": str(result.created_at)
                    if hasattr(result, "created_at")
                    else None,
                }

                # Add status
                if hasattr(result, "evaluation_status"):
                    status_val = result.evaluation_status
                    result_dict["status"] = (
                        status_val.value
                        if hasattr(status_val, "value")
                        else str(status_val)
                    )

                # Add run information
                if hasattr(result, "run") and result.run:
                    result_dict["run"] = {
                        "id": str(result.run.id) if hasattr(result.run, "id") else None,
                        "status": str(result.run.status)
                        if hasattr(result.run, "status")
                        else None,
                        "started_at": str(result.run.started_at)
                        if hasattr(result.run, "started_at")
                        else None,
                        "completed_at": str(result.run.completed_at)
                        if hasattr(result.run, "completed_at")
                        else None,
                    }

                # Add config and data if available
                if hasattr(result, "attack_config"):
                    result_dict["attack_config"] = result.attack_config
                if hasattr(result, "data"):
                    result_dict["data"] = result.data
                if hasattr(result, "logs"):
                    result_dict["logs"] = str(result.logs)

                results_list.append(result_dict)

            # Write JSON
            with open(filepath, "w") as jsonfile:
                json.dump(
                    {
                        "exported_at": datetime.now().isoformat(),
                        "total_results": len(results_list),
                        "results": results_list,
                    },
                    jsonfile,
                    indent=2,
                )

            self.notify(
                f"✅ Exported {len(results_list)} results to {filename}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"❌ Export failed: {str(e)}", severity="error")
