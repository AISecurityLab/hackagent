# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Helpers for making audit-pipeline failures visible in run records."""

import json
import logging
from typing import Any, Dict
from uuid import UUID

from hackagent.server.storage.enums import StatusEnum


class AuditPersistenceError(RuntimeError):
    """Raised when an audit failure cannot itself be persisted."""


def record_run_audit_failure(
    backend: Any,
    run_id: str,
    step: str,
    error: BaseException,
    logger: logging.Logger,
) -> Dict[str, str]:
    """Persist a structured audit failure and mark the run as failed.

    Audit-bearing code may continue after a recoverable tracking failure, but
    it must never make that failure invisible. If the run record cannot be
    updated, this helper raises so callers cannot report a trustworthy result.
    """
    entry = {
        "step": step,
        "status": "failed",
        "error": f"{type(error).__name__}: {error}"[:1000],
    }

    try:
        run_uuid = UUID(str(run_id))
    except (AttributeError, TypeError, ValueError) as exc:
        logger.error(
            "Cannot persist audit failure for %s: invalid run id %r",
            step,
            run_id,
            exc_info=True,
        )
        raise AuditPersistenceError(
            f"Cannot persist audit failure for '{step}': invalid run id"
        ) from exc

    try:
        backend.update_run(
            run_uuid,
            status=StatusEnum.FAILED.value,
            run_notes=json.dumps({"audit_failure": entry}, sort_keys=True),
        )
    except Exception as exc:
        logger.critical(
            "Cannot persist audit failure for %s: %s",
            step,
            exc,
            exc_info=True,
        )
        raise AuditPersistenceError(
            f"Cannot persist audit failure for '{step}'"
        ) from exc

    logger.error(
        "Recorded audit failure for %s: %s",
        step,
        entry["error"],
    )
    return entry
