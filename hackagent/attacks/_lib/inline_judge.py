# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Adapters that expose generation-loop judge APIs over ``ports.Judge``.

Inline-judge techniques (BoN, PAP, tool_output_ipi, TAP) historically built
``InlineStepJudge`` / ``TapEvaluation`` from raw judge configs. On the Phase 4
seam they receive ``ctx.judge`` instead; these adapters keep the call sites
stable while routing every score through the Judge port.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from hackagent.attacks._lib.scoring import normalized_jailbreak_threshold
from hackagent.attacks.ports import Judge
from hackagent.core.contracts import Sample


class CtxJudgeAdapter:
    """``InlineStepJudge``-compatible wrapper around :class:`~hackagent.attacks.ports.Judge`.

    ``is_jailbreak`` uses ``judge.score`` and the canonical 0--10 jailbreak
    threshold from *config* (default 7.0).
    """

    def __init__(
        self,
        judge: Judge,
        *,
        config: Optional[Mapping[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._judge = judge
        self._threshold = normalized_jailbreak_threshold(config)
        self.logger = logger or logging.getLogger("hackagent.attacks.inline_judge")

    @property
    def available(self) -> bool:
        return self._judge is not None

    @property
    def judge_count(self) -> int:
        return 1 if self._judge is not None else 0

    def is_jailbreak(
        self,
        goal: str,
        prompt_prefix: str,
        response: str,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        sample = Sample(
            goal=str(goal or ""),
            prompt=str(prompt_prefix or ""),
            response=str(response or ""),
        )
        try:
            score = float(self._judge.score(sample))
        except Exception as exc:
            self.logger.warning("ctx.judge.score failed: %s", exc, exc_info=True)
            return False, 0.0, {}
        is_jb = score >= self._threshold
        return is_jb, score, {"best_score": score, "success": is_jb}


class CtxTapEvaluator:
    """Minimal TAP evaluator surface backed by ``ctx.judge.score``.

    Implements the methods ``TapSearch`` calls: ``evaluate_on_topic``,
    ``extract_scores``, and ``score_candidates``. On-topic checks default to
    keeping every candidate when no separate on-topic judge is configured on
    the Panel (Phase 6).
    """

    def __init__(
        self,
        judge: Judge,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._judge = judge
        self.logger = logger or logging.getLogger("hackagent.attacks.tap")

    def evaluate_on_topic(
        self,
        input_data: List[Dict[str, Any]],
        on_topic_judges: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        _ = on_topic_judges
        # Panel does not yet expose a dedicated on-topic role; keep branches.
        for row in input_data:
            row["eval_on_topic"] = 1
            row["explanation_on_topic"] = "On-topic check via ctx.judge (default keep)"
        return input_data

    def score_candidates(
        self,
        goal: str,
        prompts: Sequence[str],
        responses: Sequence[str],
        judges_config: Optional[List[Dict[str, Any]]] = None,
        default: int = 0,
    ) -> List[int]:
        _ = judges_config
        scores: List[int] = []
        for prompt, response in zip(prompts, responses):
            sample = Sample(
                goal=str(goal or ""),
                prompt=str(prompt or ""),
                response=str(response or ""),
            )
            try:
                raw = float(self._judge.score(sample))
                scores.append(int(round(raw)) if raw is not None else default)
            except Exception as exc:
                self.logger.warning("ctx.judge.score failed for TAP candidate: %s", exc)
                scores.append(default)
        return scores

    @staticmethod
    def extract_scores(
        evaluated: List[Dict[str, Any]],
        score_key: str,
        default: int = 0,
    ) -> List[int]:
        scores: List[int] = []
        for row in evaluated:
            value = row.get(score_key)
            if value is None:
                scores.append(default)
                continue
            try:
                scores.append(int(float(value)))
            except (TypeError, ValueError):
                scores.append(default)
        return scores


def resolve_inline_step_judge(
    config: Mapping[str, Any],
    logger: logging.Logger,
    *,
    client: Any = None,
):
    """Return a step-judge for generation loops.

    Prefers ``config["_judge"]`` (a :class:`~hackagent.attacks.ports.Judge`)
    when present; otherwise builds the legacy ``InlineStepJudge``.
    """
    port = config.get("_judge")
    if port is not None:
        adapter = CtxJudgeAdapter(port, config=config, logger=logger)
        if adapter.available:
            logger.info("⚖️  Inline judge enabled via ctx.judge")
            return adapter
        return None

    _ = client
    logger.warning(
        "No ctx.judge on this run — inline judging is skipped "
        "(legacy InlineStepJudge was removed)"
    )
    return None


def postprocess_inline_results(
    input_data: List[Dict[str, Any]],
    attack_label: str,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Fill default success fields for rows already scored during generation.

    Does not sync results or talk to storage. Server writes belong to tracking.
    """
    _ = attack_label
    for item in input_data:
        if item.get("error") and not item.get("response"):
            item.setdefault("best_score", 0.0)
            item.setdefault("success", False)
            item.setdefault("evaluation_notes", f"Execution error: {item['error']}")
        else:
            item.setdefault("best_score", 0.0)
            item.setdefault(
                "success",
                item.get("is_success", item.get("best_score", 0) > 0),
            )
    n_success = sum(1 for item in input_data if item.get("success"))
    logger.info(
        "Post-processing %s results (%s jailbreaks from inline judge)",
        len(input_data),
        n_success,
    )
    return input_data


def make_postprocess_execute(attack_label: str):
    """Pipeline step that only normalises inline-judge rows."""

    def execute(input_data, config, logger, client):
        _ = (config, client)
        return postprocess_inline_results(input_data or [], attack_label, logger)

    return execute


def attach_ctx_judge(config: Dict[str, Any], ctx: Any) -> None:
    """Expose ``ctx.judge`` on the mutable config dict for generation steps."""
    if ctx is None:
        return
    config["_judge"] = ctx.judge


__all__ = [
    "CtxJudgeAdapter",
    "CtxTapEvaluator",
    "attach_ctx_judge",
    "make_postprocess_execute",
    "postprocess_inline_results",
    "resolve_inline_step_judge",
    "verdict_from_judge",
]


def verdict_from_judge(
    judge: Judge,
    *,
    goal: str,
    prompt: str = "",
    response: str = "",
):
    """Score via ``judge.evaluate`` and return ``(score, success, explanation)``.

    Custom-loop techniques normalise through :class:`~hackagent.core.contracts.Verdict`.
    """
    from hackagent.core.contracts import Sample

    sample = Sample(
        goal=str(goal or ""),
        prompt=str(prompt or ""),
        response=str(response or ""),
    )
    verdict = judge.evaluate(sample)
    return float(verdict.score), bool(verdict.success), str(verdict.explanation or "")
