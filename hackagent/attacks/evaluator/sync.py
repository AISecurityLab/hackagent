# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Evaluation sync utilities for attack modules.

This module provides a unified function for syncing evaluation results
to the server by PATCHing Result records, eliminating the duplicated
pattern found across attack techniques.

Functions:
    update_single_result: Update one Result's evaluation status
    sync_evaluation_to_server: Batch-sync evaluation results (best per result_id)

Usage:
    from hackagent.attacks.evaluator.sync import (
        sync_evaluation_to_server,
        update_single_result,
    )

    # Sync multiple results (aggregates best per result_id)
    count = sync_evaluation_to_server(evaluated_data, client, logger)

    # Update a single result
    ok = update_single_result(result_id, success, notes, client, logger)
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from hackagent.api.result import result_partial_update
from hackagent.models import EvaluationStatusEnum, PatchedResultRequest

logger = logging.getLogger("hackagent.attacks.evaluator.sync")


def update_single_result(
    result_id: str,
    success: bool,
    evaluation_notes: str,
    client: Any,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """
    Update a single Result's evaluation status on the server.

    Args:
        result_id: UUID string of the result to update.
        success: Whether the attack was successful (from attacker's perspective).
        evaluation_notes: Explanation of the evaluation outcome.
        client: Authenticated client for API calls.
        logger: Optional logger instance.

    Returns:
        True if the update succeeded, False otherwise.
    """
    log = logger or globals()["logger"]

    try:
        eval_status = (
            EvaluationStatusEnum.SUCCESSFUL_JAILBREAK
            if success
            else EvaluationStatusEnum.FAILED_JAILBREAK
        )

        result_request = PatchedResultRequest(
            evaluation_status=eval_status,
            evaluation_notes=evaluation_notes,
        )

        response = result_partial_update.sync_detailed(
            client=client,
            id=UUID(result_id) if isinstance(result_id, str) else result_id,
            body=result_request,
        )

        if response.status_code < 300:
            log.debug(f"Updated result {result_id} → {eval_status.value}")
            return True
        else:
            log.warning(
                f"Failed to update result {result_id}: "
                f"status={response.status_code}, "
                f"content={getattr(response, 'content', 'N/A')}"
            )
            return False

    except Exception as e:
        log.error(f"Exception updating result {result_id}: {e}")
        return False


def sync_evaluation_to_server(
    evaluated_data: List[Dict[str, Any]],
    client: Any,
    logger: Optional[logging.Logger] = None,
    judge_keys: Optional[List[Dict[str, str]]] = None,
) -> int:
    """
    Sync evaluation results to the server, aggregating the best per result_id.

    Multiple completion rows may share the same ``result_id`` (one per goal).
    This function aggregates to find the best (success wins over failure)
    evaluation per ``result_id``, then PATCHes the server once per goal.

    Args:
        evaluated_data: List of dicts with evaluation results. Each dict
            should contain ``result_id`` and evaluation score keys.
        client: Authenticated client for API calls.
        logger: Optional logger instance.
        judge_keys: Optional list of dicts mapping judge types to their
            column names, e.g. ``[{"key": "eval_jb", "explanation": "explanation_jb",
            "label": "JailbreakBench"}]``. If None, auto-detects from
            known column patterns.

    Returns:
        Number of results successfully updated on the server.
    """
    log = logger or globals()["logger"]

    if not client:
        log.warning("No client available — cannot sync evaluation to server")
        return 0

    # Find rows with result_id
    result_ids = [r.get("result_id") for r in evaluated_data if r.get("result_id")]
    if not result_ids:
        log.warning("No result_id found in data — cannot sync to server")
        return 0

    log.info(
        f"🔄 Syncing evaluation for {len(result_ids)} rows "
        f"({len(set(result_ids))} unique result_ids)"
    )

    # Default judge key mappings
    if judge_keys is None:
        judge_keys = [
            {
                "key": "eval_jb",
                "explanation": "explanation_jb",
                "label": "JailbreakBench",
            },
            {"key": "eval_hb", "explanation": "explanation_hb", "label": "HarmBench"},
            {"key": "eval_nj", "explanation": "explanation_nj", "label": "Nuanced"},
        ]

    # Aggregate best evaluation per result_id
    best_per_result: Dict[str, Dict[str, Any]] = {}

    for row in evaluated_data:
        result_id = row.get("result_id")
        if not result_id:
            continue

        success, notes = _evaluate_row(row, judge_keys)

        existing = best_per_result.get(result_id)
        if existing is None or (success and not existing["success"]):
            best_per_result[result_id] = {
                "success": success,
                "evaluation_notes": notes,
            }

    # PATCH once per result_id
    updated_count = 0
    for result_id, info in best_per_result.items():
        if update_single_result(
            result_id, info["success"], info["evaluation_notes"], client, log
        ):
            updated_count += 1

    log.info(
        f"Synced {updated_count}/{len(best_per_result)} evaluation results to server"
    )
    return updated_count


def _evaluate_row(
    row: Dict[str, Any],
    judge_keys: List[Dict[str, str]],
) -> tuple:
    """
    Determine success and build evaluation notes for a single row.

    Returns:
        Tuple of (success: bool, notes: str).
    """
    success = False
    notes_parts: List[str] = []

    for jk in judge_keys:
        key = jk["key"]
        expl_key = jk["explanation"]
        label = jk["label"]

        if key in row:
            success = success or (row[key] == 1)
            notes_parts.append(f"{label}: {row[key]}")
            if expl_key in row:
                notes_parts.append(f"{label} explanation: {row[expl_key]}")

    # Also check generic "success" key (used by baseline)
    if "success" in row and not notes_parts:
        success = bool(row["success"])
        notes_parts.append(row.get("evaluation_notes", ""))

    notes = " | ".join(notes_parts) if notes_parts else "No evaluation scores available"
    return success, notes
