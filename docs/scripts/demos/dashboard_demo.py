# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Record the web dashboard demo: ``docs/static/gifs/hackagent-dashboard.gif``.

The campaign the command-line demo runs (``cli_demo.py``) is run again here, the
same way, into a database of its own; the real dashboard (``hackagent web``'s
app) serves it, and a browser goes from the home page to the runs, to the
campaign and to one goal's attack conversation, a screenshot a step.

Every recording of the same code shows the same pages: the run is the
command-line demo's (scripted models, fixed clocks and ids), every time in
the database is set to one instant, the browser's clock stands still a few
minutes after it, and nothing is animated. A frame is hashed by what the
page says rather than by its pixels, which a browser or font update moves.

Needs the dashboard's build (``uv sync --extra web``) and a Playwright
Chromium.

    uv run python docs/scripts/demos/dashboard_demo.py           # writes the GIF if it changed
    uv run python docs/scripts/demos/dashboard_demo.py --force   # writes it anyway
"""

from __future__ import annotations

import argparse
import re
import socket
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cli_demo as cli  # noqa: E402
from record import Film, _chromium, write_gif  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
GIF = ROOT / "docs" / "static" / "gifs" / "hackagent-dashboard.gif"
#: The browser window, in pixels.
VIEWPORT = {"width": 1280, "height": 800}
#: When everything in the database happened, and when the browser looks.
RAN_AT = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
LOOKED_AT = RAN_AT + timedelta(minutes=5)
CAMPAIGN = "Ollama h4rm3l demo"


def seed(folder: Path) -> Path:
    """The command-line demo's campaign, run into ``folder/demo.db``, every
    time in it set to :data:`RAN_AT`."""
    folder.mkdir(parents=True, exist_ok=True)
    for command in cli.STORY:
        if command[1:3] in (("examples", "copy"), ("campaign", "run")):
            cli.run(command, folder)
    database = folder / "demo.db"
    with sqlite3.connect(database) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        for table in tables:
            columns = [
                row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
            ]
            for column in columns:
                if column.endswith("_at") or column == "timestamp":
                    connection.execute(
                        f'UPDATE "{table}" SET "{column}" = ? '
                        f'WHERE "{column}" IS NOT NULL',
                        (RAN_AT.isoformat(),),
                    )
    return database


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Browser:
    """A browser on the dashboard, filming a frame a step."""

    def __init__(self, page: Any, base: str, reel: Film) -> None:
        self.page, self.base, self.reel = page, base, reel

    def settle(self) -> None:
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(800)
        consent = self.page.get_by_role("button", name="Not now", exact=True)
        if consent.is_visible():
            consent.click()
            self.page.wait_for_timeout(300)

    def snap(self, hold_ms: int) -> None:
        """The page as shown, kept by what it says and where."""
        # Its step in the story too: a panel scrolled inside the page shows
        # different rows with the same text.
        said = self.page.inner_text("body")
        where = self.page.url.removeprefix(self.base)  # the port is any free one
        key = f"{len(self.reel.frames)}\n{where}\n{said}"
        self.reel.add(self.page.screenshot(), hold_ms, key=key)

    def go(self, path: str, hold_ms: int = 2200) -> None:
        self.page.goto(self.base + path)
        self.settle()
        self.snap(hold_ms)

    def click(self, locator: Any, hold_ms: int = 2200) -> None:
        locator.click()
        self.settle()
        self.snap(hold_ms)

    def scroll(self, pixels: int, hold_ms: int = 1600, over: Any = None) -> None:
        """Scroll what is under ``over``, else the middle of the content."""
        box = over.bounding_box() if over is not None else None
        if box:
            self.page.mouse.move(
                box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            )
        else:
            self.page.mouse.move(VIEWPORT["width"] * 0.6, VIEWPORT["height"] * 0.6)
        self.page.mouse.wheel(0, pixels)
        self.page.wait_for_timeout(400)
        self.snap(hold_ms)


def story(browser: Browser) -> None:
    page = browser.page
    browser.go("/", 2600)
    browser.click(page.get_by_role("link", name="Runs", exact=True))
    browser.click(page.get_by_role("link", name=CAMPAIGN, exact=True), 2600)
    for _ in range(3):
        browser.scroll(500)
    # Goal by goal, then one goal's conversation: what the attack sent and
    # what the target said.
    coverage = page.get_by_role("region", name="Goal by attack outcomes")
    coverage.scroll_into_view_if_needed()
    coverage.get_by_role("button", name="Detail: Categories").click()
    page.get_by_role("radio", name="Goals", exact=True).click()
    page.keyboard.press("Escape")
    browser.settle()
    browser.snap(2200)
    marker = coverage.get_by_role("link", name=re.compile(r": jailbroken")).first
    browser.click(marker, 3200)
    conversation = page.get_by_role("region", name="Attempt conversation")
    conversation.wait_for()
    for _ in range(2):
        browser.scroll(700, 1800, over=conversation)
    browser.click(page.get_by_text("Back to campaign", exact=True), 1600)


def film(folder: Path) -> Film:
    from playwright.sync_api import sync_playwright

    from hackagent.core.settings import Settings
    from hackagent.interfaces.dashboard import Served, open_dashboard

    database = seed(folder)
    settings = Settings.resolve(
        backend="local", db_path=str(database), env={}, config_path="/nonexistent"
    )
    port = _free_port()
    served = Served(open_dashboard(settings, port=port), "127.0.0.1", port)
    reel = Film()
    try:
        with sync_playwright() as playwright:
            chromium = _chromium(playwright)
            context = chromium.new_context(
                viewport=VIEWPORT,
                reduced_motion="reduce",
                locale="en-US",
                timezone_id="UTC",
            )
            page = context.new_page()
            page.clock.set_fixed_time(LOOKED_AT)
            story(Browser(page, f"http://127.0.0.1:{port}", reel))
            chromium.close()
    finally:
        served.stop()
    return reel


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="write even if unchanged")
    parser.add_argument("--out", type=Path, default=GIF, help="where to write the GIF")
    args = parser.parse_args(list(argv))

    with tempfile.TemporaryDirectory() as folder:
        reel = film(Path(folder))
    wrote = write_gif(reel, args.out, force=args.force)
    print(
        f"{args.out}: {'written' if wrote else 'unchanged'} ({len(reel.frames)} frames)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
