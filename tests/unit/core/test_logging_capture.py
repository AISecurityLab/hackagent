# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""capture(): a handler gets one run's records, at a level of its own; no
other handler is touched."""

from __future__ import annotations

import asyncio
import logging
import threading
from uuid import uuid4

import pytest

from hackagent.core.async_utils import run_coroutine_blocking
from hackagent.core.logging import about, capture, subject_of


class Keep(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)

    @property
    def messages(self) -> list[str]:
        return [record.getMessage() for record in self.records]


@pytest.fixture
def package():
    """A fresh package logger opened fully, as the CLI opens it, with a
    handler of its own (the CLI's, say) that shows only warnings."""
    logger = logging.getLogger(f"capture_test_{uuid4().hex}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    shown = Keep()
    shown.setLevel(logging.WARNING)
    logger.addHandler(shown)
    disabled = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    yield logger, shown
    logging.disable(disabled)
    logger.removeHandler(shown)


def test_each_handler_shows_its_own_level(package):
    logger, shown = package
    child = logging.getLogger(f"{logger.name}.child")
    kept = Keep()

    with capture(kept, logging.INFO, logger.name):
        child.info("for the capture")
        child.debug("for nobody")
        child.warning("for both")

    assert kept.messages == ["for the capture", "for both"]
    assert shown.messages == ["for both"]
    assert logger.level == logging.DEBUG and shown.level == logging.WARNING
    assert not shown.filters and kept not in logger.handlers


def test_the_logger_s_level_is_the_floor(package):
    """A capture never opens the logger: whoever configures logging does."""
    logger, _ = package
    logger.setLevel(logging.WARNING)
    kept = Keep()

    with capture(kept, logging.INFO, logger.name):
        logger.info("held back by the logger")
        logger.warning("through")

    assert kept.messages == ["through"]


def test_only_the_block_s_records_reach_it(package):
    logger, _ = package
    kept = Keep()

    def elsewhere():
        logger.warning("another thread")

    with capture(kept, logging.INFO, logger.name):
        logger.warning("in the block")
        asyncio.run(asyncio.to_thread(logger.warning, "in a thread it started"))
        thread = threading.Thread(target=elsewhere)
        thread.start()
        thread.join()
    logger.warning("after the block")

    assert kept.messages == ["in the block", "in a thread it started"]


def test_side_by_side_captures_keep_their_runs_apart(package):
    logger, _ = package
    first, second = Keep(), Keep()
    ready = threading.Barrier(2)

    def run(handler, name):
        with capture(handler, logging.INFO, logger.name):
            ready.wait()
            logger.info(name)
            ready.wait()

    threads = [
        threading.Thread(target=run, args=(first, "first")),
        threading.Thread(target=run, args=(second, "second")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert (first.messages, second.messages) == (["first"], ["second"])


def test_the_run_reaches_its_capture_from_inside_a_running_loop(package):
    logger, _ = package
    kept = Keep()

    async def caller():
        # A notebook: run_campaign is called while a loop is running.
        return run_coroutine_blocking(lambda: asyncio.sleep(0, logger.info("ran")))

    with capture(kept, logging.INFO, logger.name):
        asyncio.run(caller())

    assert kept.messages == ["ran"]


def test_a_record_says_what_it_is_about(package):
    """Which attack and goal a line is about comes from where it was logged."""
    logger, _ = package
    kept = Keep()

    with capture(kept, logging.INFO, logger.name):
        with about(attack="pair", goal=3, goals=20):
            logger.info("inside")
        logger.info("outside")

    inside, outside = kept.records
    assert subject_of(inside) == {"attack": "pair", "goal": 3, "goals": 20}
    assert subject_of(outside) == {}


def test_a_run_log_holds_only_its_run_s_lines(tmp_path, monkeypatch):
    from hackagent.core.logging import PACKAGE_LOGGER, run_log

    monkeypatch.setattr(logging.getLogger(PACKAGE_LOGGER), "level", logging.DEBUG)
    disabled = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    log = logging.getLogger(f"{PACKAGE_LOGGER}.tests.run_log")
    path = tmp_path / "run" / "run.log"
    try:
        with run_log(path, logging.INFO) as written:
            log.info("in the run")
            log.debug("too detailed")
            thread = threading.Thread(target=log.warning, args=("another run",))
            thread.start()
            thread.join()
    finally:
        logging.disable(disabled)

    assert written == path
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line.split(None, 3)[2:] for line in lines] == [["INFO", "in the run"]]


def test_a_model_s_worker_threads_log_into_its_run(package):
    """A batch's worker threads, and code moved off the loop, keep the run's
    context: what they log reaches the run's handlers, not only the CLI's."""
    from hackagent.models import ModelResponse
    from tests.unit.campaign.fakes import ScriptedModel

    logger, _ = package
    kept = Keep()

    class Logging(ScriptedModel):
        def complete(self, messages, **overrides):
            logger.warning("worker: %s", messages[0]["content"])
            return ModelResponse(text="ok")

    model = Logging()
    requests = [[{"role": "user", "content": str(n)}] for n in range(4)]
    with capture(kept, logging.INFO, logger.name):
        model.complete_batch(requests, max_concurrency=2)
        asyncio.run(asyncio.to_thread(logger.warning, "moved off the loop"))

    assert sorted(kept.messages) == sorted(
        [f"worker: {n}" for n in range(4)] + ["moved off the loop"]
    )


def test_no_code_moves_work_off_the_loop_without_its_context():
    """``run_in_executor`` drops the caller's context, and with it the run
    its lines belong to; ``asyncio.to_thread`` keeps it."""
    from pathlib import Path

    import hackagent

    offenders = [
        str(path)
        for path in Path(hackagent.__file__).parent.rglob("*.py")
        if ".run_in_executor(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_a_logger_and_its_descendant_hand_a_record_over_once(package):
    package, _ = package
    child = logging.getLogger(f"{package.name}.trace")
    seen = Keep()

    with capture(seen, logging.INFO, (package.name, child.name)):
        child.info("one step")

    assert seen.messages == ["one step"]


def test_a_run_ending_never_moves_the_list_another_run_is_walked_from(package):
    """Python walks a logger's handlers while another thread may be removing
    one: removing it from that very list shifted the next run's handler past
    the walk, and that run lost its own record. The list is replaced instead."""
    package, _ = package
    first, second = Keep(), Keep()
    with capture(first, logging.INFO, package.name):
        walked = package.handlers
        with capture(second, logging.INFO, package.name):
            during = package.handlers
        assert second in during and second not in package.handlers
    # The lists a walk had in hand are left as they were.
    assert first in walked and second in during
    assert first not in package.handlers


def test_an_application_s_own_handler_keeps_logging_closed(monkeypatch):
    """A handler on the package logger, at no level of its own, says the
    application configured logging: opening it to INFO for a run would hand
    that handler lines it never asked for."""
    from hackagent.core.logging import opened

    name = f"opened_test_{uuid4().hex}"
    logger = logging.getLogger(name)
    monkeypatch.setattr(logging.getLogger(), "handlers", [])
    theirs = Keep()
    logger.addHandler(theirs)
    try:
        with opened({name: logging.INFO}) as held:
            assert held is False
            assert logger.level == logging.NOTSET
        logger.removeHandler(theirs)
        with opened({name: logging.INFO}) as held:
            assert held is True
            assert logger.level == logging.INFO
    finally:
        logger.removeHandler(theirs)
        logger.setLevel(logging.NOTSET)
