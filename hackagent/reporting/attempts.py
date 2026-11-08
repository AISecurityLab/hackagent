# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""One goal's attempts, paged (``/attempts``) or in full (``/structure``).

Attempts are numbered from 1 in ``created_at``, then ``id``, order: the
order the conversation happened in, and the one ``first_jailbreak_attempt``
of the costs counts in.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from hackagent.reporting.buckets import result_bucket
from hackagent.reporting.report import iso
from hackagent.reporting.rows import (
    Attempt,
    FirstSuccess,
    StructureResult,
    StructureTrace,
)


def attempt_page(
    rows: Sequence[Attempt],
    count: int,
    page: int,
    page_size: int,
    first: Optional[FirstSuccess],
) -> dict[str, Any]:
    """``GET /run/{id}/attempts``: one page of rows (already ordered and cut
    by the database), with the page of the first jailbreak."""
    offset = (page - 1) * page_size
    return {
        "count": count,
        "next": f"?page={page + 1}" if page * page_size < count else None,
        "previous": f"?page={page - 1}" if page > 1 else None,
        "results": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "ordinal": offset + position,
                "bucket": row.bucket,
                "notes": row.notes or None,
                "created_at": iso(row.created_at),
            }
            for position, row in enumerate(rows, start=1)
        ],
        "first_success": {
            "id": first.id,
            "page": (first.position - 1) // page_size + 1,
        }
        if first is not None
        else None,
    }


def trace_item(trace: StructureTrace) -> dict[str, Any]:
    return {
        "id": trace.id,
        "result": trace.result_id,
        "sequence": trace.sequence,
        "step_type": trace.step_type,
        "timestamp": iso(trace.timestamp),
        "content": trace.content,
    }


def attack_structure(
    results: Iterable[StructureResult], traces: Iterable[StructureTrace]
) -> dict[str, Any]:
    """``GET /run/{id}/structure``: a goal's whole recorded search in one
    attack run, including work that produced no result."""
    ordered = sorted(results, key=lambda row: (row.created_at, row.id))
    position = {row.id: index for index, row in enumerate(ordered)}
    steps = sorted(
        (trace for trace in traces if trace.result_id in position),
        key=lambda trace: (position[trace.result_id], trace.sequence, trace.id),
    )
    return {
        "attempts": [
            {
                "id": row.id,
                "ordinal": ordinal,
                "run_id": row.run_id,
                "bucket": result_bucket(row.evaluation_status, row.evaluation_notes),
                "notes": row.evaluation_notes or None,
                "created_at": iso(row.created_at),
                "metadata": (row.agent_specific_data or {}).get("attack_metadata")
                or {},
            }
            for ordinal, row in enumerate(ordered, start=1)
        ],
        "traces": [trace_item(trace) for trace in steps],
        "results": [
            {
                "id": row.id,
                "request_payload": row.request_payload,
                "agent_specific_data": row.agent_specific_data,
                "evaluation_notes": row.evaluation_notes or None,
            }
            for row in ordered
        ],
    }


__all__ = ["attack_structure", "attempt_page", "trace_item"]
