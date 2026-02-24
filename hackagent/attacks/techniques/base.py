# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base class for attack technique implementations.

This module provides BaseAttack, the abstract base class for all attack
technique implementations. Techniques focus purely on attack algorithms
and evaluation, without knowledge of server integration.

Architecture:
    HackAgent → AttackOrchestrator → BaseAttack → Pipeline stages

Attack techniques are organized in:
    techniques/advprefix/attack.py    - AdvPrefixAttack
    techniques/baseline/attack.py - BaselineAttack
    techniques/pair/attack.py         - PAIRAttack

Each technique:
- Extends BaseAttack
- Implements run() method with attack logic
- Uses objectives from attacks/objectives/ for evaluation
- Returns results in appropriate format (DataFrame, dict, etc.)

The orchestration layer (attacks/orchestrator.py) handles server integration,
allowing techniques to focus solely on attack algorithms.
"""

import abc
import logging
from typing import Any, Dict, List, Optional

from hackagent.router.tracking import StepTracker, TrackingCoordinator

logger = logging.getLogger(__name__)


class BaseAttack(abc.ABC):
    """
    Abstract base class for attack technique implementations.

    Provides common infrastructure that all attacks need:
    - Configuration management (merging with defaults)
    - Logging setup
    - Run directory management
    - Tracking initialization
    - Parent result creation
    - Pipeline execution framework

    Subclasses only need to:
    1. Define DEFAULT_CONFIG in their module
    2. Implement _validate_config() for specific validation
    3. Implement _get_pipeline_steps() to define their attack pipeline
    4. Implement _build_step_args() if custom argument handling needed

    Attributes:
        config: Merged configuration dictionary
        client: Authenticated HackAgent client
        agent_router: Target agent router for queries
        logger: Logger instance for this attack
        run_id: Unique run identifier
        run_dir: Output directory for this run
        coordinator: TrackingCoordinator for unified tracking
        tracker: StepTracker for execution tracking (alias for coordinator.step_tracker)
    """

    def __init__(
        self,
        config: Dict[str, Any],
        client: Any = None,
        agent_router: Any = None,
        **kwargs,
    ):
        """
        Initialize attack implementation with common setup.

        Args:
            config: Attack configuration (will be merged with DEFAULT_CONFIG)
            client: Authenticated HackAgent client
            agent_router: Target agent router
            **kwargs: Additional technique-specific parameters
        """
        # Store additional kwargs for subclass access
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Store core dependencies
        self.client = client
        self.agent_router = agent_router

        # Config will be set by subclass before calling super().__init__()
        # This allows subclass to merge with its own defaults first
        self.config = config

        # Run setup - check both "run_id" and "_run_id" for backwards compatibility
        # The orchestrator passes "_run_id" while direct usage may use "run_id"
        self.run_id = self.config.get("_run_id") or self.config.get("run_id")
        self.run_dir = self.config.get("output_dir", "./logs/runs")

        # Tracking
        self.tracker: Optional[StepTracker] = None
        self.coordinator: Optional[TrackingCoordinator] = None

        # Validate and setup
        self._validate_config()
        self._setup()

    def _validate_config(self):
        """
        Validate configuration dictionary.

        Base validation checks for dict type and required common keys.
        Subclasses should override and call super()._validate_config() first,
        then add their own validation.
        """
        if not isinstance(self.config, dict):
            raise TypeError(f"config must be a dict, got {type(self.config)}")

        # Check for common required keys
        if "output_dir" not in self.config:
            raise ValueError("Configuration missing required key: 'output_dir'")

    def _setup(self):
        """
        Setup logging and other initialization.

        Subclasses can override to add custom setup, but should call super()._setup()
        to get standard logging configuration.
        """
        self._setup_logging()

    def _setup_logging(self):
        """
        Configure logging to console for this attack instance.

        Creates a hierarchical logger (e.g., hackagent.attacks.advprefix)
        that inherits TUI handlers if available.
        """
        # Logger should be set by subclass with appropriate name
        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(__name__)

        self.logger.propagate = False
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

        # Console handler
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            ch = logging.StreamHandler()
            ch.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self.logger.addHandler(ch)

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
        client = self.config.get("_client") or self.client

        coordinator = TrackingCoordinator.create(
            client=client,
            run_id=run_id,
            logger=self.logger,
            attack_type=attack_type,
            goals=goals,
            initial_metadata=initial_metadata,
        )

        # Backward-compat: expose step_tracker as self.tracker
        self.tracker = coordinator.step_tracker
        self.coordinator = coordinator

        return coordinator

    def _build_step_args(
        self, step_info: Dict, step_config: Dict, input_data: Any
    ) -> Dict:
        """
        Build arguments dict for a pipeline step function.

        Override this in subclasses if you need custom argument handling.

        Args:
            step_info: Pipeline step configuration
            step_config: Step-specific config values
            input_data: Input data for the step

        Returns:
            Dictionary of arguments to pass to step function
        """
        args = {"config": step_config}

        # Add required arguments based on step definition
        required_args = step_info.get("required_args", [])

        if "logger" in required_args:
            args["logger"] = self.logger
        if "client" in required_args:
            args["client"] = self.client
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
            step_info = pipeline_steps[i]
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

            # Execute step with tracking
            with self.tracker.track_step(
                step_name, step_type, input_sample, step_config
            ):
                if "function" in step_info:
                    step_function = step_info["function"]
                    step_args = self._build_step_args(
                        step_info, step_config, current_output
                    )
                    current_output = step_function(**step_args)

                    # Track output metrics
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
                else:
                    self.logger.warning(
                        f"No function defined for {step_name}. Skipping."
                    )
                    continue

            self.logger.info(f"✅ Completed: {step_name}")

        return current_output

    @abc.abstractmethod
    def _get_pipeline_steps(self) -> List[Dict]:
        """
        Define the attack pipeline configuration.

        Returns a list of step configurations, each containing:
        - name: Human-readable step name
        - function: Callable to execute
        - step_type_enum: Type for tracking (GENERATION, EXECUTION, EVALUATION)
        - config_keys: List of config keys needed by this step
        - input_data_arg_name: Parameter name for input data
        - required_args: List of required arguments (logger, client, agent_router, etc.)

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
    def run(self, **kwargs) -> Any:
        """
        Execute the attack technique.

        This method should:
        1. Initialize tracking with self._initialize_coordinator()
        2. Define pipeline with self._get_pipeline_steps()
        3. Execute pipeline with self._execute_pipeline()
        4. Finalize with coordinator.finalize_all_goals() and coordinator.finalize_pipeline()
        5. Return results

        Args:
            **kwargs: Technique-specific parameters (e.g., goals, prompts)

        Returns:
            Attack results (format varies by implementation)
        """
        pass
