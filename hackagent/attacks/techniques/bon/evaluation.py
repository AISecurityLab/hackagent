# Copyright 2026 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Best-of-N (BoN) post-processing module.

This step runs **after** the generation loop, which already includes inline
judge evaluation with early-stopping.  By the time this step executes,
every result dict already contains ``best_score``, ``success``, and the
raw judge columns (``eval_hb``, ``eval_jb``, etc.).

The post-processing step is responsible for:
- Enriching any items that are still missing scores (e.g. errors).
- Tracker integration (per-goal evaluation traces).
- Server sync of evaluation data.
- ASR logging per judge.

It does **not** re-evaluate responses with judges — that is done inline
during generation.
"""

import logging
from typing import Any, Dict, List

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.server.client import AuthenticatedClient


# ============================================================================
# DATA HELPERS
# ============================================================================


def _build_prompt_prefix(item: Dict[str, Any]) -> str:
    """Build the 'prefix' field from a BoN result item."""
    augmented = item.get("augmented_prompt")
    if augmented:
        return str(augmented)
    return item.get("goal", "")


# ============================================================================
# POST-PROCESSING STEP
# ============================================================================


class BoNEvaluation(BaseEvaluationStep):
    """Lightweight post-processing for the Best-of-N (BoN) attack.

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

    @staticmethod
    def _transform_to_eval_rows(
        input_data: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], set[int]]:
        """Transform BoN output rows into evaluator rows.

        Returns:
            Tuple of:
            - eval rows containing ``goal``, ``prefix``, ``completion``
            - set of indices that represent error rows (skipped)
        """
        eval_rows: List[Dict[str, Any]] = []
        error_indices: set[int] = set()

        for idx, item in enumerate(input_data):
            if item.get("error") and not item.get("response"):
                error_indices.add(idx)
                continue

            eval_rows.append(
                {
                    "goal": item.get("goal", ""),
                    "prefix": _build_prompt_prefix(item),
                    "completion": item.get("response", "") or "",
                }
            )

        return eval_rows, error_indices

    # ------------------------------------------------------------------ #
    # PUBLIC INTERFACE
    # ------------------------------------------------------------------ #

    def execute(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process BoN results: enrich scores, sync, and log ASR.

        Args:
            input_data: Dicts from the generation step, each already containing
                ``best_score``, ``success``, and judge columns from inline
                evaluation.

        Returns:
            Same list, enriched with any missing ``best_score`` / ``success``.
        """
        if not input_data:
            return input_data

        self._statistics["input_count"] = len(input_data)

        # Ensure every item has best_score / success (fill in for errors)
        error_indices: set = set()
        for idx, item in enumerate(input_data):
            if item.get("error") and not item.get("response"):
                error_indices.add(idx)
                item.setdefault("best_score", 0.0)
                item.setdefault("success", False)
                item.setdefault("evaluation_notes", f"Execution error: {item['error']}")
            else:
                # Scores already set by generation — just ensure defaults
                item.setdefault("best_score", 0.0)
                item.setdefault("success", item.get("best_score", 0) > 0)

        self._statistics["evaluated_count"] = len(input_data) - len(error_indices)

        n_success = sum(1 for item in input_data if item.get("success"))
        self.logger.info(
            f"Post-processing {len(input_data)} results "
            f"({n_success} jailbreaks from inline judge)"
        )

        # ----- Tracker integration ----- #
        if self._tracker:
            self.logger.info(
                "📊 Skipping final tracker evaluation trace (BoN uses per-step evaluations)"
            )

        # ----- Sync to server ----- #
        judge_keys = self._build_judge_keys_from_data(input_data)
        self._sync_to_server(input_data, judge_keys)

        # ----- Log ASR ----- #
        self._log_evaluation_asr(input_data)

        return input_data


# ============================================================================
# MODULE-LEVEL execute() — backward-compatible pipeline interface
# ============================================================================


def execute(
    input_data: List[Dict],
    config: Dict[str, Any],
    client: AuthenticatedClient,
    logger: logging.Logger,
) -> List[Dict]:
    """Pipeline-compatible function entry point.

    Wraps ``BoNEvaluation`` so that ``attack.py`` can reference
    ``evaluation.execute`` directly in the pipeline step definition.
    """
    step = BoNEvaluation(config=config, logger=logger, client=client)
    return step.execute(input_data=input_data)
