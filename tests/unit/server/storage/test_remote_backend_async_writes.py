# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Self-check for RemoteBackend's background write queue.

Invariant under test: every deferred write (create_trace / update_result) is
eventually executed exactly once — none are dropped or duplicated — and they are
fully drained by flush(), by a read, and by close().
"""

import threading
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.server.storage.remote import RemoteBackend


def _client():
    c = MagicMock()
    c.token = "tok"
    return c


def _ok(status):
    r = MagicMock()
    r.status_code = status
    r.parsed = MagicMock(id=uuid4())
    r.content = b"{}"
    return r


class TestRemoteBackendAsyncWrites(unittest.TestCase):
    def test_all_deferred_writes_land_after_flush_and_close(self):
        trace_calls = []
        update_calls = []
        lock = threading.Lock()

        def record_trace(**kw):
            with lock:
                trace_calls.append(kw)
            return _ok(201)

        def record_update(**kw):
            with lock:
                update_calls.append(kw)
            return _ok(200)

        trace_mod = MagicMock()
        trace_mod.sync_detailed.side_effect = record_trace
        update_mod = MagicMock()
        update_mod.sync_detailed.side_effect = record_update

        with (
            patch("hackagent.server.storage.remote.result_trace_create", trace_mod),
            patch("hackagent.server.storage.remote.result_partial_update", update_mod),
        ):
            backend = RemoteBackend(_client())

            n = 250
            rid = uuid4()
            for seq in range(n):
                rec = backend.create_trace(rid, seq, "OTHER", {"i": seq})
                # The synthetic record returns immediately with correct identity.
                self.assertEqual(rec.sequence, seq)
            backend.update_result(rid, evaluation_status="SUCCESSFUL_JAILBREAK")

            # Nothing is lost once the queue is drained.
            backend.flush()
            self.assertEqual(len(trace_calls), n)
            self.assertEqual(len(update_calls), 1)

            # FIFO single worker preserves per-result ordering.
            seqs = [c["body"].sequence for c in trace_calls]
            self.assertEqual(seqs, list(range(n)))

            # A write enqueued after close() still runs (synchronous fallback).
            backend.close()
            backend.create_trace(rid, n, "OTHER", {"i": n})
            self.assertEqual(len(trace_calls), n + 1)

            # No background write failed.
            self.assertEqual(backend._writer_failures, 0)

    def test_read_flushes_pending_writes(self):
        trace_mod = MagicMock()
        trace_mod.sync_detailed.return_value = _ok(201)
        retrieve_mod = MagicMock()
        retrieve_mod.sync_detailed.return_value = _ok(200)

        with (
            patch("hackagent.server.storage.remote.result_trace_create", trace_mod),
            patch("hackagent.server.storage.remote.result_retrieve", retrieve_mod),
        ):
            backend = RemoteBackend(_client())
            rid = uuid4()
            for seq in range(20):
                backend.create_trace(rid, seq, "OTHER", {"i": seq})
            # list_traces() must drain the queue before reading back.
            backend.list_traces(rid)
            self.assertEqual(trace_mod.sync_detailed.call_count, 20)
            backend.close()


if __name__ == "__main__":
    unittest.main()
