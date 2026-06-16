# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared inline judge runner for generation-time attack loops.

Use this helper in attacks that evaluate candidate responses during generation
(instead of in a dedicated evaluation phase), currently:
- PAP
- BoN

Note:
    This helper only evaluates the candidate it receives from the caller.
    Candidate selection strategy stays attack-specific. For BoN, callers pass
    only the step-best candidate.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.attacks.evaluator.judge_evaluators import EVALUATOR_MAP
from hackagent.attacks.shared.router_factory import extract_passthrough_request_config
from hackagent.attacks.techniques.advprefix.config import EvaluatorConfig

if TYPE_CHECKING:
    from hackagent.server.client import AuthenticatedClient


def build_inline_judge_base_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build base evaluator options for inline judge execution.

    Intended users:
        - PAP generation
        - BoN generation
    """
    return {
        "batch_size": config.get("batch_size_judge", 1),
        "max_tokens_eval": config.get("max_tokens_eval", 256),
        "filter_len": config.get("filter_len", 10),
        "timeout": config.get("judge_timeout", 120),
        "temperature": config.get("judge_temperature", 0.0),
        "max_judge_retries": config.get("max_judge_retries", 1),
        "organization_id": config.get("organization_id"),
    }


class InlineStepJudge:
    """Evaluate one selected candidate response with configured judges.

    Intended users:
        - PAP generation
        - BoN generation

    The generation loop decides *which* candidate is evaluated.
    """

    JUDGE_COLUMN_MAP = BaseEvaluationStep.JUDGE_COLUMN_MAP

    def __init__(
        self,
        judges_config: List[Dict[str, Any]],
        base_eval_config: Dict[str, Any],
        client: "AuthenticatedClient",
        logger: logging.Logger,
        run_id: Optional[str] = None,
    ):
        self._judges: List[Tuple[str, Any]] = []
        self.logger = logger

        for jcfg in judges_config:
            judge_type = jcfg.get("evaluator_type") or jcfg.get("type")
            identifier = jcfg.get("identifier")
            if not judge_type or judge_type not in EVALUATOR_MAP:
                continue
            if not identifier:
                continue

            evaluator_class = EVALUATOR_MAP[judge_type]
            sub_cfg: Dict[str, Any] = {**base_eval_config, **jcfg}
            sub_cfg["model_id"] = identifier
            sub_cfg["agent_name"] = jcfg.get(
                "agent_name",
                f"judge-{judge_type}-{identifier.replace('/', '-')[:20]}",
            )
            sub_cfg["agent_type"] = jcfg.get("agent_type", "OPENAI_SDK")
            sub_cfg["agent_endpoint"] = jcfg.get("endpoint")
            sub_cfg["agent_metadata"] = dict(jcfg.get("agent_metadata", {}) or {})
            sub_cfg["agent_metadata"].update(extract_passthrough_request_config(jcfg))

            api_key = jcfg.get("api_key") or jcfg.get("api_key_env")
            if api_key:
                sub_cfg["agent_metadata"]["api_key"] = api_key

            expected_fields = set(EvaluatorConfig.model_fields.keys())
            filtered = {k: v for k, v in sub_cfg.items() if k in expected_fields}

            try:
                ev_config = EvaluatorConfig(**filtered)
                evaluator = evaluator_class(
                    client=client,
                    config=ev_config,
                    run_id=run_id,
                    tracking_client=None,
                    tracker=None,
                )
                self._judges.append((judge_type, evaluator))
            except Exception as exc:
                logger.warning(f"Could not initialise judge '{judge_type}': {exc}")

        if not self._judges:
            logger.warning("No valid judges initialised for inline evaluation")

    @property
    def available(self) -> bool:
        """True if at least one judge was successfully initialised."""
        return bool(self._judges)

    @property
    def judge_count(self) -> int:
        """Number of configured judge evaluator instances."""
        return len(self._judges)

    def is_jailbreak(
        self,
        goal: str,
        prompt_prefix: str,
        response: str,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Evaluate a candidate response and return (success, best_score, cols)."""
        row = {
            "goal": goal,
            "prefix": prompt_prefix,
            "completion": response,
        }

        judge_cols: Dict[str, Any] = {}
        best_score = 0.0
        total_by_type: Dict[str, int] = {}
        seen_by_type: Dict[str, int] = {}

        for judge_type, _evaluator in self._judges:
            total_by_type[judge_type] = total_by_type.get(judge_type, 0) + 1

        for judge_type, evaluator in self._judges:
            try:
                evaluated = evaluator.evaluate([row.copy()])
                if not evaluated:
                    continue

                ev_row = evaluated[0]
                seen_by_type[judge_type] = seen_by_type.get(judge_type, 0) + 1
                idx = seen_by_type[judge_type]
                use_suffix = total_by_type.get(judge_type, 0) > 1

                judge_cols_for_type = self.JUDGE_COLUMN_MAP.get(judge_type, [])
                for col in judge_cols_for_type:
                    if col not in ev_row:
                        continue
                    out_col = f"{col}_{idx}" if use_suffix else col
                    judge_cols[out_col] = ev_row[col]

                if judge_cols_for_type:
                    eval_col = judge_cols_for_type[0]
                    val = ev_row.get(eval_col)
                    if val is not None:
                        try:
                            best_score = max(best_score, float(val))
                        except (TypeError, ValueError):
                            pass
            except Exception as exc:
                self.logger.warning(f"Judge '{judge_type}' failed on candidate: {exc}")

        return best_score > 0, best_score, judge_cols
