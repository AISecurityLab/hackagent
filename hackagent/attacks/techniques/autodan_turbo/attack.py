# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""AutoDAN-Turbo attack orchestrator — 3-step pipeline (WarmUp → Lifelong → Evaluation)."""

import copy
import logging
import os
from typing import Any, Dict, List

from hackagent.attacks.shared.tui import with_tui_logging
from hackagent.attacks.techniques.base import BaseAttack

from . import evaluation, lifelong, warm_up
from .config import DEFAULT_AUTODAN_TURBO_CONFIG
from .dashboard_tracing import emit_phase_trace
from .log_styles import format_phase_message, phase_separator


def _deep_update(target, source):
    """Recursively merge user config into defaults.

    Args:
        target: Destination dictionary (mutated in place).
        source: Source dictionary whose values override destination.

    Returns:
        None.
    """
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_update(target[k], v)
        else:
            target[k] = (
                copy.deepcopy(v)
                if not (isinstance(k, str) and k.startswith("_"))
                else v
            )


class AutoDANTurboAttack(BaseAttack):
    """AutoDAN-Turbo: Lifelong agent for strategy self-exploration in jailbreaking LLMs.

    Three-phase pipeline:
    1. WarmUp — free exploration to bootstrap a strategy library
    2. Lifelong — strategy-guided attacks with retrieval + summarization
    3. Evaluation — multi-judge scoring for consistent metrics
    """

    def __init__(self, config=None, client=None, agent_router=None):
        """Initialize AutoDAN-Turbo attack with merged defaults.

        Args:
            config: Optional user overrides for default config.
            client: Authenticated API client (required).
            agent_router: Router to the target model (required).

        Returns:
            None.

        Raises:
            ValueError: If ``client`` or ``agent_router`` are missing.
        """
        if not client:
            raise ValueError("AuthenticatedClient required")
        if not agent_router:
            raise ValueError("AgentRouter required")

        cfg = copy.deepcopy(DEFAULT_AUTODAN_TURBO_CONFIG)
        if config:
            _deep_update(cfg, config)

        self.logger = logging.getLogger("hackagent.attacks.autodan_turbo")
        super().__init__(cfg, client, agent_router)

    def _validate_config(self):
        """Validate AutoDAN-Turbo specific configuration constraints.

        Returns:
            None.

        Raises:
            ValueError: If required fields are invalid or missing.
        """
        super()._validate_config()
        params = self.config.get("autodan_turbo_params", {})
        if params.get("epochs", 0) < 1:
            raise ValueError("epochs must be >= 1")
        if not self.config.get("attacker", {}).get("identifier"):
            raise ValueError("attacker.identifier required")

    def _get_pipeline_steps(self):
        """Disable BaseAttack static pipeline; orchestration is manual in ``run``.

        Paper mapping: AutoDAN-Turbo uses iterative loops with internal scoring
        and strategy updates, so warm-up/lifelong/evaluation are tracked
        explicitly in ``run`` instead of declarative fixed steps.

        Returns:
            Empty list.
        """
        return []  # Managed manually in run() (like PAIR)

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict[str, Any]]:
        """Execute full 3-step AutoDAN-Turbo pipeline.

        Pipeline mapping to paper/integration:
        1) WarmUp: free exploration + strategy library bootstrap
        2) Lifelong: retrieval-guided attack with online strategy growth
        3) Evaluation: hackagent multi-judge scoring harmonization

        Args:
            goals: List of malicious goals to attack.

        Returns:
            Final per-goal result list, enriched with attack and judge metrics.

        Raises:
            Exception: Re-raises any runtime failure after coordinator finalization.
        """
        if not goals:
            return []

        params = self.config.get("autodan_turbo_params", {})
        coordinator = self._initialize_coordinator(attack_type="autodan_turbo")
        coordinator.initialize_goals(
            goals,
            {
                "attack_type": "autodan_turbo",
                "epochs": params.get("epochs", 100),
                "warm_up_iterations": params.get("warm_up_iterations", 1),
                "lifelong_iterations": params.get("lifelong_iterations", 1),
            },
        )
        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        role_models = {
            role: (
                (self.config.get(role, {}) or {}).get("identifier")
                or (self.config.get(role, {}) or {}).get("model")
                or (self.config.get(role, {}) or {}).get("name")
                or "unknown-model"
            )
            for role in ("attacker", "scorer", "summarizer")
        }

        backend_agent = getattr(self.agent_router, "backend_agent", None)
        registration_key = (
            str(getattr(backend_agent, "id", "")) if backend_agent else ""
        )
        registry = getattr(self.agent_router, "_agent_registry", {})
        adapter = registry.get(registration_key) if isinstance(registry, dict) else None
        target_model = getattr(adapter, "model_name", None)
        if not target_model:
            adapter_cfg = getattr(adapter, "config", {}) if adapter else {}
            if isinstance(adapter_cfg, dict):
                target_model = adapter_cfg.get("name") or adapter_cfg.get("model")
        if not target_model:
            metadata = getattr(backend_agent, "metadata", {}) if backend_agent else {}
            if isinstance(metadata, dict):
                target_model = metadata.get("name") or metadata.get("model")
        if not target_model:
            target_model = (
                getattr(backend_agent, "name", None) if backend_agent else None
            )
        target_model = target_model or "unknown-model"

        self.logger.info(
            format_phase_message(
                "pipeline",
                "AutoDAN-Turbo LLM map -> "
                f"attacker:{role_models['attacker']} | "
                f"scorer:{role_models['scorer']} | "
                f"summarizer:{role_models['summarizer']} | "
                f"target:{target_model}",
            )
        )

        try:
            # Step 1: WarmUp — free exploration + strategy library building
            self.logger.info(phase_separator("warmup", "starting phase"))
            for goal_idx, goal in enumerate(goals):
                emit_phase_trace(
                    self.config,
                    phase="WARMUP",
                    subphase="PHASE_START",
                    step_name="Warmup - Start",
                    goal=goal,
                    goal_idx=goal_idx,
                    payload={
                        "dashboard_section": "Warmup",
                        "dashboard_group": "Warmup",
                        "dashboard_item": "Start",
                        "message": "WarmUp phase started",
                    },
                )
            with self.tracker.track_step(
                "WarmUp: Free exploration",
                "GENERATION",
                goals[:3],
                {"warm_up_iterations": params.get("warm_up_iterations", 1)},
            ):
                strategy_lib, warm_up_log = warm_up.execute(
                    goals,
                    self.config,
                    self.client,
                    self.agent_router,
                    self.logger,
                )
            self.logger.info(
                format_phase_message(
                    "warmup", f"WarmUp complete: {strategy_lib.size()} strategies"
                )
            )
            for goal_idx, goal in enumerate(goals):
                emit_phase_trace(
                    self.config,
                    phase="WARMUP",
                    subphase="PHASE_END",
                    step_name="Warmup - End",
                    goal=goal,
                    goal_idx=goal_idx,
                    payload={
                        "dashboard_section": "Warmup",
                        "dashboard_group": "Warmup",
                        "dashboard_item": "End",
                        "strategy_count": strategy_lib.size(),
                    },
                )

            # Step 2: Lifelong — strategy-guided attacks
            self.logger.info(phase_separator("lifelong", "starting phase"))
            for goal_idx, goal in enumerate(goals):
                emit_phase_trace(
                    self.config,
                    phase="LIFELONG",
                    subphase="PHASE_START",
                    step_name="Lifelong - Start",
                    goal=goal,
                    goal_idx=goal_idx,
                    payload={
                        "dashboard_section": "Lifelong",
                        "dashboard_group": "Lifelong",
                        "dashboard_item": "Start",
                        "message": "Lifelong phase started",
                    },
                )
            with self.tracker.track_step(
                "Lifelong: Strategy-guided attacks",
                "GENERATION",
                goals[:3],
                {"lifelong_iterations": params.get("lifelong_iterations", 1)},
            ):
                results = lifelong.execute(
                    goals,
                    self.config,
                    self.client,
                    self.agent_router,
                    self.logger,
                    strategy_lib,
                )
            self.logger.info(
                format_phase_message(
                    "lifelong", f"Lifelong complete: {len(results)} results"
                )
            )
            for goal_idx, goal in enumerate(goals):
                emit_phase_trace(
                    self.config,
                    phase="LIFELONG",
                    subphase="PHASE_END",
                    step_name="Lifelong - End",
                    goal=goal,
                    goal_idx=goal_idx,
                    payload={
                        "dashboard_section": "Lifelong",
                        "dashboard_group": "Lifelong",
                        "dashboard_item": "End",
                        "num_results": len(results),
                    },
                )

            results = coordinator.enrich_with_result_ids(results)

            # Step 3: Evaluation — multi-judge scoring
            self.logger.info(phase_separator("evaluation", "starting phase"))
            with self.tracker.track_step(
                "Evaluation: Multi-judge scoring",
                "EVALUATION",
                results[:3],
                {},
            ):
                results = evaluation.execute(
                    results, self.config, self.client, self.logger
                )

            for idx, result in enumerate(results):
                self.logger.info(
                    format_phase_message(
                        "final",
                        f"Goal {idx}: autodan_score={result.get('autodan_score', result.get('attack_score', 0.0)):.1f}/10 | "
                        f"judge_best_score={result.get('best_score', 0.0):.1f} | "
                        f"success={result.get('success', False)}",
                    )
                )

            # Finalize
            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            # Save strategy library
            output_dir = self.config.get("output_dir", ".")
            os.makedirs(output_dir, exist_ok=True)
            strategy_lib.save(f"{output_dir}/strategy_library")

            return results

        except Exception:
            coordinator.finalize_on_error("AutoDAN-Turbo failed")
            raise
