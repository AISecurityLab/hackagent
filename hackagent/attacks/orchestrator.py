# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack orchestration layer.

This module provides the AttackOrchestrator base class that coordinates attack execution
with server-side tracking. The orchestrator acts as a bridge between:
- HackAgent (user API)
- HackAgent backend server (tracking/audit)
- Attack technique implementations (algorithms)

Architecture:
    HackAgent.hack() → AttackOrchestrator.execute() → BaseAttack.run()

The orchestrator handles:
- Server record creation (Attack/Run records)
- Configuration validation and preparation
- Delegation to technique implementations
- HTTP response parsing and error handling

Technique implementations remain pure algorithms, unaware of server integration.
"""

import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from hackagent.logger import get_logger
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx

from hackagent.errors import HackAgentError
from hackagent.server.api.models import StatusEnum

if TYPE_CHECKING:
    from hackagent.agent import HackAgent

logger = get_logger(__name__)


class _BatchContextFilter(logging.Filter):
    """
    Logging filter that prepends ``[Batchindex/total]`` to every log record
    emitted from a goal-batch worker thread.

    It reads the current thread name (set to ``B{idx}/{n}`` by the worker
    before the attack runs) and prefixes the message **only** for non-main
    threads, so sequential runs are unaffected.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        t = threading.current_thread()
        if t.name != "MainThread":
            record.msg = f"[{t.name}] {record.msg}"
        return True


class AttackOrchestrator:
    """
    Base class for attack orchestrators managing server-tracked execution.

    Orchestrators coordinate attack execution by:
    1. Creating Attack record on server for tracking
    2. Creating Run record on server for this execution
    3. Executing attack locally using BaseAttack implementation
    4. Returning results to caller

    Concrete orchestrators only need to specify:
    - attack_type: String identifier (e.g., "advprefix", "pair")
    - attack_impl_class: BaseAttack subclass to instantiate
    - (Optional) Override methods for custom behavior

    Example:
        class AdvPrefix(AttackOrchestrator):
            attack_type = "advprefix"
            attack_impl_class = AdvPrefixAttack

    Attributes:
        hack_agent: HackAgent instance providing context
        client: Authenticated client for API communication
        attack_type: Attack identifier (must be set by subclass)
        attack_impl_class: Implementation class (must be set by subclass)
    """

    attack_type: str = None  # Must be overridden by subclass
    attack_impl_class: type = None  # Must be overridden by subclass

    def __init__(self, hack_agent: "HackAgent"):
        """
        Initialize orchestrator with HackAgent instance.

        Args:
            hack_agent: HackAgent instance providing client and configuration

        Raises:
            ValueError: If attack_type or attack_impl_class not defined
        """
        self.hack_agent = hack_agent
        # keep self.client as legacy attr for subclasses that may reference it directly
        self.client = getattr(hack_agent, "client", None)

        if not self.attack_type:
            raise ValueError(f"{self.__class__.__name__} must define attack_type")
        if not self.attack_impl_class:
            raise ValueError(f"{self.__class__.__name__} must define attack_impl_class")

    def _create_server_attack_record(
        self,
        attack_type: str,
        victim_agent_id: UUID,
        organization_id: UUID,
        attack_config: Dict[str, Any],
    ) -> str:
        """Create Attack record via the storage backend."""
        logger.info(f"Creating {attack_type} Attack record")
        try:
            record = self.hack_agent.backend.create_attack(
                attack_type=attack_type,
                agent_id=victim_agent_id,
                organization=organization_id,
                configuration=attack_config,
            )
            logger.info(f"Attack record created. ID: {record.id}")
            return str(record.id)
        except Exception as e:
            logger.error(
                f"Failed to create {attack_type} Attack record: {e}", exc_info=True
            )
            raise HackAgentError(f"Failed to create Attack record: {e}") from e

    def _create_server_run_record(
        self,
        attack_id: str,
        victim_agent_id: str,
        run_config_override: Optional[Dict[str, Any]],
    ) -> str:
        """Create Run record via the storage backend."""
        logger.info(f"Creating Run record for Attack ID: {attack_id}")
        try:
            record = self.hack_agent.backend.create_run(
                attack_id=UUID(attack_id),
                agent_id=UUID(victim_agent_id),
                run_config=run_config_override or {},
            )
            logger.info(f"Run record created. ID: {record.id}")
            return str(record.id)
        except Exception as e:
            logger.error(f"Failed to create Run record: {e}", exc_info=True)
            raise HackAgentError(f"Failed to create Run record: {e}") from e

    def _prepare_attack_params(self, attack_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters for attack execution.

        Override this method for custom parameter handling.
        Default implementation extracts 'goals' from config, either directly
        as a list or by loading them from a dataset source.

        Args:
            attack_config: Full attack configuration. Can contain either:
                - goals: Direct list of goal strings
                - dataset: Configuration for loading goals from a dataset source

        Returns:
            Parameters to pass to technique's run() method

        Raises:
            ValueError: If neither 'goals' nor 'dataset' is provided, or if format is invalid
        """
        # Check for direct goals first
        goals = attack_config.get("goals")
        dataset_config = attack_config.get("dataset")

        if goals is not None and dataset_config is not None:
            logger.warning(
                "Both 'goals' and 'dataset' provided. Using 'goals' directly."
            )
            dataset_config = None

        if dataset_config is not None:
            # Load goals from dataset source
            goals = self._load_goals_from_dataset(dataset_config)
        elif goals is None:
            raise ValueError(
                f"'{self.attack_type}' requires either 'goals' (list) or 'dataset' (config)"
            )

        if not isinstance(goals, list):
            raise ValueError(f"'goals' must be a list for {self.attack_type}")

        if len(goals) == 0:
            raise ValueError(f"'goals' list is empty for {self.attack_type}")

        logger.info(f"Prepared {len(goals)} goals for {self.attack_type} attack")
        return {"goals": goals}

    def _load_goals_from_dataset(self, dataset_config: Dict[str, Any]) -> list:
        """
        Load goals from a dataset configuration.

        Supports loading from:
        - Pre-configured presets (e.g., "agentharm", "strongreject")
        - HuggingFace datasets
        - Local files (JSON, CSV, JSONL, TXT)

        Args:
            dataset_config: Dataset configuration dictionary with keys:
                - preset (str, optional): Name of a pre-configured preset
                - provider (str, optional): "huggingface" or "file"
                - path (str, optional): Dataset path or file path
                - goal_field (str, optional): Field containing goal text
                - split (str, optional): Dataset split (for HuggingFace)
                - limit (int, optional): Maximum goals to load
                - shuffle (bool, optional): Shuffle before selecting
                - seed (int, optional): Random seed for shuffling

        Returns:
            List of goal strings

        Raises:
            ValueError: If dataset configuration is invalid
            ImportError: If required dependencies are not available
        """
        from hackagent.datasets import load_goals_from_config

        logger.info(f"Loading goals from dataset: {dataset_config}")

        try:
            goals = load_goals_from_config(dataset_config)
            logger.info(f"Loaded {len(goals)} goals from dataset")
            return goals
        except Exception as e:
            logger.error(f"Failed to load goals from dataset: {e}", exc_info=True)
            raise ValueError(f"Failed to load goals from dataset: {e}") from e

    def _get_attack_impl_kwargs(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
        run_id: str,
    ) -> Dict[str, Any]:
        """
        Prepare kwargs for attack implementation instantiation.

        Override this method for special initialization needs
        (e.g., PAIR requires an attacker router).

        Args:
            attack_config: Full attack configuration
            run_config_override: Optional run overrides
            run_id: Server-side run record ID for result tracking

        Returns:
            Kwargs for attack_impl_class constructor
        """
        target_config = getattr(self.hack_agent, "target_config", {}) or {}

        return {
            "config": {
                **target_config,
                **attack_config,  ## Spread full attack config
                **(run_config_override or {}),
                "_run_id": run_id,
                "_client": self.hack_agent.backend,  # backend expected by evaluator/router factory
                "_backend": self.hack_agent.backend,  # StorageBackend for result tracking
            },
            "client": self.hack_agent.backend,  # pass backend as 'client' for BaseAttack compat
            "agent_router": self.hack_agent.router,
        }

    def _execute_local_attack(
        self,
        attack_id: str,
        run_id: str,
        attack_params: Dict[str, Any],
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
    ) -> Any:
        """
        Execute attack locally using technique implementation.

        If ``goal_batch_size`` is present in *attack_config*, goals are split
        into sequential batches of that size.  Within each batch, every goal
        is executed in its own thread (up to ``goal_batch_workers`` threads)
        so goals inside the same batch run in parallel.

        Batches are processed **sequentially** — batch *N+1* starts only
        after all goals in batch *N* have completed.

        When ``goal_batch_size`` is absent, the attack runs as a single call
        to ``run()``.

        Args:
            attack_id: Server-side attack record ID
            run_id: Server-side run record ID
            attack_params: Parameters from _prepare_attack_params()
            attack_config: Full attack configuration
            run_config_override: Optional run overrides

        Returns:
            Attack results (format depends on implementation)
        """
        logger.info(
            f"Executing {self.attack_type} attack (Attack: {attack_id}, Run: {run_id})"
        )

        impl_kwargs = self._get_attack_impl_kwargs(
            attack_config, run_config_override, run_id
        )
        attack_impl = self.attack_impl_class(**impl_kwargs)

        goals = attack_params.get("goals")
        goal_batch_size = attack_config.get("goal_batch_size")
        raw_goal_batch_workers = attack_config.get("goal_batch_workers", 1)
        try:
            goal_batch_workers = max(1, int(raw_goal_batch_workers))
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid goal_batch_workers={raw_goal_batch_workers!r}; defaulting to 1"
            )
            goal_batch_workers = 1

        if goal_batch_size and isinstance(goals, list):
            batches = [
                (i, goals[i : i + goal_batch_size])
                for i in range(0, len(goals), goal_batch_size)
            ]
            n_batches = len(batches)
            logger.info(
                f"Batching {len(goals)} goals into {n_batches} sequential batch(es) "
                f"of up to {goal_batch_size}, "
                f"goal_batch_workers={goal_batch_workers} (parallel goals per batch)"
            )

            all_results: List[Dict[str, Any]] = []
            batch_timings: List[float] = []

            for batch_idx, (batch_start_idx, batch_goals) in enumerate(batches):
                batch_label = f"B{batch_idx + 1}/{n_batches}"
                n_goals_in_batch = len(batch_goals)
                logger.info(f"[{batch_label}] Starting ({n_goals_in_batch} goals)")
                _batch_t0 = time.perf_counter()

                if goal_batch_workers <= 1:
                    # Sequential: pass all goals at once to a single run()
                    attack_impl.config["_goal_index_offset"] = batch_start_idx
                    # This run() call is only a sub-batch within a larger run.
                    # Global run status is finalized once in execute().
                    attack_impl.config["_suppress_run_status_updates"] = True
                    batch_params = {**attack_params, "goals": batch_goals}
                    batch_results = attack_impl.run(**batch_params) or []
                else:
                    # Parallel: one thread per goal inside this batch
                    effective_workers = min(goal_batch_workers, n_goals_in_batch)

                    def _run_single_goal(
                        goal_idx_goal: Tuple[int, str],
                        _batch_label: str = batch_label,
                        _batch_start_idx: int = batch_start_idx,
                    ) -> Tuple[int, List[Dict[str, Any]]]:
                        goal_idx, goal = goal_idx_goal

                        # Label thread for _BatchContextFilter
                        threading.current_thread().name = (
                            f"{_batch_label} G{goal_idx + 1}/{n_goals_in_batch}"
                        )
                        logger.info(f"Processing goal: {goal[:60]}...")

                        # Each goal gets its own attack instance to avoid
                        # shared mutable state across threads.
                        local_impl_kwargs = {
                            **impl_kwargs,
                            "config": {
                                **impl_kwargs["config"],
                                "_goal_index_offset": _batch_start_idx + goal_idx,
                                # Per-goal worker is a sub-run; avoid premature
                                # global run status updates from attack_impl.run().
                                "_suppress_run_status_updates": True,
                            },
                        }
                        local_impl = self.attack_impl_class(**local_impl_kwargs)
                        goal_params = {**attack_params, "goals": [goal]}
                        goal_results = local_impl.run(**goal_params) or []

                        logger.info(f"Goal done ({len(goal_results)} results)")
                        return goal_idx, goal_results

                    per_goal_results: Dict[int, List[Dict[str, Any]]] = {}

                    # Install a LogRecordFactory so *all* log records,
                    # regardless of logger/handler routing, get the batch
                    # label injected directly into the message.
                    _previous_factory = logging.getLogRecordFactory()

                    def _batch_record_factory(*args, **kwargs):
                        record = _previous_factory(*args, **kwargs)
                        tname = threading.current_thread().name
                        if tname != "MainThread":
                            record.msg = f"[{tname}] {record.msg}"
                        return record

                    logging.setLogRecordFactory(_batch_record_factory)
                    try:
                        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
                            for goal_idx, goal_results in pool.map(
                                _run_single_goal, enumerate(batch_goals)
                            ):
                                per_goal_results[goal_idx] = goal_results
                    finally:
                        logging.setLogRecordFactory(_previous_factory)

                    # Reassemble in original goal order
                    batch_results = []
                    for goal_idx in range(n_goals_in_batch):
                        batch_results.extend(per_goal_results.get(goal_idx, []))

                _batch_elapsed = round(time.perf_counter() - _batch_t0, 3)
                batch_timings.append(_batch_elapsed)
                logger.info(
                    f"[{batch_label}] Completed in {_batch_elapsed:.1f}s "
                    f"({len(batch_results)} results)"
                )
                all_results.extend(batch_results)

            # Log goal-batch latency summary
            if batch_timings:
                avg_bt = sum(batch_timings) / len(batch_timings)
                logger.info(
                    f"Goal-batch latency: avg={avg_bt:.1f}s "
                    f"[{min(batch_timings):.1f}–{max(batch_timings):.1f}s], "
                    f"total={sum(batch_timings):.1f}s"
                )

            logger.info(
                f"{self.attack_type} attack completed "
                f"({len(all_results)} total results from {n_batches} batches)"
            )
            return all_results

        results = attack_impl.run(**attack_params)
        logger.info(f"{self.attack_type} attack completed")
        return results

    def execute(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
        fail_on_run_error: bool,
        max_wait_time_seconds: Optional[int] = None,
        poll_interval_seconds: Optional[int] = None,
        _tui_app: Optional[Any] = None,
        _tui_log_callback: Optional[Any] = None,
    ) -> Any:
        """
        Execute attack with server tracking.

        Standard workflow:
        1. Validate and extract attack parameters
        2. Create Attack record on server
        3. Create Run record on server
        4. Execute attack locally via BaseAttack implementation
        5. Return results

        Args:
            attack_config: Attack configuration dictionary
            run_config_override: Optional run configuration overrides
            fail_on_run_error: Whether to raise on errors
            max_wait_time_seconds: Unused for local execution
            poll_interval_seconds: Unused for local execution
            _tui_app: Optional TUI app for logging
            _tui_log_callback: Optional TUI log callback

        Returns:
            Attack results from local execution

        Raises:
            ValueError: If configuration is invalid
            HackAgentError: If server record creation fails
        """
        # 1. Validate parameters
        attack_params = self._prepare_attack_params(attack_config)

        # 2. Create Attack record
        victim_agent_id = self.hack_agent.router.backend_agent.id
        organization_id = self.hack_agent.router.organization_id

        attack_id = self._create_server_attack_record(
            attack_type=self.attack_type,
            victim_agent_id=victim_agent_id,
            organization_id=organization_id,
            attack_config=attack_config,
        )

        # 3. Create Run record
        run_id = self._create_server_run_record(
            attack_id=attack_id,
            victim_agent_id=str(victim_agent_id),
            run_config_override=run_config_override,
        )

        # 4. Update run status to RUNNING
        try:
            logger.info(f"Updating run {run_id} status to RUNNING")
            self.hack_agent.backend.update_run(
                UUID(run_id),
                status=StatusEnum.RUNNING.value,
            )
        except Exception as e:
            logger.warning(f"Failed to update run status to RUNNING: {e}")

        # 5. Execute locally
        try:
            _total_t0 = time.perf_counter()
            results = self._execute_local_attack(
                attack_id=attack_id,
                run_id=run_id,
                attack_params=attack_params,
                attack_config=attack_config,
                run_config_override=run_config_override,
            )
            _total_elapsed = round(time.perf_counter() - _total_t0, 3)
            logger.info(f"Total run time: {_total_elapsed:.1f}s")

            # 6. Update run status to COMPLETED
            try:
                logger.info(f"Updating run {run_id} status to COMPLETED")
                self.hack_agent.backend.update_run(
                    UUID(run_id),
                    status=StatusEnum.COMPLETED.value,
                )
            except Exception as e:
                logger.warning(f"Failed to update run status to COMPLETED: {e}")

            return results

        except Exception as e:
            # Update run status to FAILED on error
            try:
                logger.error(f"Attack execution failed: {e}")
                self.hack_agent.backend.update_run(
                    UUID(run_id),
                    status=StatusEnum.FAILED.value,
                    run_notes=f"Execution failed: {str(e)}",
                )
            except Exception as update_error:
                logger.warning(f"Failed to update run status to FAILED: {update_error}")
            raise

    # ========================================================================
    # HTTP Response Helpers
    # ========================================================================

    def _decode_response(self, response: httpx.Response) -> str:
        """Decode response content to UTF-8 string."""
        return (
            response.content.decode("utf-8", errors="replace")
            if response.content
            else "N/A"
        )

    def _parse_json(
        self,
        response: httpx.Response,
        decoded_content: str,
        context: str,
    ) -> Optional[Dict[str, Any]]:
        """Parse JSON from response with fallback to pre-parsed attributes."""
        parsed_data: Optional[Dict[str, Any]] = None

        if response.content:
            try:
                parsed_data = json.loads(decoded_content)
            except json.JSONDecodeError as jde:
                if response.status_code == 201:
                    logger.error(f"Failed to parse JSON for {context} (201): {jde}")
                    raise HackAgentError(
                        f"Failed to parse 201 response for {context}"
                    ) from jde
                logger.warning(
                    f"Could not parse JSON for {context} (status {response.status_code})",
                    exc_info=False,
                )

        # Fallback to pre-parsed attributes
        if not parsed_data and hasattr(response, "parsed") and response.parsed:
            if hasattr(response.parsed, "additional_properties") and isinstance(
                response.parsed.additional_properties, dict
            ):
                parsed_data = response.parsed.additional_properties
            elif isinstance(response.parsed, dict):
                parsed_data = response.parsed

        return parsed_data

    def _parse_response(
        self,
        response: httpx.Response,
        decoded_content: str,
        context: str,
    ) -> Dict[str, Any]:
        """Parse and validate response data."""
        parsed_data = self._parse_json(response, decoded_content, context)

        if response.status_code == 201:
            if not parsed_data:
                logger.error(f"201 response for {context} but no parseable data")
                raise HackAgentError(f"201 for {context} but no parseable data")
        elif response.status_code >= 300:
            err = f"Failed {context}. Status: {response.status_code}, Body: {decoded_content}"
            logger.error(err)
            raise HackAgentError(err)
        else:
            logger.warning(f"Unexpected status {response.status_code} for {context}")
            if not parsed_data:
                err = f"No parseable data for {context} (status {response.status_code})"
                logger.error(err)
                raise HackAgentError(err)

        if not parsed_data:
            err = f"Failed to parse data for {context} (status {response.status_code})"
            logger.error(err)
            raise HackAgentError(err)

        return parsed_data

    def _extract_ids_from_data(
        self,
        parsed_data: Dict[str, Any],
        context: str,
        original_content: str,
    ) -> Tuple[str, Optional[str]]:
        """Extract attack_id and optional run_id from parsed data."""
        raw_attack_id = parsed_data.get("id")
        attack_id = str(raw_attack_id) if raw_attack_id is not None else None

        if not attack_id:
            err = f"Could not extract attack_id from {context}. Data: {parsed_data}"
            logger.error(err)
            raise HackAgentError(err)

        raw_run_id = parsed_data.get("associated_run_id")
        run_id = str(raw_run_id) if raw_run_id is not None else None

        logger.info(f"Extracted Attack ID: {attack_id}, Run ID: {run_id or 'N/A'}")
        return attack_id, run_id

    def _extract_ids_from_response(
        self, response: httpx.Response, context: str = "attack"
    ) -> Tuple[str, Optional[str]]:
        """Main entry point for extracting IDs from API response."""
        logger.debug(f"Extracting IDs for '{context}' (status: {response.status_code})")
        decoded_content = self._decode_response(response)
        parsed_data = self._parse_response(response, decoded_content, context)
        return self._extract_ids_from_data(parsed_data, context, decoded_content)
