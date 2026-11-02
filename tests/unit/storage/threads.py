# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run storage writes from many threads at once."""

import threading
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")


def run_concurrently(work: Callable[[T], None], items: Sequence[T]) -> None:
    """Call ``work(item)`` for every item, each in a thread of its own, all
    released together, and wait for them to finish.

    The threads start one at a time: on Python 3.11 and earlier, a thread
    that installs the coverage tracer while another does can die before it
    runs (python/cpython#98257). Only the writes overlap.
    """
    go = threading.Event()

    def run(item: T, running: threading.Event) -> None:
        running.set()
        go.wait()
        work(item)

    threads = []
    for item in items:
        running = threading.Event()
        thread = threading.Thread(target=run, args=(item, running))
        thread.start()
        running.wait()
        threads.append(thread)
    go.set()
    for thread in threads:
        thread.join()
