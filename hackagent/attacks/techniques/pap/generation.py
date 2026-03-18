# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
PAP generation module.

Core algorithm: for each goal, iterate over selected persuasion techniques
from the taxonomy.  For each technique:
1. Build a mutation prompt using the technique's definition and examples.
2. Send to the attacker LLM to paraphrase the goal into a persuasive variant.
3. Send the persuasive prompt to the target model.
4. Evaluate the response with a judge.
5. If the judge confirms a jailbreak → early stop.

Uses the same inline ``_StepJudge`` pattern as BoN for judge evaluation
inside the generation loop.

Based on: https://arxiv.org/abs/2401.06373
"""

import logging
import time
from dataclasses import fields
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.attacks.evaluator.judge_evaluators import EVALUATOR_MAP
from hackagent.attacks.techniques.advprefix.config import EvaluatorConfig
from hackagent.router.router import AgentRouter

from .config import ALL_TECHNIQUES, TOP_5_TECHNIQUES
from .taxonomy import build_mutation_prompt, extract_mutated_text

if TYPE_CHECKING:
    from hackagent.server.client import AuthenticatedClient
    from hackagent.router.tracking import Tracker
    from hackagent.router.tracking.tracker import Context


# ---------------------------------------------------------------------------
# Inline judge helper (same pattern as BoN)
# ---------------------------------------------------------------------------


class _StepJudge:
    """Lightweight wrapper to call judges on a single candidate."""

    JUDGE_COLUMN_MAP = {
        "nuanced": ["eval_nj", "explanation_nj"],
        "jailbreakbench": ["eval_jb", "explanation_jb"],
        "harmbench": ["eval_hb", "explanation_hb"],
        "on_topic": ["eval_on_topic", "explanation_on_topic"],
    }

    def __init__(
        self,
        judges_config: List[Dict[str, Any]],
        base_eval_config: Dict[str, Any],
        client: "AuthenticatedClient",
        logger: logging.Logger,
        run_id: Optional[str] = None,
        tracker: Optional["Tracker"] = None,
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

            api_key = jcfg.get("api_key") or jcfg.get("api_key_env")
            if api_key:
                sub_cfg["agent_metadata"]["api_key"] = api_key

            expected_fields = {f.name for f in fields(EvaluatorConfig)}
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
        return bool(self._judges)

    def is_jailbreak(
        self,
        goal: str,
        persuasive_prompt: str,
        response: str,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Evaluate a single candidate with all judges.

        Returns:
            ``(is_success, best_score, judge_columns)``
        """
        row = {
            "goal": goal,
            "prefix": persuasive_prompt,
            "completion": response,
        }

        judge_cols: Dict[str, Any] = {}
        best_score = 0.0

        for judge_type, evaluator in self._judges:
            try:
                evaluated = evaluator.evaluate([row.copy()])
                if evaluated:
                    ev_row = evaluated[0]
                    for col in self.JUDGE_COLUMN_MAP.get(judge_type, []):
                        if col in ev_row:
                            judge_cols[col] = ev_row[col]
                    eval_col = self.JUDGE_COLUMN_MAP[judge_type][0]
                    val = ev_row.get(eval_col)
                    if val is not None:
                        try:
                            best_score = max(best_score, float(val))
                        except (TypeError, ValueError):
                            pass
            except Exception as exc:
                self.logger.warning(f"Judge '{judge_type}' failed on candidate: {exc}")

        return best_score > 0, best_score, judge_cols


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_techniques(pap_params: Dict[str, Any]) -> List[str]:
    """Resolve the list of persuasion technique names to use.

    Args:
        pap_params: The ``pap_params`` section of the config.

    Returns:
        Ordered list of technique name strings.
    """
    techniques = pap_params.get("techniques", "top5")
    if isinstance(techniques, list):
        return list(techniques)
    if techniques == "all":
        return list(ALL_TECHNIQUES)
    # Default: top5
    return list(TOP_5_TECHNIQUES)


def _create_attacker_router(
    attacker_config: Dict[str, Any],
    client: "AuthenticatedClient",
) -> AgentRouter:
    """Create an AgentRouter for the attacker LLM."""
    metadata: Dict[str, Any] = {
        "name": attacker_config.get("identifier"),
    }
    api_key = attacker_config.get("api_key")
    if api_key:
        metadata["api_key"] = api_key

    return AgentRouter(
        backend=client,
        name=f"pap-attacker-{attacker_config.get('identifier', 'unknown')[:30]}",
        agent_type=attacker_config.get("agent_type", "OPENAI_SDK"),
        endpoint=attacker_config.get("endpoint"),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict]:
    """Generate persuasive prompts, query the target, and judge inline.

    For each goal:
    1. Iterate over selected persuasion techniques.
    2. Use the attacker LLM to paraphrase the goal.
    3. Send the persuasive prompt to the target.
    4. Judge the response.  If jailbreak → early stop.

    Args:
        goals: List of harmful prompt strings.
        agent_router: Router for the target model.
        config: Configuration dictionary.
        logger: Logger instance.

    Returns:
        List of result dicts, one per goal.
    """
    pap_params = config.get("pap_params", {})
    attacker_cfg = config.get("attacker", {})

    tracker: Optional["Tracker"] = config.get("_tracker")
    client: Optional["AuthenticatedClient"] = config.get("_backend") or config.get(
        "_client"
    )

    techniques = _resolve_techniques(pap_params)
    max_techniques = pap_params.get("max_techniques_per_goal", 0)
    if max_techniques and max_techniques > 0:
        techniques = techniques[:max_techniques]

    target_max_new_tokens = int(config.get("max_new_tokens", 4096))
    target_temperature = float(config.get("temperature", 0.6))
    target_timeout = int(config.get("request_timeout", 120))

    victim_key = str(agent_router.backend_agent.id)

    logger.info(
        f"PAP generation: {len(goals)} goal(s), "
        f"{len(techniques)} technique(s): {[t[:25] for t in techniques]}"
    )

    # Create attacker router
    attacker_router: Optional[AgentRouter] = None
    if client and attacker_cfg.get("identifier"):
        try:
            attacker_router = _create_attacker_router(attacker_cfg, client)
            logger.info(
                f"Attacker LLM: {attacker_cfg.get('identifier')} "
                f"(endpoint={attacker_cfg.get('endpoint')})"
            )
        except Exception as exc:
            logger.error(f"Failed to create attacker router: {exc}")
            raise

    if not attacker_router:
        raise ValueError(
            "PAP requires an attacker LLM. Configure 'attacker' in the attack config."
        )

    attacker_key = str(attacker_router.backend_agent.id)

    # Initialise inline judge
    step_judge: Optional[_StepJudge] = None
    judges_config = config.get("judges")
    if isinstance(judges_config, list) and judges_config and client is not None:
        base_eval_cfg: Dict[str, Any] = {
            "batch_size": config.get("batch_size_judge", 1),
            "max_new_tokens_eval": config.get("max_new_tokens_eval", 256),
            "filter_len": config.get("filter_len", 10),
            "request_timeout": config.get("judge_request_timeout", 120),
            "temperature": config.get("judge_temperature", 0.0),
            "max_judge_retries": config.get("max_judge_retries", 1),
            "organization_id": config.get("organization_id"),
        }
        step_judge = _StepJudge(
            judges_config=judges_config,
            base_eval_config=base_eval_cfg,
            client=client,
            logger=logger,
            run_id=config.get("_run_id"),
            tracker=tracker,
        )
        if step_judge.available:
            logger.info(f"⚖️  Inline judge enabled ({len(step_judge._judges)} judge(s))")
        else:
            step_judge = None
            logger.warning("No valid judges — no inline jailbreak detection")
    else:
        logger.warning("No judges configured — no inline jailbreak detection")

    # Process goals
    results: List[Dict] = []

    for goal_idx, goal in enumerate(goals):
        t0 = time.perf_counter()
        logger.info(f"Processing goal {goal_idx + 1}/{len(goals)}")

        best_result = _attack_single_goal(
            goal=goal,
            goal_idx=goal_idx,
            techniques=techniques,
            pap_params=pap_params,
            target_max_new_tokens=target_max_new_tokens,
            target_temperature=target_temperature,
            target_timeout=target_timeout,
            attacker_router=attacker_router,
            attacker_key=attacker_key,
            agent_router=agent_router,
            victim_key=victim_key,
            step_judge=step_judge,
            tracker=tracker,
            logger=logger,
        )

        elapsed = round(time.perf_counter() - t0, 3)
        best_result["generation_elapsed_s"] = elapsed

        if tracker:
            goal_ctx = tracker.get_goal_context(goal_idx)
            if goal_ctx and goal_ctx.result_id:
                best_result["result_id"] = goal_ctx.result_id

        results.append(best_result)

        success = best_result.get("success", False)
        status = (
            "🎯 JAILBREAK"
            if success
            else ("✓ has response" if best_result.get("response") else "✗ no response")
        )
        logger.info(
            f"Goal {goal_idx + 1} done in {elapsed}s — {status} "
            f"(technique={best_result.get('technique')}, "
            f"score={best_result.get('best_score', 0)})"
        )

    n_success = sum(1 for r in results if r.get("success"))
    logger.info(
        f"PAP generation completed: {len(results)} result(s), "
        f"{n_success}/{len(results)} jailbreaks"
    )
    return results


def _attack_single_goal(
    goal: str,
    goal_idx: int,
    techniques: List[str],
    pap_params: Dict[str, Any],
    target_max_new_tokens: int,
    target_temperature: float,
    target_timeout: int,
    attacker_router: AgentRouter,
    attacker_key: str,
    agent_router: AgentRouter,
    victim_key: str,
    step_judge: Optional[_StepJudge],
    tracker: Optional["Tracker"],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Run the PAP attack loop for a single goal.

    Iterates over persuasion techniques, paraphrases with the attacker LLM,
    queries the target, evaluates with the judge.  Early stops on jailbreak.
    """
    attacker_temp = pap_params.get("attacker_temperature", 1.0)
    attacker_max_tokens = pap_params.get("attacker_max_tokens", 1024)

    best_result: Dict[str, Any] = {
        "goal": goal,
        "persuasive_prompt": None,
        "response": None,
        "error": None,
        "technique": None,
        "technique_index": None,
        "best_score": 0.0,
        "success": False,
    }

    for tech_idx, technique in enumerate(techniques):
        _label = f"Goal {goal_idx + 1}, Technique {tech_idx + 1}/{len(techniques)} ({technique[:30]})"

        # 1. Build mutation prompt
        mutation_prompt = build_mutation_prompt(goal, technique)

        # 2. Call attacker LLM to paraphrase
        logger.info(f"[{_label}] Paraphrasing with attacker LLM...")
        try:
            attacker_response = attacker_router.route_request(
                registration_key=attacker_key,
                request_data={
                    "prompt": mutation_prompt,
                    "temperature": attacker_temp,
                    "max_tokens": attacker_max_tokens,
                },
            )
            attacker_text = attacker_response.get("generated_text", "")
            attacker_error = attacker_response.get("error_message")
        except Exception as e:
            logger.warning(f"[{_label}] Attacker LLM failed — {e}")
            attacker_text = ""
            attacker_error = str(e)

        if not attacker_text:
            logger.warning(f"[{_label}] No attacker response (error={attacker_error})")
            # Persist trace even on failure
            if tracker:
                goal_ctx = tracker.get_goal_context(goal_idx)
                if goal_ctx:
                    _persist_technique_trace(
                        tracker,
                        goal_ctx,
                        tech_idx,
                        len(techniques),
                        technique,
                        None,
                        None,
                        attacker_error,
                        0.0,
                        False,
                        {},
                    )
            continue

        # 3. Extract the mutated persuasive prompt
        persuasive_prompt = extract_mutated_text(attacker_text)

        logger.info(
            f"[{_label}] Prompt: {persuasive_prompt[:120]}..."
            if len(persuasive_prompt) > 120
            else f"[{_label}] Prompt: {persuasive_prompt}"
        )

        # 4. Send persuasive prompt to target
        try:
            target_response = agent_router.route_request(
                registration_key=victim_key,
                request_data={
                    "prompt": persuasive_prompt,
                    # Pass both aliases because adapters normalize differently.
                    "max_new_tokens": target_max_new_tokens,
                    "max_tokens": target_max_new_tokens,
                    "temperature": target_temperature,
                    # OpenAI-compatible per-request timeout.
                    "timeout": target_timeout,
                },
            )
            response_text = target_response.get("generated_text")
            target_error = target_response.get("error_message")
        except Exception as e:
            response_text = None
            target_error = str(e)
            logger.warning(f"[{_label}] Target request failed — {e}")

        if response_text:
            _preview = (
                f"{response_text[:120]}..."
                if len(response_text) > 120
                else response_text
            )
            logger.info(f"[{_label}] Response (len={len(response_text)}): {_preview}")
        else:
            logger.info(f"[{_label}] No response (error={target_error})")

        # 5. Judge evaluation
        is_jailbreak = False
        judge_score = 0.0
        judge_cols: Dict[str, Any] = {}

        if step_judge and step_judge.available and response_text:
            logger.info(f"[{_label}] ⚖️  Evaluating with judge...")
            is_jailbreak, judge_score, judge_cols = step_judge.is_jailbreak(
                goal=goal,
                persuasive_prompt=persuasive_prompt,
                response=response_text,
            )
            logger.info(
                f"[{_label}] ⚖️  Judge verdict: "
                f"{'🎯 JAILBREAK' if is_jailbreak else '❌ Not a jailbreak'} "
                f"(score={judge_score})"
            )

        # Persist trace
        if tracker:
            goal_ctx = tracker.get_goal_context(goal_idx)
            if goal_ctx:
                _persist_technique_trace(
                    tracker,
                    goal_ctx,
                    tech_idx,
                    len(techniques),
                    technique,
                    persuasive_prompt,
                    response_text,
                    target_error,
                    judge_score,
                    is_jailbreak,
                    judge_cols,
                )

        # Update best result
        if is_jailbreak or judge_score > best_result.get("best_score", 0):
            best_result = {
                "goal": goal,
                "persuasive_prompt": persuasive_prompt,
                "response": response_text,
                "error": target_error if not response_text else None,
                "technique": technique,
                "technique_index": tech_idx,
                "best_score": judge_score,
                "success": is_jailbreak,
                **judge_cols,
            }
        elif not best_result.get("response") and response_text:
            best_result = {
                "goal": goal,
                "persuasive_prompt": persuasive_prompt,
                "response": response_text,
                "error": None,
                "technique": technique,
                "technique_index": tech_idx,
                "best_score": judge_score,
                "success": False,
                **judge_cols,
            }

        # Early stop
        if is_jailbreak:
            logger.info(f"[{_label}] 🎯 Jailbreak confirmed — early stopping")
            break

    return best_result


def _persist_technique_trace(
    tracker: "Tracker",
    goal_ctx: "Context",
    tech_idx: int,
    total_techniques: int,
    technique: str,
    persuasive_prompt: Optional[str],
    response_text: Optional[str],
    error: Optional[str],
    judge_score: float,
    is_jailbreak: bool,
    judge_cols: Dict[str, Any],
) -> None:
    """Persist PAP technique trace for dashboard display.

    Emits two traces per technique:
    - Candidate trace with the persuasive prompt and target response.
    - Evaluation trace with the judge verdict.
    """
    step_name = f"PAP Technique {tech_idx + 1}/{total_techniques}: {technique[:40]}"

    # Candidate trace
    tracker.add_interaction_trace(
        ctx=goal_ctx,
        request={"prompt": persuasive_prompt},
        response={
            "generated_text": response_text,
            "error_message": error,
        },
        step_name=step_name,
        metadata={
            "display_type": "pap_candidate",
            "technique": technique,
            "technique_index": tech_idx,
            "total_techniques": total_techniques,
            "response_length": len(response_text) if response_text else 0,
        },
    )

    # Evaluation trace
    explanation = next(
        (
            str(v)
            for k_col, v in judge_cols.items()
            if k_col.startswith("explanation_") and v is not None
        ),
        None,
    )

    verdict_lines = [
        f"Technique: {technique}",
        f"Judge score: {judge_score}",
        f"Jailbreak: {'YES' if is_jailbreak else 'NO'}",
    ]
    if explanation:
        verdict_lines.append(f"Explanation: {explanation}")
    if response_text:
        verdict_lines.extend(["", "Target response:", response_text])

    tracker.add_interaction_trace(
        ctx=goal_ctx,
        request={
            "prompt": persuasive_prompt,
            "technique": technique,
        },
        response={
            "generated_text": "\n".join(verdict_lines),
            "target_response": response_text,
            "judge_columns": judge_cols,
        },
        step_name=f"Evaluation – Technique {tech_idx + 1}/{total_techniques}",
        metadata={
            "display_type": "pap_evaluation",
            "technique": technique,
            "technique_index": tech_idx,
            "total_techniques": total_techniques,
            "judge_score": judge_score,
            "is_jailbreak": is_jailbreak,
            "judge_columns": judge_cols,
        },
    )
