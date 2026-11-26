# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``hackagent web`` serves every dashboard page in a real browser with no
failed API call (:mod:`tests.smoke.smoke_webui`).

Needs a dashboard bundle and a Playwright Chromium; without either the test
skips and says which. CI's dashboard smoke job installs both and runs it with
``--fail-on-skip``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.smoke import smoke_webui


def _missing_prerequisite() -> str | None:
    from hackagent.interfaces.web import _static

    if _static.find_bundle() is None:
        return "no dashboard bundle: `uv sync --extra web` or deploy/web/build_webui.sh"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright is not installed"
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).exists():
            return "no Playwright Chromium: `uv run playwright install chromium`"
    return None


# Server start-up plus a browser pass over every page outlasts the default.
@pytest.mark.timeout(300)
def test_every_dashboard_page_renders_without_failed_requests():
    missing = _missing_prerequisite()
    if missing:
        pytest.skip(missing)
    assert smoke_webui.main([]) == 0


# The demo seeds its database by running a campaign, then browses.
@pytest.mark.timeout(300)
def test_the_dashboard_demo_tells_its_story(tmp_path):
    """The README's dashboard GIF is recorded from a storyboard
    (docs/scripts/demos/dashboard_demo.py): it still gets from the home page to
    one goal's conversation, and records the same frames each time."""
    import importlib
    import sys

    missing = _missing_prerequisite()
    if missing:
        pytest.skip(missing)
    demos = Path(__file__).resolve().parents[2] / "docs" / "scripts" / "demos"
    sys.path.insert(0, str(demos))
    try:
        dashboard = importlib.import_module("dashboard_demo")
        first = dashboard.film(tmp_path / "first")
        second = dashboard.film(tmp_path / "second")
    finally:
        sys.path.remove(str(demos))

    assert first.digest() == second.digest()
    assert "Target response" in first.keys[-3]
