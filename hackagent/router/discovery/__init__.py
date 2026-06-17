# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Agentic attack planning + browser helpers for the ``web`` provider.

    from hackagent.router.discovery import auto_plan, plan_attack, build_web_target

    result = auto_plan("https://example.com")   # build web target → LLM picks a strategy
    if result.plan:
        print(result.plan.summary())
        attack_config = result.plan.to_attack_config()
"""

from hackagent.router.discovery.scanner import (
    DEFAULT_PLANNER_MODEL,
    AttackPlan,
    AutoPlanResult,
    PlannerError,
    auto_plan,
    build_attack_catalog,
    build_web_target,
    plan_attack,
)

# Browser helpers are imported directly: the ``browser`` module keeps its
# Playwright imports inside the functions that need them, so importing it here
# never pulls Playwright at package-import time. Importing the names explicitly
# (rather than resolving them via ``__getattr__``) keeps every entry in
# ``__all__`` defined in module scope for static analysis.
from hackagent.router.discovery.browser import (
    BrowserScanError,
    chromium_installed,
    ensure_chromium,
    install_chromium,
)

__all__ = [
    # Planner
    "plan_attack",
    "auto_plan",
    "build_web_target",
    "build_attack_catalog",
    "AttackPlan",
    "AutoPlanResult",
    "PlannerError",
    "DEFAULT_PLANNER_MODEL",
    # Browser helpers
    "BrowserScanError",
    "ensure_chromium",
    "chromium_installed",
    "install_chromium",
]
