# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Record the command-line demo: ``docs/static/gifs/hackagent-cli.gif``.

The story is the quick start ``hackagent --help`` shows: pick an example,
copy it, check it, run it, see what it found. Each command is the real
``hackagent`` run in a process of its own, as in a terminal, against the
scripted models of the terminal UI's demo (``tui_demo.py``) and with its clocks
and ids fixed, so every recording of the same code is the same. Its output
is filmed as a terminal: the command typed, then what it printed.

    uv run python docs/scripts/demos/cli_demo.py           # writes the GIF if it changed
    uv run python docs/scripts/demos/cli_demo.py --force   # writes it anyway
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from record import Film, terminal_frame, write_gif  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
GIF = ROOT / "docs" / "static" / "gifs" / "hackagent-cli.gif"
#: The terminal, in columns and rows.
WIDTH, ROWS = 110, 32
#: The prompt, dimmed: where the demo runs, then ``$``.
PROMPT = "\x1b[2m~/red-team\x1b[0m $ "

#: The commands, as typed: the quick start.
STORY: tuple[tuple[str, ...], ...] = (
    ("hackagent", "examples", "list"),
    ("hackagent", "examples", "copy", "ollama/h4rm3l-demo", "campaign.yaml"),
    ("hackagent", "campaign", "validate", "campaign.yaml"),
    ("hackagent", "campaign", "run", "campaign.yaml"),
    ("hackagent", "results", "summary", "--goals"),
)


def run(command: Sequence[str], folder: Path) -> str:
    """What ``command`` prints in a terminal ``WIDTH`` columns wide, colours
    included: the real CLI, in a process of its own (:func:`_as_hackagent`)."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("HACKAGENT_") and key not in {"NO_COLOR"}
    }
    env.update(
        {
            "FORCE_COLOR": "1",
            "COLORTERM": "truecolor",
            "TERM": "xterm-256color",
            # Colours, but nothing animated: a spinner redraws itself with
            # cursor moves a recording would keep as text.
            "TTY_INTERACTIVE": "0",
            "COLUMNS": str(WIDTH),
            "LINES": str(ROWS),
            "PYTHONUNBUFFERED": "1",
            "HACKAGENT_DB_PATH": "demo.db",
            # The machine's own configuration would change what is printed.
            "XDG_CONFIG_HOME": str(folder / ".config"),
            "HOME": str(folder),
        }
    )
    done = subprocess.run(
        [sys.executable, __file__, "--as-hackagent", *command[1:]],
        cwd=folder,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return done.stdout.rstrip("\n")


def _no_servers() -> Any:
    """``campaign run`` first checks the campaign's Ollama and vLLM servers
    are up; the demo's models are scripted, so there is none to wait for."""
    from unittest.mock import patch

    return patch("hackagent.orchestrator.campaign.wait_for_servers")


def _as_hackagent(argv: Sequence[str]) -> int:
    """Be ``hackagent argv``, with the demo's models, clocks and ids."""
    import tui_demo as tui
    from record import Gate, fixed_ids, frozen_clock, steady_clock

    tui.preload()
    import hackagent.interfaces.cli.main as entry

    import asyncio

    # Nothing here waits for a storyboard, so nothing needs a thread: every
    # model call is answered at once, and the work the run hands a worker
    # thread (a call, a write to the store) is done in place, on its loop.
    # Threads would finish in their own order, and the goals' lines with
    # them; on one loop, there is one order.
    gate = Gate()
    gate.release_all()

    async def in_place(function: Any, /, *args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs)

    asyncio.to_thread = in_place  # type: ignore[assignment]
    sys.argv = ["hackagent", *argv]
    with tui._models(gate), _no_servers(), frozen_clock(), fixed_ids(), steady_clock():
        try:
            entry.main()
        except SystemExit as stop:
            return int(stop.code or 0)
    return 0


def film(folder: Path) -> Film:
    """The story, a frame per few keys typed and per few lines printed."""
    reel = Film()
    screen = ""

    def show(text: str, hold: int) -> None:
        reel.add(terminal_frame(text, WIDTH, ROWS), hold)

    show(PROMPT, 900)
    for command in STORY:
        typed = " ".join(command)
        for end in range(6, len(typed) + 6, 6):
            show(screen + PROMPT + typed[:end], 90)
        show(screen + PROMPT + typed, 500)
        printed = run(command, folder).split("\n")
        # Long output scrolls by, a few lines a frame.
        step = 6 if len(printed) > ROWS // 2 else len(printed)
        head = screen + PROMPT + typed
        for end in range(step, len(printed) + step, step):
            show(head + "\n" + "\n".join(printed[:end]), 140)
        screen = head + "\n" + "\n".join(printed) + "\n\n"
        show(screen + PROMPT, 2600)
    return reel


def main(argv: Sequence[str] = ()) -> int:
    argv = list(argv)
    if argv[:1] == ["--as-hackagent"]:
        return _as_hackagent(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="write even if unchanged")
    parser.add_argument("--out", type=Path, default=GIF, help="where to write the GIF")
    args = parser.parse_args(argv)

    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        reel = film(Path(folder))
    wrote = write_gif(reel, args.out, force=args.force)
    print(
        f"{args.out}: {'written' if wrote else 'unchanged'} ({len(reel.frames)} frames)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
