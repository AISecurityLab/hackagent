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
    # Browser helpers (lazily exposed — keep Playwright optional)
    "BrowserScanError",
    "ensure_chromium",
    "chromium_installed",
    "install_chromium",
]

_BROWSER_EXPORTS = (
    "BrowserScanError",
    "ensure_chromium",
    "chromium_installed",
    "install_chromium",
)


def __getattr__(name):
    # Lazily expose the browser helpers so importing the discovery package never
    # pulls in Playwright (an optional dependency) until the web provider runs.
    if name in _BROWSER_EXPORTS:
        from hackagent.router.discovery import browser

        return getattr(browser, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
