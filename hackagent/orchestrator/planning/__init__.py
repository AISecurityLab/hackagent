# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack planning: an LLM picks a technique, goals and parameters.

- :mod:`~hackagent.orchestrator.planning.catalog`: the technique catalog and
  its JSON-schema parameters
- :mod:`~hackagent.orchestrator.planning.planner`: ``plan_attack`` and
  ``auto_plan``
- :mod:`~hackagent.orchestrator.planning.web`: ``build_web_target``
"""

from hackagent.orchestrator.planning.catalog import (
    SchemaField,
    build_attack_catalog,
    schema_fields,
)
from hackagent.orchestrator.planning.planner import (
    DEFAULT_PLANNER_MODEL,
    AttackPlan,
    AutoPlanResult,
    PlannerError,
    auto_plan,
    plan_attack,
)
from hackagent.orchestrator.planning.web import build_web_target

__all__ = [
    "DEFAULT_PLANNER_MODEL",
    "AttackPlan",
    "AutoPlanResult",
    "PlannerError",
    "SchemaField",
    "auto_plan",
    "build_attack_catalog",
    "build_web_target",
    "plan_attack",
    "schema_fields",
]
