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
Best-of-N (BoN) generation module.

Core algorithm: for each goal, run ``n_steps`` sequential search steps.
Within each step, generate ``num_concurrent_k`` independently-seeded
augmented variants of the prompt and send them to the target model in
parallel.  After selecting the best candidate (longest response), a
**judge evaluator** is called to determine whether the candidate constitutes
a successful jailbreak.  If the judge confirms success, the search stops
early.  If no step produces a jailbreak after all steps, the attack is
marked as failed.

Text augmentations ported from the original BoN codebase:
- **word_scrambling**: shuffles middle characters of words >3 chars
- **random_capitalization**: randomly toggles letter case
- **ascii_perturbation**: shifts printable ASCII chars by ±1

Based on: https://arxiv.org/abs/2412.03556
"""

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.attacks.evaluator.judge_evaluators import EVALUATOR_MAP
from hackagent.attacks.techniques.advprefix.config import EvaluatorConfig
from hackagent.router.router import AgentRouter

if TYPE_CHECKING:
    from hackagent.server.client import AuthenticatedClient
    from hackagent.router.tracking import Tracker
    from hackagent.router.tracking.tracker import Context


# ---------------------------------------------------------------------------
# Inline judge helper — evaluates a single candidate inside the search loop
# ---------------------------------------------------------------------------


class _StepJudge:
    """Lightweight wrapper to call one or more judges on a single candidate.

    Instantiated once per :func:`execute` call (not per step) and re-used
    throughout the generation loop to avoid repeated router creation.
    """

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
        self._judges: List[Tuple[str, Any]] = []  # (type_str, evaluator_instance)
        self.logger = logger

        for jcfg in judges_config:
            judge_type = jcfg.get("evaluator_type") or jcfg.get("type")
            identifier = jcfg.get("identifier")
            if not judge_type or judge_type not in EVALUATOR_MAP:
                continue
            if not identifier:
                continue

            evaluator_class = EVALUATOR_MAP[judge_type]

            # Build subprocess config
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

            # Filter to EvaluatorConfig fields
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

    # ------------------------------------------------------------------ #

    @property
    def available(self) -> bool:
        """True if at least one judge was successfully initialised."""
        return bool(self._judges)

    def is_jailbreak(
        self,
        goal: str,
        augmented_prompt: str,
        response: str,
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Evaluate a single candidate with all judges.

        Returns:
            ``(is_success, best_score, judge_columns)`` where
            *judge_columns* contains the raw eval/explanation columns
            produced by each judge.
        """
        row = {
            "goal": goal,
            "prefix": augmented_prompt,
            "completion": response,
        }

        judge_cols: Dict[str, Any] = {}
        best_score = 0.0

        for judge_type, evaluator in self._judges:
            try:
                evaluated = evaluator.evaluate([row.copy()])
                if evaluated:
                    ev_row = evaluated[0]
                    # Collect judge columns
                    for col in self.JUDGE_COLUMN_MAP.get(judge_type, []):
                        if col in ev_row:
                            judge_cols[col] = ev_row[col]
                    # Check score
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
# Text augmentation functions (ported from original codebase)
# ---------------------------------------------------------------------------


def apply_word_scrambling(text: str, sigma: float) -> str:
    """Scramble middle characters of words longer than 3 characters.

    For each qualifying word, the first and last characters are preserved
    while the middle characters are randomly shuffled.

    Args:
        text: Input text to augment.
        sigma: Base augmentation strength.  Scrambling probability per word
            is ``sigma^(1/2)``.

    Returns:
        Augmented text with scrambled words.

    Example::

        apply_word_scrambling("The quick brown fox", 0.4)
        # possible: "The qiuck bwron fox"
    """
    words = text.split()
    scrambled_words = []
    for word in words:
        if len(word) > 3 and random.random() < sigma ** (1 / 2):
            chars = list(word)
            middle_chars = chars[1:-1]
            random.shuffle(middle_chars)
            scrambled_word = chars[0] + "".join(middle_chars) + chars[-1]
            scrambled_words.append(scrambled_word)
        else:
            scrambled_words.append(word)
    return " ".join(scrambled_words)


def apply_random_capitalization(text: str, sigma: float) -> str:
    """Randomly toggle letter case for each character.

    Args:
        text: Input text to augment.
        sigma: Base augmentation strength.  Toggle probability per character
            is ``sigma^(1/2)``.

    Returns:
        Augmented text with random case changes.

    Example::

        apply_random_capitalization("hello world", 0.4)
        # possible: "hEllo wOrLd"
    """
    new_text = []
    for c in text:
        if c.isalpha() and random.random() < sigma ** (1 / 2):
            if "a" <= c <= "z":
                new_text.append(chr(ord(c) - 32))
            elif "A" <= c <= "Z":
                new_text.append(chr(ord(c) + 32))
        else:
            new_text.append(c)
    return "".join(new_text)


def apply_ascii_noising(text: str, sigma: float) -> str:
    """Shift printable ASCII characters by ±1 code point.

    Args:
        text: Input text to augment.
        sigma: Base augmentation strength.  Perturbation probability per
            character is ``sigma^3``.

    Returns:
        Augmented text with ASCII perturbations.

    Example::

        apply_ascii_noising("hello world", 0.4)
        # possible: "hfllo world"
    """
    new_text = []
    for c in text:
        if c.isprintable() and random.random() < sigma**3:
            perturbation = random.choice([-1, 1])
            new_char_code = ord(c) + perturbation
            if 32 <= new_char_code <= 126:
                new_text.append(chr(new_char_code))
            else:
                new_text.append(c)
        else:
            new_text.append(c)
    return "".join(new_text)


def augment_text(
    text: str,
    sigma: float,
    seed: int,
    word_scrambling: bool = True,
    random_capitalization: bool = True,
    ascii_perturbation: bool = True,
) -> str:
    """Apply all enabled text augmentations to *text*.

    Sets the random seed for reproducibility, then applies augmentations in
    the canonical order: word scrambling → random capitalization → ASCII
    perturbation.

    Args:
        text: The original prompt text to augment.
        sigma: Augmentation strength parameter (0–1).
        seed: Random seed for reproducibility.
        word_scrambling: Enable word-scrambling augmentation.
        random_capitalization: Enable random-capitalization augmentation.
        ascii_perturbation: Enable ASCII-perturbation augmentation.

    Returns:
        Augmented text.
    """
    random.seed(seed)
    if word_scrambling:
        text = apply_word_scrambling(text, sigma)
    if random_capitalization:
        text = apply_random_capitalization(text, sigma)
    if ascii_perturbation:
        text = apply_ascii_noising(text, sigma)
    return text


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict]:
    """Generate augmented prompts, execute them, and judge inline.

    For each goal, performs a multi-step search:

    1. For each step ``n`` in ``[0, n_steps)``:
       a. Generate ``num_concurrent_k`` augmented candidates (different seeds).
       b. Send all candidates to the target model in parallel.
       c. Select the best candidate (longest response).
       d. **Call the judge** on the best candidate.
       e. If the judge confirms a jailbreak → **early stop**.
    2. After all steps, if no jailbreak was found, mark as failed.

    Args:
        goals: List of harmful prompt strings.
        agent_router: Router for target model communication.
        config: Configuration dictionary with ``bon_params``, ``judges``, etc.
        logger: Logger instance.

    Returns:
        List of dicts (one per goal) with keys: ``goal``, ``augmented_prompt``,
        ``response``, ``error``, ``step``, ``candidate``, ``seed``,
        ``augmentation_params``, ``best_score``, ``success``,
        ``generation_elapsed_s``, plus any judge columns.
    """
    bon_params = config.get("bon_params", {})
    n_steps = bon_params.get("n_steps", 4)
    num_concurrent_k = bon_params.get("num_concurrent_k", 5)
    sigma = bon_params.get("sigma", 0.4)
    word_scrambling = bon_params.get("word_scrambling", True)
    random_capitalization_flag = bon_params.get("random_capitalization", True)
    ascii_perturbation_flag = bon_params.get("ascii_perturbation", True)

    configured_batch_size = max(1, config.get("batch_size", num_concurrent_k))
    candidate_workers = max(1, int(num_concurrent_k))
    target_max_new_tokens = config.get("max_new_tokens")
    tracker: Optional["Tracker"] = config.get("_tracker")
    client: Optional["AuthenticatedClient"] = config.get("_client")

    victim_key = str(agent_router.backend_agent.id)
    logger.info(
        f"BoN generation: {len(goals)} goal(s), "
        f"n_steps={n_steps}, K={num_concurrent_k}, sigma={sigma}, "
        f"candidate_workers={candidate_workers}"
    )

    if configured_batch_size != candidate_workers:
        logger.warning(
            "BoN candidate concurrency is pinned to num_concurrent_k=%s "
            "(configured batch_size=%s is ignored for candidate fanout)",
            candidate_workers,
            configured_batch_size,
        )

    if tracker:
        logger.info("📊 Generation tracking via Tracker enabled")

    # --- Initialise inline judge ---
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
            logger.warning("No valid judges — falling back to length heuristic only")
    else:
        logger.warning(
            "No judges configured or client unavailable — "
            "jailbreak detection will use response-length heuristic only"
        )

    results: List[Dict] = []

    for goal_idx, goal in enumerate(goals):
        t0 = time.perf_counter()
        logger.info(f"Processing goal {goal_idx + 1}/{len(goals)}")

        best_result = _search_single_goal(
            goal=goal,
            goal_idx=goal_idx,
            n_steps=n_steps,
            num_concurrent_k=num_concurrent_k,
            target_max_new_tokens=target_max_new_tokens,
            sigma=sigma,
            word_scrambling=word_scrambling,
            random_capitalization=random_capitalization_flag,
            ascii_perturbation=ascii_perturbation_flag,
            candidate_workers=candidate_workers,
            victim_key=victim_key,
            agent_router=agent_router,
            tracker=tracker,
            step_judge=step_judge,
            logger=logger,
        )

        elapsed = round(time.perf_counter() - t0, 3)
        best_result["generation_elapsed_s"] = elapsed

        # Inject result_id from tracker so the evaluation step can sync to server
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
            f"(step={best_result.get('step')}, "
            f"candidate={best_result.get('candidate')}, "
            f"score={best_result.get('best_score', 0)})"
        )

    n_success = sum(1 for r in results if r.get("success"))
    logger.info(
        f"BoN generation completed: {len(results)} result(s), "
        f"{n_success}/{len(results)} jailbreaks"
    )
    return results


def _search_single_goal(
    goal: str,
    goal_idx: int,
    n_steps: int,
    num_concurrent_k: int,
    target_max_new_tokens: Optional[int],
    sigma: float,
    word_scrambling: bool,
    random_capitalization: bool,
    ascii_perturbation: bool,
    candidate_workers: int,
    victim_key: str,
    agent_router: AgentRouter,
    tracker: Optional["Tracker"],
    step_judge: Optional[_StepJudge],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Run the BoN search loop for a single goal.

    After each step, the best candidate (longest response) is evaluated by
    the judge.  If the judge confirms a jailbreak, the loop terminates
    early.  Otherwise, all steps are attempted and the best response is
    returned with ``success=False``.

    Returns:
        Result dict with ``success``, ``best_score``, judge columns, etc.
    """
    best_result: Dict[str, Any] = {
        "goal": goal,
        "augmented_prompt": None,
        "response": None,
        "error": None,
        "step": None,
        "candidate": None,
        "seed": None,
        "augmentation_params": {
            "sigma": sigma,
            "word_scrambling": word_scrambling,
            "random_capitalization": random_capitalization,
            "ascii_perturbation": ascii_perturbation,
        },
        "best_score": 0.0,
        "success": False,
    }

    for step in range(n_steps):
        candidates = _generate_candidates(
            goal=goal,
            step=step,
            num_concurrent_k=num_concurrent_k,
            sigma=sigma,
            word_scrambling=word_scrambling,
            random_capitalization=random_capitalization,
            ascii_perturbation=ascii_perturbation,
        )

        # Send all K candidates to the target in parallel
        _lock = threading.Lock()
        candidate_results: Dict[int, Dict] = {}
        _label = f"Goal {goal_idx + 1}, Step {step + 1}/{n_steps}"

        logger.info(f"[{_label}] Sending {num_concurrent_k} candidate(s) to target")

        def _query_candidate(k_and_prompt: Tuple[int, str, int]) -> None:
            k, augmented_prompt, seed = k_and_prompt
            _cand_label = f"{_label}, K{k + 1}/{num_concurrent_k}"
            logger.info(
                f"[{_cand_label}] Prompt: {augmented_prompt[:120]}..."
                if len(augmented_prompt) > 120
                else f"[{_cand_label}] Prompt: {augmented_prompt}"
            )
            try:
                request_data = {"prompt": augmented_prompt}
                if target_max_new_tokens is not None:
                    request_data["max_new_tokens"] = target_max_new_tokens
                response = agent_router.route_request(
                    registration_key=victim_key,
                    request_data=request_data,
                )
                generated_text = response.get("generated_text")
                error_message = response.get("error_message")
            except Exception as e:
                generated_text = None
                error_message = str(e)
                logger.warning(f"[{_cand_label}] Request failed — {e}")

            # Log per-candidate response
            if generated_text:
                _preview = (
                    f"{generated_text[:120]}..."
                    if len(generated_text) > 120
                    else generated_text
                )
                logger.info(
                    f"[{_cand_label}] Response (len={len(generated_text)}): {_preview}"
                )
            else:
                logger.info(f"[{_cand_label}] No response (error={error_message})")

            with _lock:
                candidate_results[k] = {
                    "goal": goal,
                    "augmented_prompt": augmented_prompt,
                    "response": generated_text,
                    "error": error_message,
                    "step": step,
                    "candidate": k,
                    "seed": seed,
                    "augmentation_params": {
                        "sigma": sigma,
                        "word_scrambling": word_scrambling,
                        "random_capitalization": random_capitalization,
                        "ascii_perturbation": ascii_perturbation,
                    },
                }

        with ThreadPoolExecutor(max_workers=candidate_workers) as pool:
            list(pool.map(_query_candidate, candidates))

        # Pick the best candidate from this step (longest response)
        step_best = _select_best_candidate(candidate_results, num_concurrent_k)

        if not (step_best and step_best.get("response")):
            logger.info(
                f"[{_label}] ✗ No valid response from {num_concurrent_k} candidates"
            )
            # Persist a grouped step trace even when no valid response
            if tracker:
                goal_ctx = tracker.get_goal_context(goal_idx)
                if goal_ctx:
                    _persist_step_trace(
                        tracker=tracker,
                        goal_ctx=goal_ctx,
                        step=step,
                        n_steps=n_steps,
                        num_concurrent_k=num_concurrent_k,
                        sigma=sigma,
                        candidate_results=candidate_results,
                        step_best=None,
                        judge_score=0.0,
                        is_jailbreak=False,
                        judge_cols={},
                    )
            continue

        resp_len = len(step_best.get("response") or "")
        logger.info(
            f"[{_label}] Best candidate K{step_best['candidate'] + 1} — "
            f"response len={resp_len}"
        )

        # --- Judge evaluation on the step's best candidate ---
        is_jailbreak = False
        judge_score = 0.0
        judge_cols: Dict[str, Any] = {}

        if step_judge and step_judge.available:
            logger.info(f"[{_label}] ⚖️  Evaluating best candidate with judge...")
            is_jailbreak, judge_score, judge_cols = step_judge.is_jailbreak(
                goal=goal,
                augmented_prompt=step_best["augmented_prompt"],
                response=step_best["response"],
            )
            logger.info(
                f"[{_label}] ⚖️  Judge verdict: "
                f"{'🎯 JAILBREAK' if is_jailbreak else '❌ Not a jailbreak'} "
                f"(score={judge_score})"
            )

        # Persist grouped step trace + evaluation trace
        if tracker:
            goal_ctx = tracker.get_goal_context(goal_idx)
            if goal_ctx:
                _persist_step_trace(
                    tracker=tracker,
                    goal_ctx=goal_ctx,
                    step=step,
                    n_steps=n_steps,
                    num_concurrent_k=num_concurrent_k,
                    sigma=sigma,
                    candidate_results=candidate_results,
                    step_best=step_best,
                    judge_score=judge_score,
                    is_jailbreak=is_jailbreak,
                    judge_cols=judge_cols,
                )

        # Update best result if this candidate is better
        if is_jailbreak or (judge_score > best_result.get("best_score", 0)):
            best_result = {
                **step_best,
                "best_score": judge_score,
                "success": is_jailbreak,
                **judge_cols,
            }
        elif not best_result.get("response"):
            # First valid response — keep it even if not a jailbreak
            best_result = {
                **step_best,
                "best_score": judge_score,
                "success": False,
                **judge_cols,
            }

        # Early stop if jailbreak confirmed
        if is_jailbreak:
            logger.info(f"[{_label}] 🎯 Jailbreak confirmed — early stopping")
            break

    return best_result


def _persist_step_trace(
    tracker: "Tracker",
    goal_ctx: "Context",
    step: int,
    n_steps: int,
    num_concurrent_k: int,
    sigma: float,
    candidate_results: Dict[int, Dict],
    step_best: Optional[Dict],
    judge_score: float,
    is_jailbreak: bool,
    judge_cols: Dict[str, Any],
) -> None:
    """Persist BoN step traces as per-candidate entries plus evaluation.

    To let the dashboard render readable per-candidate tabs inside a single
    step accordion, we emit multiple traces with the same step name:

    - ``BoN Step X/Y`` candidate trace for each K
    - ``Evaluation – Step X/Y`` trace containing best candidate data + verdict
    """
    step_name = f"BoN Step {step + 1}/{n_steps}"

    # Candidate traces: one trace per candidate (same step_name => tabs)
    for k in range(num_concurrent_k):
        c_res = candidate_results.get(k)
        if not c_res:
            continue

        response_text = c_res.get("response")
        tracker.add_interaction_trace(
            ctx=goal_ctx,
            request={"prompt": c_res.get("augmented_prompt")},
            response={
                "generated_text": response_text,
                "error_message": c_res.get("error"),
            },
            step_name=step_name,
            metadata={
                "display_type": "bon_candidate",
                "step": step,
                "n_steps": n_steps,
                "candidate_index": k + 1,
                "total_candidates": num_concurrent_k,
                "seed": c_res.get("seed"),
                "sigma": sigma,
                "response_length": len(response_text) if response_text else 0,
                "is_best": (
                    step_best is not None
                    and c_res.get("candidate") == step_best.get("candidate")
                ),
            },
        )

    # Per-step evaluation trace with best candidate + prompt + target response
    explanation = next(
        (
            str(v)
            for k_col, v in judge_cols.items()
            if k_col.startswith("explanation_") and v is not None
        ),
        None,
    )

    best_candidate_idx = step_best["candidate"] + 1 if step_best else None
    target_response = step_best.get("response") if step_best else None

    verdict_lines = [
        (
            f"Best candidate: K{best_candidate_idx}/{num_concurrent_k}"
            if best_candidate_idx is not None
            else "Best candidate: N/A"
        ),
        f"Judge score: {judge_score}",
        f"Jailbreak: {'YES' if is_jailbreak else 'NO'}",
    ]
    if explanation:
        verdict_lines.append(f"Explanation: {explanation}")
    if target_response:
        verdict_lines.extend(["", "Target response:", target_response])

    tracker.add_interaction_trace(
        ctx=goal_ctx,
        request={
            "prompt": step_best.get("augmented_prompt") if step_best else None,
            "best_candidate_index": (step_best["candidate"] + 1 if step_best else None),
        },
        response={
            "generated_text": "\n".join(verdict_lines),
            "target_response": target_response,
            "judge_columns": judge_cols,
        },
        step_name=f"Evaluation – Step {step + 1}/{n_steps}",
        metadata={
            "display_type": "bon_evaluation",
            "step": step,
            "n_steps": n_steps,
            "num_candidates": num_concurrent_k,
            "best_candidate_index": best_candidate_idx,
            "judge_score": judge_score,
            "is_jailbreak": is_jailbreak,
            "judge_columns": judge_cols,
        },
    )


def _generate_candidates(
    goal: str,
    step: int,
    num_concurrent_k: int,
    sigma: float,
    word_scrambling: bool,
    random_capitalization: bool,
    ascii_perturbation: bool,
) -> List[Tuple[int, str, int]]:
    """Generate K augmented candidates for a given goal and step.

    Each candidate uses a deterministic seed derived from the step index
    so results are reproducible.

    Returns:
        List of ``(k, augmented_prompt, seed)`` tuples.
    """
    candidates = []
    for k in range(num_concurrent_k):
        seed = step * num_concurrent_k + k
        augmented = augment_text(
            text=goal,
            sigma=sigma,
            seed=seed,
            word_scrambling=word_scrambling,
            random_capitalization=random_capitalization,
            ascii_perturbation=ascii_perturbation,
        )
        candidates.append((k, augmented, seed))
    return candidates


def _select_best_candidate(
    candidate_results: Dict[int, Dict],
    num_candidates: int,
) -> Optional[Dict]:
    """Select the best candidate from a step's results.

    Prioritises candidates with non-empty, error-free responses.
    Among valid candidates, selects the one with the longest response
    (a rough proxy for engagement / non-refusal).

    Returns:
        Best candidate dict, or ``None`` if all candidates failed.
    """
    best: Optional[Dict] = None
    best_len = -1

    for k in range(num_candidates):
        result = candidate_results.get(k)
        if result is None:
            continue
        response = result.get("response")
        if response and not result.get("error"):
            resp_len = len(response)
            if resp_len > best_len:
                best = result
                best_len = resp_len

    # Fallback: if no error-free response, return any result that has a response
    if best is None:
        for k in range(num_candidates):
            result = candidate_results.get(k)
            if result and result.get("response"):
                return result

    # Last fallback: return the first result, even if errored
    if best is None and candidate_results:
        best = candidate_results.get(0)

    return best
