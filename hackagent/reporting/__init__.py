# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign run reports: the one implementation of every reporting rule.

The dashboard's campaign run routes (``/run/summary``, ``/run/{id}/report``,
``/goals``, ``/matrix``, ``/attempts``, ``/structure``, ``/costs``,
``/compare``) are served by ``hackagent web`` from SQLite and by the platform
API from Postgres. Both turn database rows into JSON with these pure
functions, so the two servers cannot drift:

* :mod:`~hackagent.reporting.buckets` classifies a result;
* :mod:`~hackagent.reporting.tallies` defines the two stored per-goal tables
  and the functions that keep them on every write;
* :mod:`~hackagent.reporting.rows` defines the rows a request reads, with
  the query that produces each;
* :mod:`~hackagent.reporting.goals`, :mod:`~hackagent.reporting.report`,
  :mod:`~hackagent.reporting.attempts` and :mod:`~hackagent.reporting.costs`
  build the responses;
* :mod:`~hackagent.reporting.http` parses requests, pages and computes ETags;
* :mod:`~hackagent.reporting.conformance` ships a sample and the exact
  responses both servers must return for it.

Nothing here touches a database, a web framework or the rest of the SDK.
"""

from hackagent.reporting.attempts import attack_structure, attempt_page
from hackagent.reporting.buckets import (
    BUCKETS,
    ERROR,
    JAILBREAK,
    MITIGATED,
    PENDING,
    Bucket,
    result_bucket,
)
from hackagent.reporting.costs import campaign_run_costs
from hackagent.reporting.goals import (
    GoalFilters,
    GoalSummary,
    category_summaries,
    goal_verdict,
    outcome_counts,
    summarize_goals,
)
from hackagent.reporting.report import (
    campaign_run_report,
    campaign_run_summaries,
    campaign_run_summary,
    compare_runs,
    goal_listing,
    goal_matrix,
    pick_previous,
    previous_summary,
)
from hackagent.reporting.rows import (
    TERMINAL_STATUSES,
    AttackRun,
    Attempt,
    CampaignRun,
    FirstSuccess,
    GoalTotal,
    Latency,
    StructureResult,
    StructureTrace,
)
from hackagent.reporting.tallies import (
    GoalOutcome,
    GoalUsage,
    ResultRow,
    TraceCoverage,
    TraceFlags,
    TraceRow,
    add_trace,
    goal_outcome,
    goal_usage,
    trace_coverage,
    trace_flags,
)

__all__ = [
    "AttackRun",
    "Attempt",
    "BUCKETS",
    "Bucket",
    "CampaignRun",
    "ERROR",
    "FirstSuccess",
    "GoalFilters",
    "GoalOutcome",
    "GoalSummary",
    "GoalTotal",
    "GoalUsage",
    "JAILBREAK",
    "Latency",
    "MITIGATED",
    "PENDING",
    "ResultRow",
    "StructureResult",
    "StructureTrace",
    "TERMINAL_STATUSES",
    "TraceCoverage",
    "TraceFlags",
    "TraceRow",
    "add_trace",
    "attack_structure",
    "attempt_page",
    "campaign_run_costs",
    "campaign_run_report",
    "campaign_run_summaries",
    "campaign_run_summary",
    "category_summaries",
    "compare_runs",
    "goal_listing",
    "goal_matrix",
    "goal_outcome",
    "goal_usage",
    "goal_verdict",
    "outcome_counts",
    "pick_previous",
    "previous_summary",
    "result_bucket",
    "summarize_goals",
    "trace_coverage",
    "trace_flags",
]
