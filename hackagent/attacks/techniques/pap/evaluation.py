# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
PAP post-processing module.

This step runs **after** the generation loop, which already includes inline
judge evaluation with early-stopping.  By the time this step executes,
every result dict already contains ``best_score``, ``success``, and the
raw judge columns.

In PAP, each persuasion-technique attempt may be judged inline during
generation. This evaluation step never re-runs judge evaluation.

The post-processing step is responsible for:
- Enriching any items still missing scores (e.g. errors).
- Server sync of evaluation data.
- ASR logging per judge.
"""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.server.client import AuthenticatedClient


class PAPEvaluation(BaseEvaluationStep):
    """Lightweight post-processing for the PAP attack.

    Judge evaluation is performed inline during the generation loop while
    iterating persuasion techniques.
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

        self._postprocess_inline_judge_results(input_data, attack_label="PAP")

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
