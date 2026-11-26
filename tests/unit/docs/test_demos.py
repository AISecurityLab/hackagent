# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The terminal UI demo still films, and films the same each time.

The README's GIF is recorded from a storyboard that drives the real app
(``docs/scripts/demos/tui_demo.py``). A change to the app that breaks the story
fails here, in the pull request that makes it, rather than in the job that
records the demos after the merge. Rendering the frames needs a browser and
is left to that job.
"""

from __future__ import annotations

import asyncio
import importlib
import re
import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parents[3] / "docs" / "scripts" / "demos"


def _film():
    sys.path.insert(0, str(DEMOS))
    try:
        tui = importlib.import_module("tui_demo")
        record = importlib.import_module("record")
        tui.preload()
        with (
            tui._sandbox(),
            record.frozen_clock(),
            record.fixed_ids(),
            record.steady_clock(),
        ):
            return asyncio.run(tui._film())
    finally:
        sys.path.remove(str(DEMOS))


def _text(svg: str) -> str:
    return " ".join(re.findall(r">([^<]+)</text>", svg)).replace("&#160;", " ")


def test_the_story_runs_the_campaign_to_its_end_the_same_each_time():
    first, second = _film(), _film()

    assert first.digest() == second.digest()
    end = _text(first.frames[-1][0])
    # The run went all the way: its closing line is on screen.
    assert "Ollama h4rm3l demo" in end
    assert "succeeded" in end and "of" in end and "goals" in end
