# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base class for attack technique implementations.

This module provides BaseAttack, the abstract base class for all attack
technique implementations. Techniques focus purely on attack algorithms
and evaluation, without knowledge of server integration.

Architecture:
    HackAgent → AttackOrchestrator → BaseAttack → Pipeline stages

Forward construction is ``BaseAttack(config, ctx)`` with
``run(goals) -> list[AttackResult]``. ``config`` is an
:class:`~hackagent.attacks.config.AttackConfig` (or a plain dict). ``ctx``
is a :class:`~hackagent.attacks.ports.RunContext`. Pipeline stages may be
typed :class:`~hackagent.attacks.ports.Step` values or legacy dicts.

The orchestrator still instantiates shipped techniques as
``(config_dict, client, agent_router)`` until they migrate. That legacy
path, including ``client=`` as a keyword, remains supported.

Attack techniques are organized in:
    techniques/advprefix/attack.py    - AdvPrefixAttack
    techniques/static_template/attack.py - StaticTemplateAttack
    techniques/pair/attack.py         - PAIRAttack

Each technique:
- Extends BaseAttack
- Implements run(goals)
- Returns list[AttackResult]

The orchestration layer (attacks/orchestrator.py) handles server integration,
allowing techniques to focus solely on attack algorithms.
"""

import abc
from hackagent.core.logging import get_logger
from typing import Any, Dict, List, Optional, Sequence, Union

from hackagent.attacks.config import AttackConfig, roles_from_paths
from hackagent.attacks.ports import RunContext, Step
from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import Goal
from hackagent.router.tracking import StepTracker, TrackingCoordinator

logger = get_logger(__name__)


class BaseAttack(abc.ABC):
    """
    Abstract base class for attack technique implementations.

    Provides common infrastructure that all attacks need:
    - Configuration handling (typed :class:`~hackagent.attacks.config.AttackConfig` or dict)
    - Run directory management
    - Tracking initialization
    - Pipeline execution (typed :class:`~hackagent.attacks.ports.Step` or legacy dicts)

    Prefer ``BaseAttack(config, ctx)``. Logging handlers are not installed
    here; interfaces own logging.

    Subclasses:
    1. Optionally set ``config_model`` to an AttackConfig subclass
    2. Implement ``_validate_config()`` when extra validation is required
    3. Implement ``_get_pipeline_steps()`` (``Step`` or legacy dict)
    4. Implement ``run(goals)``

    Shipped techniques still use the legacy ``(config, client, agent_router)``
    constructor. Do not treat every technique as already migrated.

    Attributes:
        config: Plain dict view of the attack config (``model_dump()`` when
            an AttackConfig was passed).
        attack_config: The AttackConfig instance, or None when a dict was passed.
        ctx: RunContext on the new seam, otherwise None.
        backend: Storage backend on the legacy path; None when ``ctx`` is set.
        agent_router: Target router. On the new seam this is ``ctx.target``.
        logger: Logger instance for this attack.
        run_id: Unique run identifier (``ctx.run_id``, else the config dict).
        run_dir: Output directory (``ctx.workspace.root``, else ``output_dir``).
        coordinator: TrackingCoordinator for unified tracking.
        tracker: StepTracker for execution tracking (alias for coordinator.step_tracker).
    """

    #: Optional typed config model for the technique (Phase 4+).
    config_model: type[AttackConfig] | None = None

    def __init__(
        self,
        config: Union[AttackConfig, Dict[str, Any]],
        ctx_or_client: Any = None,
        agent_router: Any = None,
        *,
        ctx: Optional[RunContext] = None,
        client: Any = None,
    ):
        """Initialize with ``(config, ctx)`` or legacy ``(config, client, agent_router)``.

        Phase 4 seam: prefer ``BaseAttack(config, ctx)``. Existing techniques
        and the orchestrator still pass ``(config_dict, client, agent_router)``
        (including ``client=`` as a keyword); that path stays until Phase 5
        migrates them. Logging handlers are no longer installed here —
        interfaces own logging (D12).
        """
        if not isinstance(config, (AttackConfig, dict)):
            raise ValueError(f"config must be AttackConfig or dict, got {type(config)}")
        if ctx is None and isinstance(ctx_or_client, RunContext):
            ctx = ctx_or_client

        self.ctx: Optional[RunContext] = ctx
        self.attack_config: Optional[AttackConfig] = (
            config if isinstance(config, AttackConfig) else None
        )

        if ctx is not None:
            # New seam: dependencies come from RunContext.
            self.backend = None
            self.agent_router = ctx.target
            if isinstance(config, AttackConfig):
                # Keep a plain dict view for code that still reads self.config.
                self.config: Dict[str, Any] = config.model_dump()
            elif isinstance(config, dict):
                self.config = config
            else:
                raise ValueError(
                    f"config must be AttackConfig or dict, got {type(config)}"
                )
            self.run_id = ctx.run_id
            self.run_dir = str(ctx.workspace.root)
        else:
            # Legacy path used by techniques / orchestrator today.
            # Orchestrator passes ``client=``; techniques pass it positionally.
            if client is not None and ctx_or_client is not None:
                raise TypeError("Pass client positionally or as client=, not both")
            resolved_client = client if client is not None else ctx_or_client
            self.backend = resolved_client
            self.agent_router = agent_router
            if isinstance(config, AttackConfig):
                self.config = config.model_dump()
            elif isinstance(config, dict):
                self.config = config
            else:
                raise ValueError(
                    f"config must be AttackConfig or dict, got {type(config)}"
                )
            self.run_id = self.config.get("_run_id") or self.config.get("run_id")
            self.run_dir = self.config.get("output_dir", "./logs/runs")

        self.tracker: Optional[StepTracker] = None
        self.coordinator: Optional[TrackingCoordinator] = None

        if not hasattr(self, "logger"):
            self.logger = get_logger(__name__)

        self._validate_config()
        self._setup()

    @staticmethod
    def _goal_texts(
        goals: Optional[Sequence[Union[Goal, str]]] = None,
    ) -> List[str]:
        """Normalize ``Goal`` / string goals to plain text strings."""
        out: List[str] = []
        for goal in goals or []:
            if isinstance(goal, Goal):
                out.append(goal.text)
            else:
                out.append(str(goal))
        return out

    def _wire_workspace_cache(self, cache_key: str = "flowchart") -> None:
        """Expose ``ctx.workspace`` cache paths on the config dict for steps."""
        if self.ctx is None:
            return
        cache_path = self.ctx.workspace.path("cache", cache_key)
        cache_path.mkdir(parents=True, exist_ok=True)
        self.config["_workspace_cache_dir"] = str(cache_path)

    def _validate_config(self):
        """Validate configuration.

        Legacy dict configs still require ``output_dir``. Typed
        :class:`AttackConfig` instances do not — output lives on
        :class:`~hackagent.orchestrator.run_spec.RunSpec` / the workspace.
        """
        if self.attack_config is not None and self.ctx is not None:
            return
        if not isinstance(self.config, dict):
            raise ValueError(f"config must be a dict, got {type(self.config)}")
        if "output_dir" not in self.config:
            raise ValueError("Configuration missing required key: 'output_dir'")

    def _setup(self):
        """Hook for subclass initialization. Does not configure logging."""

    @classmethod
    def get_effective_model_roles(
        cls,
        attack_config: Dict[str, Any],
        *,
        goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Return attack-owned preflight model roles via ``AttackConfig.roles()``.

        Prefer a technique ``config_model.roles()``. Fall back to
        :func:`roles_from_paths` using ``attack_type``. Returning ``None``
        is reserved for "no opinion" and should be rare after Phase 4.
        """
        _ = goal_labels_by_index
        config_model = getattr(cls, "config_model", None)
        if config_model is not None:
            # Prefer dict introspection so pydantic defaults do not invent
            # roles the caller never set (preflight must match the raw config).
            mapper = getattr(config_model, "roles_from_mapping", None)
            if callable(mapper):
                try:
                    return mapper(attack_config)
                except Exception:
                    pass
            if isinstance(attack_config, config_model) and callable(
                getattr(attack_config, "roles", None)
            ):
                try:
                    return attack_config.roles()
                except Exception:
                    pass

        attack_type = ""
        if isinstance(attack_config, dict):
            attack_type = str(attack_config.get("attack_type") or "")
        if attack_type:
            return roles_from_paths(attack_type, attack_config)
        return None

    def _setup_logging(self):
        """Deprecated no-op. Logging is owned by interfaces, not BaseAttack."""
        if not hasattr(self, "logger"):
            self.logger = get_logger(__name__)

    def _prepare_input_sample(self, data: Any) -> Any:
        """
        Prepare input sample for tracking (limit size, sanitize values).

        Takes first 5 items from lists and replaces inf with None for JSON compatibility.
        """
        if data is None:
            return None

        if isinstance(data, list):
            # Sample first 5 items
            sample = data[:5] if len(data) > 5 else data

            # Clean items for JSON serialization
            result = []
            for item in sample:
                if isinstance(item, dict):
                    clean_item = {}
                    for k, v in item.items():
                        if isinstance(v, float) and (
                            v == float("inf") or v == float("-inf")
                        ):
                            clean_item[k] = None
                        else:
                            clean_item[k] = v
                    result.append(clean_item)
                else:
                    result.append(item)
            return result

        return None

    def _initialize_coordinator(
        self,
        attack_type: str,
        goals: Optional[List[str]] = None,
        initial_metadata: Optional[Dict[str, Any]] = None,
    ) -> TrackingCoordinator:
        """
        Initialize unified tracking coordinator.

        Creates a TrackingCoordinator that manages both StepTracker
        (pipeline-level) and Tracker (per-goal) in a single call.
        Also sets ``self.tracker`` for backward compatibility.

        When *goals* is ``None``, the coordinator is created without
        initialising goal Results.  Call ``coordinator.initialize_goals()``
        or ``coordinator.initialize_goals_from_pipeline_data()`` later to
        defer result creation until the surviving goals are known.

        Args:
            attack_type: Attack identifier (e.g., "advprefix", "pair")
            goals: Optional list of goals. Pass ``None`` to defer goal
                   result creation until after the Generation step.
            initial_metadata: Optional metadata for each goal result

        Returns:
            Initialized TrackingCoordinator
        """
        run_id = self.config.get("_run_id") or self.run_id
        backend = self.config.get("_backend") or self.backend

        # Optional per-goal metadata injected by the orchestrator when dataset
        # providers expose extra fields (e.g., AgentHazard/AgentHarm metadata).
        goal_metadata_by_index = self.config.get("_goal_extra_fields_by_index")
        goal_metadata_by_goal = self.config.get("_goal_extra_fields_by_goal")
        if (
            isinstance(goal_metadata_by_index, dict)
            and goal_metadata_by_index
            or isinstance(goal_metadata_by_goal, dict)
            and goal_metadata_by_goal
        ):
            merged_initial_metadata = dict(initial_metadata or {})
            if isinstance(goal_metadata_by_index, dict) and goal_metadata_by_index:
                merged_initial_metadata["_goal_metadata_by_index"] = (
                    goal_metadata_by_index
                )
            if isinstance(goal_metadata_by_goal, dict) and goal_metadata_by_goal:
                merged_initial_metadata["_goal_metadata_by_goal"] = (
                    goal_metadata_by_goal
                )
            initial_metadata = merged_initial_metadata

        raw_run_start_time = self.config.get("_global_run_start_time")
        run_start_time: Optional[float]
        try:
            run_start_time = (
                float(raw_run_start_time) if raw_run_start_time is not None else None
            )
        except (TypeError, ValueError):
            run_start_time = None
        raw_goal_index_start = self.config.get("_goal_index_offset", 0)
        try:
            goal_index_start = int(raw_goal_index_start)
        except (TypeError, ValueError):
            goal_index_start = 0

        coordinator = TrackingCoordinator.create(
            backend=backend,
            run_id=run_id,
            logger=self.logger,
            attack_type=attack_type,
            category_classifier_config=self.config.get("category_classifier"),
            preclassified_goal_labels_by_index=self.config.get("_goal_labels_by_index"),
            disable_goal_category_classifier=bool(
                self.config.get("_disable_goal_category_classifier")
            ),
            goals=goals,
            initial_metadata=initial_metadata,
            goal_index_start=goal_index_start,
            run_start_time=run_start_time,
            event_bus=self.config.get("_tui_event_bus"),
        )

        # Backward-compat: expose step_tracker as self.tracker
        self.tracker = coordinator.step_tracker
        self.coordinator = coordinator

        return coordinator

    def _normalize_step(self, step_info: Union[Step, Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize a typed :class:`Step` or legacy dict into a dict view."""
        if isinstance(step_info, Step):
            return {
                "name": step_info.name,
                "function": step_info.fn,
                "step_type_enum": step_info.kind,
                "config_keys": list(step_info.config_keys),
                "input_data_arg_name": step_info.input_arg,
                "required_args": ["logger", "config"],
            }
        return step_info

    def _build_step_args(
        self,
        step_info: Union[Step, Dict[str, Any]],
        step_config: Dict,
        input_data: Any,
    ) -> Dict:
        """
        Build arguments dict for a pipeline step function.

        Override this in subclasses if you need custom argument handling.

        Args:
            step_info: Pipeline step configuration (:class:`Step` or dict)
            step_config: Step-specific config values
            input_data: Input data for the step

        Returns:
            Dictionary of arguments to pass to step function
        """
        step_info = self._normalize_step(step_info)
        args = {"config": step_config}

        # Add required arguments based on step definition
        required_args = step_info.get("required_args", [])

        if "logger" in required_args:
            args["logger"] = self.logger
        if "client" in required_args:
            args["client"] = self.backend
        if "agent_router" in required_args:
            args["agent_router"] = self.agent_router

        # Add input data with the correct parameter name
        input_arg_name = step_info.get("input_data_arg_name", "input_data")
        args[input_arg_name] = input_data

        return args

    def _execute_pipeline(
        self,
        pipeline_steps: List[Dict],
        initial_input: Any,
        start_step: int = 0,
        end_step: Optional[int] = None,
    ) -> Any:
        """
        Execute a pipeline of steps with tracking.

        Args:
            pipeline_steps: List of step configurations
            initial_input: Initial input data (usually goals)
            start_step: Step index to start from (0-based)
            end_step: Step index to stop before (exclusive, 0-based).
                      Defaults to ``len(pipeline_steps)`` (run all remaining).

        Returns:
            Output from final pipeline step
        """
        current_output = initial_input
        _end = end_step if end_step is not None else len(pipeline_steps)

        for i in range(start_step, _end):
            step_info = self._normalize_step(pipeline_steps[i])
            step_name = step_info["name"]
            step_type = step_info["step_type_enum"]

            # Prepare tracking data
            input_sample = self._prepare_input_sample(current_output)
            step_config = {
                k: self.config[k]
                for k in step_info.get("config_keys", [])
                if k in self.config
            }

            # Calculate and log progress (50-90% range for pipeline)
            progress = int(50 + (i / len(pipeline_steps)) * 40)
            self.logger.info(f"━━━ Progress: {progress}% ━━━")

            # Execute step with tracking (tracker) or ctx.events when present.
            def _run_step() -> Any:
                nonlocal current_output
                if "function" not in step_info:
                    self.logger.warning(
                        f"No function defined for {step_name}. Skipping."
                    )
                    return None
                step_function = step_info["function"]
                step_args = self._build_step_args(
                    step_info, step_config, current_output
                )
                return step_function(**step_args)

            if self.tracker is not None:
                with self.tracker.track_step(
                    step_name, step_type, input_sample, step_config
                ):
                    result = _run_step()
                    if result is None and "function" not in step_info:
                        continue
                    current_output = result
                    if current_output is None:
                        self.tracker.add_step_metadata("output_type", "None")
                        self.tracker.add_step_metadata("warning", "Step returned None")
                    elif isinstance(current_output, list):
                        item_count = len(current_output)
                        self.tracker.add_step_metadata("output_items", item_count)
                        if item_count == 0:
                            self.tracker.add_step_metadata(
                                "warning", "Empty list returned"
                            )
                    else:
                        self.tracker.add_step_metadata(
                            "output_type", type(current_output).__name__
                        )
            elif self.ctx is not None:
                with self.ctx.events.step(step_name, step_type):
                    result = _run_step()
                    if result is None and "function" not in step_info:
                        continue
                    current_output = result
                    self.ctx.events.progress(
                        (i + 1) / max(len(pipeline_steps), 1),
                        step_name,
                    )
            else:
                result = _run_step()
                if result is None and "function" not in step_info:
                    continue
                current_output = result

            self.logger.info(f"✅ Completed: {step_name}")

        return current_output

    @abc.abstractmethod
    def _get_pipeline_steps(self) -> List[Dict]:
        """
        Define the attack pipeline configuration.

        ``_execute_pipeline`` accepts a typed :class:`~hackagent.attacks.ports.Step`
        or a legacy dict. Dict steps contain:
        - name: Human-readable step name
        - function: Callable to execute
        - step_type_enum: Type for tracking (GENERATION, EXECUTION, EVALUATION)
        - config_keys: List of config keys needed by this step
        - input_data_arg_name: Parameter name for input data
        - required_args: List of required arguments (logger, client, agent_router, etc.)

        A ``Step`` maps ``name``, ``kind`` → ``step_type_enum``, ``fn`` →
        ``function``, ``config_keys``, and ``input_arg`` → ``input_data_arg_name``.

        Example:
            return [
                {
                    "name": "Generation: Generate prompts",
                    "function": generation.execute,
                    "step_type_enum": "GENERATION",
                    "config_keys": ["batch_size", "temperature"],
                    "input_data_arg_name": "goals",
                    "required_args": ["logger", "agent_router", "config"],
                },
                {
                    "name": "Evaluation: Evaluate responses",
                    "function": evaluation.execute,
                    "step_type_enum": "EVALUATION",
                    "config_keys": ["objective"],
                    "input_data_arg_name": "input_data",
                    "required_args": ["logger", "config"],
                },
            ]
        """
        pass

    @abc.abstractmethod
    def run(
        self,
        goals: Optional[Sequence[Union[Goal, str]]] = None,
        **kwargs: Any,
    ) -> List[AttackResult]:
        """
        Execute the attack technique against *goals*.

        Phase 4 signature is ``run(goals)``. Legacy ``**kwargs`` (including
        passing goals as a kwarg) remains until Phase 5 migrates callers.

        This method should:
        1. Initialize tracking with self._initialize_coordinator()
        2. Define pipeline with self._get_pipeline_steps() (dict or :class:`Step`)
        3. Execute pipeline with self._execute_pipeline()
        4. Finalize with coordinator.finalize_all_goals() and coordinator.finalize_pipeline()
        5. Return results as ``list[AttackResult]`` (with optional ``verdict``)

        Args:
            goals: Goals to attack (``Goal`` or raw strings).
            **kwargs: Technique-specific parameters (legacy).

        Returns:
            A list of :class:`~hackagent.attacks.types.AttackResult` instances.
        """
        raise NotImplementedError
