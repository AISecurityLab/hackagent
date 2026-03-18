# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CipherChat evaluation module."""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.client import AuthenticatedClient


class CipherChatEvaluation(BaseEvaluationStep):
    """Evaluate decoded CipherChat responses with configured judges."""

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        client: AuthenticatedClient,
    ):
        super().__init__(config, logger, client)

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not input_data:
            return input_data

        self._statistics["input_count"] = len(input_data)

        params = self._raw_config.get("cipherchat_params", {})
        judges_config = self._resolve_judges_from_config(technique_params=params)

        eval_rows: List[Dict[str, Any]] = []
        error_indices: set[int] = set()

        for idx, item in enumerate(input_data):
            if item.get("error") and not item.get("decoded_response"):
                error_indices.add(idx)
                item["best_score"] = 0.0
                item["success"] = False
                item["evaluation_notes"] = f"Execution error: {item['error']}"
                continue

            eval_rows.append(
                {
                    "goal": item.get("goal", ""),
                    "prefix": item.get("full_prompt", ""),
                    "completion": item.get("decoded_response")
                    or item.get("response", "")
                    or "",
                }
            )

        if not eval_rows:
            self._enrich_items_with_scores(input_data, error_indices)
            return input_data

        base_config = self._build_base_eval_config(technique_params=params)
        evaluated_rows = self._run_evaluation(eval_rows, judges_config, base_config)
        self._statistics["evaluated_count"] = len(evaluated_rows)

        all_judge_cols: set[str] = set()
        for cols in self.JUDGE_COLUMN_MAP.values():
            all_judge_cols.update(cols)

        normalize = self._normalize_merge_key
        lookup = {}
        for row in evaluated_rows:
            key = (
                normalize("goal", row.get("goal")),
                normalize("prefix", row.get("prefix")),
                normalize("completion", row.get("completion")),
            )
            lookup[key] = {c: row[c] for c in all_judge_cols if c in row}

        for idx, item in enumerate(input_data):
            if idx in error_indices:
                continue

            key = (
                normalize("goal", item.get("goal", "")),
                normalize("prefix", item.get("full_prompt", "")),
                normalize(
                    "completion",
                    item.get("decoded_response") or item.get("response", ""),
                ),
            )
            item.update(lookup.get(key, {}))

        self._enrich_items_with_scores(input_data, error_indices)
        self._update_tracker(input_data, evaluator_prefix="cipherchat_eval")

        judge_keys = self._build_judge_keys_from_data(input_data)
        self._sync_to_server(input_data, judge_keys)
        self._log_evaluation_asr(input_data)

        return input_data


def execute(
    input_data: List[Dict],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict]:
    return CipherChatEvaluation(config=config, logger=logger, client=client).execute(
        input_data
    )
