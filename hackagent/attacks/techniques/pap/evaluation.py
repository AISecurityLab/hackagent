# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
PAP post-processing module.

This step runs **after** the generation loop, which already includes inline
judge evaluation with early-stopping.  By the time this step executes,
every result dict already contains ``best_score``, ``success``, and the
raw judge columns.

The post-processing step is responsible for:
- Enriching any items still missing scores (e.g. errors).
- Server sync of evaluation data.
- ASR logging per judge.
"""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.server.client import AuthenticatedClient


def _build_prompt_prefix(item: Dict[str, Any]) -> str:
    """Build the 'prefix' field from a PAP result item."""
    persuasive = item.get("persuasive_prompt")
    if persuasive:
        return str(persuasive)
    return item.get("goal", "")


class PAPEvaluation(BaseEvaluationStep):
    """Lightweight post-processing for the PAP attack.

    Judge evaluation is performed inline during the generation loop.
    This step handles server sync, tracker updates, and ASR logging only.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        client: AuthenticatedClient,
    ):
        super().__init__(config, logger, client)

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process PAP results: enrich scores, sync, and log ASR.

        Args:
            input_data: Dicts from the generation step.

        Returns:
            Same list, enriched with any missing ``best_score`` / ``success``.
        """
        if not input_data:
            return input_data

        self._statistics["input_count"] = len(input_data)

        error_indices: set = set()
        for idx, item in enumerate(input_data):
            if item.get("error") and not item.get("response"):
                error_indices.add(idx)
                item.setdefault("best_score", 0.0)
                item.setdefault("success", False)
                item.setdefault("evaluation_notes", f"Execution error: {item['error']}")
            else:
                item.setdefault("best_score", 0.0)
                item.setdefault("success", item.get("best_score", 0) > 0)

        self._statistics["evaluated_count"] = len(input_data) - len(error_indices)

        n_success = sum(1 for item in input_data if item.get("success"))
        self.logger.info(
            f"Post-processing {len(input_data)} results "
            f"({n_success} jailbreaks from inline judge)"
        )

        # Tracker: skip final trace (PAP uses per-technique evaluations)
        if self._tracker:
            self.logger.info(
                "📊 Skipping final tracker evaluation trace (PAP uses per-technique evaluations)"
            )

        # Sync to server
        judge_keys = self._build_judge_keys_from_data(input_data)
        self._sync_to_server(input_data, judge_keys)

        # Log ASR
        self._log_evaluation_asr(input_data)

        return input_data


def execute(
    input_data: List[Dict],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict]:
    """Pipeline-compatible function entry point."""
    step = PAPEvaluation(config=config, logger=logger, client=client)
    return step.execute(input_data=input_data)
