# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Goal-based result tracking for attack techniques.

This module provides the main Tracker class which creates one Result per
goal/datapoint and accumulates traces for each interaction during the attack.
This addresses the issue of having too many Results (one per LLM call) with
only 1-2 traces each.

Architecture:
    Attack → Tracker → Result per goal → Multiple Traces per Result

Each attack creates one Result per goal/datapoint via Tracker,
then accumulates traces for each interaction during the attack.

For step-level tracking (pipeline steps like "Generation", "Evaluation"),
use the StepTracker class from step.py instead.
"""

import logging
from hackagent.logger import get_logger
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from hackagent.api.result import result_partial_update, result_trace_create
from hackagent.api.run import run_result_create
from hackagent.api.models import (
    EvaluationStatusEnum,
    PatchedResultRequest,
    ResultRequest,
    StepTypeEnum,
    TraceRequest,
)

from .utils import deep_clean, sanitize_for_json


@dataclass
class Context:
    """Context for tracking a single goal's attack execution."""

    goal: str
    goal_index: int
    result_id: Optional[str] = None
    sequence_counter: int = 0
    traces: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_finalized: bool = False

    def increment_sequence(self) -> int:
        """Atomically increment and return the next sequence number."""
        self.sequence_counter += 1
        return self.sequence_counter


class Tracker:
    """
    Tracks attack execution on a per-goal basis.

    Creates one Result per goal, with multiple Traces capturing:
    - Attack attempts (prompts sent, responses received)
    - Intermediate steps (judge evaluations, refinements)
    - Final evaluation status

    This provides better organization of results where each Result represents
    a complete attack attempt on a single goal/datapoint.

    Attributes:
        client: Authenticated client for API calls
        run_id: Server-side run record ID
        logger: Logger instance

    Example:
        >>> tracker = Tracker(client=client, run_id=run_id)
        >>>
        >>> for goal in goals:
        ...     # Create result for this goal
        ...     goal_ctx = tracker.create_goal_result(goal, goal_index=i)
        ...
        ...     # Add traces for each attack attempt
        ...     for iteration in range(n_iterations):
        ...         response = query_target(prompt)
        ...         tracker.add_interaction_trace(
        ...             goal_ctx,
        ...             request={"prompt": prompt},
        ...             response={"content": response},
        ...             step_name="Attack Attempt"
        ...         )
        ...
        ...     # Finalize with evaluation
        ...     tracker.finalize_goal(
        ...         goal_ctx,
        ...         success=is_success,
        ...         evaluation_notes="Attack succeeded with score 10/10"
        ...     )
    """

    def __init__(
        self,
        client: Any,
        run_id: str,
        logger: Optional[logging.Logger] = None,
        attack_type: Optional[str] = None,
    ):
        """
        Initialize tracker.

        Args:
            client: Authenticated client for API calls
            run_id: Server-side run record ID
            logger: Optional logger instance
            attack_type: Optional attack type identifier for metadata
        """
        self.client = client
        self.run_id = run_id
        self.logger = logger or get_logger(__name__)
        self.attack_type = attack_type

        # Track all goal contexts for batch operations
        self._goal_contexts: Dict[int, Context] = {}

    @property
    def is_enabled(self) -> bool:
        """Check if tracking is enabled (has client and run_id)."""
        return self.client is not None and self.run_id is not None

    def _get_run_uuid(self) -> Optional[UUID]:
        """Get run_id as UUID."""
        if self.run_id:
            try:
                return UUID(self.run_id)
            except (ValueError, AttributeError):
                self.logger.warning(f"Invalid UUID format for run_id: {self.run_id}")
        return None

    def create_goal_result(
        self,
        goal: str,
        goal_index: int,
        initial_metadata: Optional[Dict[str, Any]] = None,
    ) -> Context:
        """
        Create a Result record for a goal and return its tracking context.

        Args:
            goal: The goal/datapoint text
            goal_index: Index of this goal in the batch
            initial_metadata: Optional initial metadata to store

        Returns:
            Context for tracking this goal's attack execution
        """
        ctx = Context(
            goal=goal,
            goal_index=goal_index,
            metadata=initial_metadata or {},
        )

        if not self.is_enabled:
            self.logger.debug(f"Tracking disabled - goal {goal_index} won't be tracked")
            self._goal_contexts[goal_index] = ctx
            return ctx

        try:
            run_uuid = self._get_run_uuid()
            if not run_uuid:
                self._goal_contexts[goal_index] = ctx
                return ctx

            # Create result with goal information
            result_request = ResultRequest(
                run=run_uuid,
                request_payload={
                    "goal": goal,
                    "goal_index": goal_index,
                    "attack_type": self.attack_type,
                },
                evaluation_status=EvaluationStatusEnum.NOT_EVALUATED,
                agent_specific_data={
                    "goal": goal,
                    "goal_index": goal_index,
                    **(initial_metadata or {}),
                },
            )

            response = run_result_create.sync_detailed(
                client=self.client,
                id=run_uuid,
                body=result_request,
            )

            if response.status_code == 201:
                result_id = self._extract_id(response)
                if result_id:
                    ctx.result_id = result_id
                    self.logger.info(
                        f"Created result for goal {goal_index}: {result_id}"
                    )

                    # Add initial trace with goal info
                    self._add_trace(
                        ctx,
                        step_name="Goal Setup",
                        step_type=StepTypeEnum.OTHER,
                        content={
                            "goal": goal,
                            "goal_index": goal_index,
                            "attack_type": self.attack_type,
                        },
                    )
            else:
                self.logger.warning(
                    f"Failed to create result for goal {goal_index}: "
                    f"status={response.status_code}"
                )

        except Exception as e:
            self.logger.error(
                f"Exception creating result for goal {goal_index}: {e}", exc_info=True
            )

        self._goal_contexts[goal_index] = ctx
        return ctx

    def add_interaction_trace(
        self,
        ctx: Context,
        request: Dict[str, Any],
        response: Any,
        step_name: str = "Agent Interaction",
        step_type: StepTypeEnum = StepTypeEnum.OTHER,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a trace for an agent interaction (request/response pair).

        Args:
            ctx: Context from create_goal_result
            request: Request data sent to the agent
            response: Response received from the agent
            step_name: Human-readable step name
            step_type: Type of step for categorization
            metadata: Optional additional metadata
        """
        # Extract response content
        response_content = self._extract_response_content(response)

        content = {
            "step_name": step_name,
            "request": sanitize_for_json(request),
            "response": response_content,
        }

        if metadata:
            content["metadata"] = metadata

        self._add_trace(ctx, step_name, step_type, content)

    def add_evaluation_trace(
        self,
        ctx: Context,
        evaluation_result: Any,
        score: Optional[float] = None,
        explanation: Optional[str] = None,
        evaluator_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a trace for an evaluation step.

        Args:
            ctx: Context from create_goal_result
            evaluation_result: Result from the evaluator
            score: Optional numeric score
            explanation: Optional explanation text
            evaluator_name: Name of the evaluator used
            metadata: Optional additional metadata
        """
        content = {
            "step_name": "Evaluation",
            "evaluator": evaluator_name,
            "result": sanitize_for_json(evaluation_result),
        }

        if score is not None:
            content["score"] = score
        if explanation:
            content["explanation"] = explanation
        if metadata:
            content["metadata"] = sanitize_for_json(metadata)

        self._add_trace(ctx, "Evaluation", StepTypeEnum.OTHER, content)

    def add_custom_trace(
        self,
        ctx: Context,
        step_name: str,
        content: Dict[str, Any],
        step_type: StepTypeEnum = StepTypeEnum.OTHER,
    ) -> None:
        """
        Add a custom trace with arbitrary content.

        Args:
            ctx: Context from create_goal_result
            step_name: Human-readable step name
            content: Trace content dictionary
            step_type: Type of step for categorization
        """
        self._add_trace(ctx, step_name, step_type, content)

    def _add_trace(
        self,
        ctx: Context,
        step_name: str,
        step_type: StepTypeEnum,
        content: Dict[str, Any],
    ) -> Optional[str]:
        """
        Internal method to add a trace to a goal's result.

        Args:
            ctx: Context
            step_name: Step name
            step_type: Step type enum
            content: Trace content

        Returns:
            Trace ID if successful, None otherwise
        """

        try:
            content = deep_clean(content)
        except Exception as e:
            self.logger.warning(f"Deep clean failed: {e}")
            content["serialization_error"] = str(e)

        sanitized_content = sanitize_for_json(content)

        # Always track locally
        seq = ctx.increment_sequence()
        trace_record = {
            "sequence": seq,
            "step_name": step_name,
            "step_type": (
                step_type.value if hasattr(step_type, "value") else str(step_type)
            ),
            "content": sanitized_content,
        }
        ctx.traces.append(trace_record)

        # Send to server if enabled and we have a result_id
        if not self.is_enabled or not ctx.result_id:
            return None

        try:
            result_uuid = UUID(ctx.result_id)

            trace_request = TraceRequest(
                sequence=seq,
                step_type=step_type,
                content=sanitized_content,
            )

            response = result_trace_create.sync_detailed(
                client=self.client,
                id=result_uuid,
                body=trace_request,
            )

            if response.status_code == 201:
                trace_id = self._extract_id(response)
                self.logger.debug(
                    f"Created trace {seq} for goal {ctx.goal_index}: {trace_id}"
                )
                return trace_id
            else:
                self.logger.warning(
                    f"Failed to create trace for goal {ctx.goal_index}: "
                    f"status={response.status_code}"
                )

        except Exception as e:
            self.logger.error(
                f"Exception creating trace for goal {ctx.goal_index}: {e}",
                exc_info=True,
            )

        return None

    def finalize_goal(
        self,
        ctx: Context,
        success: bool,
        evaluation_notes: Optional[str] = None,
        final_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Finalize a goal's result with evaluation status.

        Args:
            ctx: Context from create_goal_result
            success: Whether the attack was successful
            evaluation_notes: Optional evaluation notes
            final_metadata: Optional final metadata to merge

        Returns:
            True if update was successful, False otherwise
        """
        if ctx.is_finalized:
            self.logger.warning(f"Goal {ctx.goal_index} already finalized")
            return False

        ctx.is_finalized = True

        # Update local metadata
        if final_metadata:
            ctx.metadata.update(final_metadata)
        ctx.metadata["success"] = success
        ctx.metadata["total_traces"] = len(ctx.traces)

        if not self.is_enabled or not ctx.result_id:
            return False

        try:
            result_uuid = UUID(ctx.result_id)

            # Map success to evaluation status
            if success:
                eval_status = EvaluationStatusEnum.SUCCESSFUL_JAILBREAK
            else:
                eval_status = EvaluationStatusEnum.FAILED_JAILBREAK

            # Backend requires non-null evaluation_notes
            notes = (
                evaluation_notes
                if evaluation_notes
                else (
                    "Goal completed successfully"
                    if success
                    else "Goal evaluation failed"
                )
            )

            result_request = PatchedResultRequest(
                evaluation_status=eval_status,
                evaluation_notes=notes,
                agent_specific_data={
                    **ctx.metadata,
                    "goal": ctx.goal,
                    "goal_index": ctx.goal_index,
                    "total_traces": len(ctx.traces),
                },
            )

            response = result_partial_update.sync_detailed(
                client=self.client,
                id=result_uuid,
                body=result_request,
            )

            if response.status_code < 300:
                self.logger.info(
                    f"Finalized goal {ctx.goal_index} (result {ctx.result_id}): "
                    f"{'SUCCESS' if success else 'FAILED'}"
                )
                return True
            else:
                self.logger.warning(
                    f"Failed to finalize goal {ctx.goal_index}: "
                    f"status={response.status_code}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Exception finalizing goal {ctx.goal_index}: {e}", exc_info=True
            )
            return False

    def get_goal_context(self, goal_index: int) -> Optional[Context]:
        """Get the Context for a specific goal index."""
        return self._goal_contexts.get(goal_index)

    def get_goal_context_by_goal(self, goal: str) -> Optional[Context]:
        """
        Get the Context for a specific goal string.

        Searches all contexts to find one matching the goal text.
        Use this when you have the goal string but not the index.

        Args:
            goal: The goal text to find

        Returns:
            Context if found, None otherwise
        """
        for ctx in self._goal_contexts.values():
            if ctx.goal == goal:
                return ctx
        return None

    def get_result_id(self, goal_index: int) -> Optional[str]:
        """Get the result ID for a specific goal index."""
        ctx = self._goal_contexts.get(goal_index)
        return ctx.result_id if ctx else None

    def get_all_contexts(self) -> Dict[int, Context]:
        """Get all goal contexts."""
        return self._goal_contexts.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all tracked goals."""
        total = len(self._goal_contexts)
        successful = sum(
            1
            for ctx in self._goal_contexts.values()
            if ctx.metadata.get("success", False)
        )
        finalized = sum(1 for ctx in self._goal_contexts.values() if ctx.is_finalized)
        total_traces = sum(len(ctx.traces) for ctx in self._goal_contexts.values())

        return {
            "total_goals": total,
            "successful_attacks": successful,
            "finalized": finalized,
            "total_traces": total_traces,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "avg_traces_per_goal": (total_traces / total) if total > 0 else 0,
        }

    @contextmanager
    def track_goal(
        self,
        goal: str,
        goal_index: int,
        initial_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for tracking a single goal's attack execution.

        Creates result on entry, yields context for adding traces,
        and auto-finalizes on exit (with failure status if exception occurs).

        Args:
            goal: The goal/datapoint text
            goal_index: Index of this goal
            initial_metadata: Optional initial metadata

        Yields:
            Context for adding traces during execution

        Example:
            >>> with tracker.track_goal(goal, i) as ctx:
            ...     response = attack(goal)
            ...     tracker.add_interaction_trace(ctx, request, response)
            ...     # Finalize manually or let context manager handle it
        """
        ctx = self.create_goal_result(goal, goal_index, initial_metadata)

        try:
            yield ctx
        except Exception as e:
            # Finalize with failure on exception
            if not ctx.is_finalized:
                self.finalize_goal(
                    ctx,
                    success=False,
                    evaluation_notes=f"Attack failed with exception: {str(e)[:200]}",
                )
            raise
        finally:
            # Auto-finalize if the caller forgot to call finalize_goal().
            # Using FAILED_JAILBREAK with an explanatory note is safer than
            # leaving the backend result in NOT_EVALUATED indefinitely.
            if not ctx.is_finalized:
                self.logger.warning(
                    f"Goal {goal_index} not explicitly finalized — "
                    "marking as NOT_EVALUATED on backend"
                )
                self.finalize_goal(
                    ctx,
                    success=False,
                    evaluation_notes="Goal exited context manager without explicit finalization",
                )

    def _extract_id(self, response) -> Optional[str]:
        """Extract ID from API response."""
        if response.parsed and hasattr(response.parsed, "id"):
            return str(response.parsed.id)
        return None

    def _extract_response_content(self, response: Any) -> Any:
        """Extract content from various response formats."""
        if response is None:
            return None

        # OpenAI-style response
        if hasattr(response, "choices") and response.choices:
            try:
                return response.choices[0].message.content
            except (AttributeError, IndexError):
                pass

        # Dictionary response
        if isinstance(response, dict):
            return (
                response.get("generated_text")
                or response.get("processed_response")
                or response.get("content")
            )

        # String response
        if isinstance(response, str):
            return response

        # Fallback: convert to string
        return str(response)
