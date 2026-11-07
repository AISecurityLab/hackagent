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
