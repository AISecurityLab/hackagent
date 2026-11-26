# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Record an interface of HackAgent as a GIF, from code.

A demo is a storyboard: ``tui_demo.py`` drives the real app headless and
:class:`Film` snapshots the screen at each step it chooses; ``cli_demo.py`` runs
the real commands and films the terminal (:func:`terminal_frame`);
``dashboard_demo.py`` serves the real dashboard and films a browser. The models are
scripted (:class:`DemoModel`) and every call waits at a :class:`Gate` the
storyboard opens, so a run moves exactly as far as the storyboard says
between two snapshots. The log's clock is frozen (:func:`frozen_clock`).
The same code therefore always films the same frames, whatever the machine
or its speed.

Each frame is an SVG of the screen (Textual's own export). Chromium renders
them and Pillow assembles the GIF. The GIF carries a hash of its frames, so
recording again writes nothing unless a frame changed: CI can run this on
every change and propose new GIFs only when an interface really looks
different.
"""

from __future__ import annotations

import asyncio
import contextlib
import glob
import hashlib
import io
import os
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from hackagent.models import Model, ModelResponse

#: How long a frame stays on screen by default, in milliseconds.
HOLD_MS = 900
#: Where the GIF's frame hash is kept: the GIF's own comment.
_HASH = b"hackagent-demo-frames:"


# --- the models a demo runs against -----------------------------------------


class Gate:
    """Lets model calls through only as the storyboard says.

    Every call waits for a permit (:meth:`open`). The storyboard opens a
    number of permits, then waits until the run is held again
    (:meth:`settled`): every permit used and the next call waiting, or the
    run over. What happened in between is therefore always the same.
    """

    def __init__(self) -> None:
        self._lock = threading.Condition()
        self._permits = 0
        self._waiting = 0
        self.closed = False

    def pass_through(self) -> None:
        """Called by a model call, in a worker thread: wait for a permit."""
        with self._lock:
            self._waiting += 1
            self._lock.notify_all()
            while self._permits == 0 and not self.closed:
                self._lock.wait()
            self._waiting -= 1
            if self._permits:
                self._permits -= 1
            self._lock.notify_all()

    def open(self, calls: int) -> None:
        with self._lock:
            self._permits += calls
            self._lock.notify_all()

    def release_all(self) -> None:
        """Let every call through from now on."""
        with self._lock:
            self.closed = True
            self._lock.notify_all()

    def settled(self, finished: Callable[[], bool], timeout: float = 30.0) -> None:
        """Wait until the permits are used and a call waits again, or the
        run is ``finished``."""
        deadline = time.monotonic() + timeout
        with self._lock:
            while not (finished() or (self._permits == 0 and self._waiting > 0)):
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("the run did not reach the next call")
                self._lock.wait(min(left, 0.05))


@dataclass
class DemoModel(Model):
    """A model that answers from a script: ``reply(messages)``, after its
    call passes the :class:`Gate`."""

    reply: Callable[[Sequence[Mapping[str, Any]]], str]
    gate: Gate

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **_: Any
    ) -> ModelResponse:
        self.gate.pass_through()
        return ModelResponse(text=self.reply(messages))

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **_: Any
    ) -> ModelResponse:
        await asyncio.to_thread(self.gate.pass_through)
        return ModelResponse(text=self.reply(messages))

    async def is_reachable(self) -> Any:
        from hackagent.models import Reachability

        return Reachability(True, latency_s=0.1)


@contextlib.contextmanager
def frozen_clock(start: str = "2026-11-25 10:00:00") -> Iterator[None]:
    """Log lines stamped from a fixed clock that moves a second per record,
    so the time in a frame never changes from one recording to the next."""
    import hackagent.core.logging as core

    base = time.mktime(time.strptime(start, "%Y-%m-%d %H:%M:%S"))
    #: Each record's real time, by the second it is shown at: the same record
    #: formatted twice (for run.log and the screen) shows the same time.
    seconds: dict[Optional[float], int] = {}
    real = core.time

    class Clock:
        def __getattr__(self, name: str) -> Any:
            return getattr(real, name)

        @staticmethod
        def localtime(created: Optional[float] = None) -> time.struct_time:
            second = seconds.setdefault(created, len(seconds))
            return real.localtime(base + second)

    core.time = Clock()  # type: ignore[assignment]
    try:
        yield
    finally:
        core.time = real


@contextlib.contextmanager
def fixed_ids(seed: int = 7) -> Iterator[None]:
    """Run and record ids drawn from a seeded generator instead of
    ``uuid.uuid4``, wherever the code took it from, so an id on screen is
    the same in every recording."""
    import random
    import sys
    import uuid

    real = uuid.uuid4
    draw = random.Random(seed)

    def uuid4() -> uuid.UUID:
        return uuid.UUID(int=draw.getrandbits(128), version=4)

    holders = [uuid] + [
        module
        for name, module in list(sys.modules.items())
        if name.startswith("hackagent") and getattr(module, "uuid4", None) is real
    ]
    for holder in holders:
        holder.uuid4 = uuid4  # type: ignore[attr-defined]
    try:
        yield
    finally:
        for holder in holders:
            holder.uuid4 = real  # type: ignore[attr-defined]


@contextlib.contextmanager
def steady_clock(step: float = 0.1) -> Iterator[None]:
    """Durations measured by the code (an attack's, a goal's, a call's) from
    a clock that moves ``step`` seconds each time it is read, in place of
    ``time.monotonic`` wherever the code took it, so a duration on screen is
    the same in every recording. Python's own clock, and asyncio's with it,
    is left alone."""
    import sys

    real = time.monotonic
    # Each thread its own count: a thread that wakes when it likes (a run's
    # heartbeat) must not move the clock the run's own steps read.
    reads = threading.local()

    def monotonic() -> float:
        reads.count = getattr(reads, "count", 0) + 1
        return reads.count * step

    holders = [
        module
        for name, module in list(sys.modules.items())
        if name.startswith("hackagent") and getattr(module, "monotonic", None) is real
    ]
    for holder in holders:
        holder.monotonic = monotonic  # type: ignore[attr-defined]
    try:
        yield
    finally:
        for holder in holders:
            holder.monotonic = real  # type: ignore[attr-defined]


# --- filming -----------------------------------------------------------------


@dataclass
class Film:
    """The frames of a demo: an SVG of the screen (or a PNG of a browser's
    page), and how long it stays."""

    app: Any = None
    frames: list[tuple[Any, int]] = field(default_factory=list)
    #: What each frame is hashed by, when not by itself: a browser's page by
    #: what it shows rather than by its pixels, which a font update moves.
    keys: list[str] = field(default_factory=list)

    def add(self, frame: Any, hold_ms: int = HOLD_MS, key: str = "") -> None:
        """Keep ``frame`` for ``hold_ms``; the last frame again is held longer."""
        key = key or (frame if isinstance(frame, str) else "")
        if self.frames and self.keys[-1] == key and key:
            self.frames[-1] = (self.frames[-1][0], self.frames[-1][1] + hold_ms)
            return
        self.frames.append((frame, hold_ms))
        self.keys.append(key)

    def snap(self, hold_ms: int = HOLD_MS) -> None:
        """Keep the screen as it is now for ``hold_ms``."""
        from textual.widgets import Input, TextArea

        # A blinking cursor would make two recordings differ.
        for widget in self.app.query("*"):
            if isinstance(widget, (Input, TextArea)):
                widget.cursor_blink = False
        self.add(self.app.export_screenshot(title="HackAgent"), hold_ms)

    def digest(self) -> str:
        """A hash of every frame (by its key) and how long it stays."""
        hashed = hashlib.sha256()
        for (frame, hold), key in zip(self.frames, self.keys):
            hashed.update(key.encode() if key else bytes(frame))
            hashed.update(str(hold).encode())
        return hashed.hexdigest()


def terminal_frame(ansi: str, width: int, rows: int, title: str = "HackAgent") -> str:
    """A terminal showing the last ``rows`` lines of ``ansi``, as an SVG drawn
    the way the TUI's frames are (Rich's export, as Textual's)."""
    from rich.console import Console
    from rich.text import Text

    import re

    # Colours stay; any other control sequence (a cursor shown or hidden)
    # draws nothing in a terminal, so it draws nothing here.
    ansi = re.sub(r"\x1b\[[0-9;?]*[A-La-ln-z]", "", ansi)
    console = Console(
        width=width,
        height=rows,
        file=io.StringIO(),
        force_terminal=True,
        color_system="truecolor",
        record=True,
        legacy_windows=False,
        safe_box=False,
    )
    # Wrapped at the terminal's edge, as a terminal does, then its last rows.
    lines: list[Text] = []
    for line in ansi.split("\n"):
        lines.extend(Text.from_ansi(line).wrap(console, width) or [Text()])
    lines = lines[-rows:]
    lines += [Text()] * (rows - len(lines))
    for line in lines:
        console.print(line, overflow="crop", no_wrap=True)
    return console.export_svg(title=title)


# --- rendering ---------------------------------------------------------------


def _chromium(playwright: Any) -> Any:
    """Playwright's Chromium, or the newest one already downloaded when the
    installed package expects a build that is not."""
    try:
        return playwright.chromium.launch()
    except Exception:
        home = Path(
            os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "~/.cache/ms-playwright")
        )
        found = sorted(
            glob.glob(str(home.expanduser() / "chromium-*/chrome-linux*/chrome")),
            key=lambda path: int(path.split("chromium-")[1].split("/")[0]),
        )
        if not found:
            raise
        return playwright.chromium.launch(executable_path=found[-1])


def _render(frames: Sequence[tuple[Any, int]], scale: float) -> list[Any]:
    """Each frame as a Pillow image: an SVG drawn by Chromium, a PNG read."""
    from PIL import Image
    from playwright.sync_api import sync_playwright

    if all(isinstance(frame, bytes) for frame, _ in frames):
        return [Image.open(io.BytesIO(frame)).convert("RGB") for frame, _ in frames]
    images = []
    with sync_playwright() as playwright:
        browser = _chromium(playwright)
        page = browser.new_page(device_scale_factor=scale)
        for svg, _ in frames:
            page.set_content(
                f"<html><body style='margin:0;background:transparent'>{svg}</body></html>"
            )
            page.evaluate("document.fonts.ready")
            png = page.query_selector("svg").screenshot(omit_background=True)
            images.append(Image.open(io.BytesIO(png)).convert("RGB"))
        browser.close()
    return images


def recorded_digest(path: Path) -> Optional[str]:
    """The frame hash a GIF was recorded from, if it carries one."""
    if not path.exists():
        return None
    from PIL import Image

    with Image.open(path) as gif:
        comment = gif.info.get("comment", b"")
    return comment[len(_HASH) :].decode() if comment.startswith(_HASH) else None


def write_gif(
    film: Film, path: Path, *, scale: float = 1.0, force: bool = False
) -> bool:
    """Write ``film`` to ``path`` as a GIF, unless the GIF there was recorded
    from the same frames. Whether it wrote."""
    digest = film.digest()
    if not force and recorded_digest(path) == digest:
        return False
    images = _render(film.frames, scale)
    # One palette for every frame, from the frames themselves, so colours do
    # not shift between frames.
    from PIL import Image

    sheet = Image.new("RGB", (images[0].width, images[0].height * len(images)))
    for index, image in enumerate(images):
        sheet.paste(image, (0, image.height * index))
    palette = sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    paletted = [
        image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    paletted[0].save(
        path,
        save_all=True,
        append_images=paletted[1:],
        duration=[hold for _, hold in film.frames],
        loop=0,
        optimize=True,
        comment=_HASH + digest.encode(),
    )
    return True


__all__ = [
    "DemoModel",
    "Film",
    "Gate",
    "HOLD_MS",
    "fixed_ids",
    "frozen_clock",
    "recorded_digest",
    "steady_clock",
    "terminal_frame",
    "write_gif",
]
