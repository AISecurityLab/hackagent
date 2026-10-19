# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the sync/async bridge helper."""

import asyncio
import unittest

from hackagent.core.async_utils import run_coroutine_blocking


async def _add(left: int, right: int) -> int:
    await asyncio.sleep(0)
    return left + right


class TestRunCoroutineBlocking(unittest.TestCase):
    def test_runs_when_no_event_loop_is_active(self):
        self.assertEqual(run_coroutine_blocking(lambda: _add(2, 3)), 5)

    def test_runs_from_inside_an_already_running_loop(self):
        async def nested() -> int:
            # Calling a blocking helper from a running loop must not raise
            # "asyncio.run() cannot be called from a running event loop".
            return run_coroutine_blocking(lambda: _add(10, 7))

        self.assertEqual(asyncio.run(nested()), 17)

    def test_propagates_coroutine_exceptions(self):
        async def boom() -> None:
            raise RuntimeError("bridge failed")

        with self.assertRaises(RuntimeError) as ctx:
            run_coroutine_blocking(boom)
        self.assertIn("bridge failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
