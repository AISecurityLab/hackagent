# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for audit-failure persistence on run records."""

import json
import logging
import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from hackagent.tracking.audit import (
    AuditPersistenceError,
    record_run_audit_failure,
)
from hackagent.core.contracts import RunStatus


class TestRecordRunAuditFailure(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test.audit")
        self.logger.disabled = True
        self.backend = MagicMock()
        self.run_id = str(uuid4())

    def test_persists_failed_status_and_structured_notes(self):
        entry = record_run_audit_failure(
            self.backend,
            self.run_id,
            "goal_tracker",
            ValueError("classifier timed out"),
            self.logger,
        )

        self.assertEqual(entry["step"], "goal_tracker")
        self.assertEqual(entry["status"], "failed")
        self.assertIn("ValueError: classifier timed out", entry["error"])

        kwargs = self.backend.update_run.call_args.kwargs
        self.assertEqual(str(self.backend.update_run.call_args.args[0]), self.run_id)
        self.assertEqual(kwargs["status"], RunStatus.FAILED.value)
        notes = json.loads(kwargs["run_notes"])
        self.assertEqual(notes["audit_failure"], entry)

    def test_truncates_long_error_messages(self):
        entry = record_run_audit_failure(
            self.backend,
            self.run_id,
            "sync",
            RuntimeError("x" * 2000),
            self.logger,
        )
        self.assertEqual(len(entry["error"]), 1000)

    def test_invalid_run_id_raises_without_touching_backend(self):
        with self.assertRaises(AuditPersistenceError) as ctx:
            record_run_audit_failure(
                self.backend,
                "not-a-uuid",
                "tracker",
                RuntimeError("boom"),
                self.logger,
            )
        self.assertIn("invalid run id", str(ctx.exception))
        self.backend.update_run.assert_not_called()

    def test_backend_failure_is_wrapped(self):
        self.backend.update_run.side_effect = OSError("disk full")
        with self.assertRaises(AuditPersistenceError) as ctx:
            record_run_audit_failure(
                self.backend,
                self.run_id,
                "tracker",
                RuntimeError("original"),
                self.logger,
            )
        self.assertIn("Cannot persist audit failure for 'tracker'", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, OSError)


if __name__ == "__main__":
    unittest.main()
