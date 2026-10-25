# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Persist campaign runs to the HackAgent store.

One :class:`RunTracker` owns the store records of one attack run: the
attack and run rows when it starts, a result row per attempt as soon as
the attempt is judged (with a trace row per search step, then the final
exchange), and the final run status.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Mapping, Optional
from uuid import UUID

from hackagent.core.contracts import EvalStatus, RunStatus
from hackagent.core.settings import Settings
from hackagent.models.config import ModelConfig
from hackagent.orchestrator.campaign.results import (
    Attempt,
    trace_payload,
    trace_step_type,
)
from hackagent.orchestrator.campaign.spec import (
    OutputSpec,
    StorageSpec,
    recorded_model,
)
from hackagent.storage.store import Store
from hackagent.tracking.evaluation import eval_columns
from hackagent.tracking.serialize import sanitize_for_json


def open_store(storage: StorageSpec, settings: Optional[Settings] = None) -> Store:
    """Open the store the campaign names.

    A campaign says where its results go, and nothing else decides it: the
    default is this machine's SQLite, and ``remote`` names its own server
    and the environment variable holding that server's key. ``settings``
    supplies the database path the CLI or TUI resolved, so a run follows
    the configuration they were started with.
    """
    if storage.backend == "remote":
        from hackagent.storage.remote import RemoteBackend

        assert storage.base_url and storage.api_key_env  # enforced by StorageSpec
        api_key = os.environ.get(storage.api_key_env, "").strip()
        if not api_key:
            raise ValueError(
                f"Environment variable {storage.api_key_env!r} required for remote storage is not set."
            )
        return RemoteBackend.connect(storage.base_url, api_key)

    from hackagent.storage.local import LocalBackend

    runtime = settings or Settings.resolve()
    return LocalBackend(db_path=runtime.db_path)


def register_target(store: Store, target: ModelConfig) -> UUID:
    """Create or update the agent record that runs are attached to.

    The agent stores the target's whole model config, with any credential
    written into the campaign file redacted: keys stay in the environment
    variable ``api_key_env`` names.
    """
    agent = store.create_or_update_agent(target.name, recorded_model(target))
    return agent.id


class RunTracker:
    """Store records of one attack run."""

    def __init__(
        self,
        store: Store,
        *,
        agent_id: UUID,
        attack_name: str,
        configuration: Mapping[str, Any],
        expected_goals: int,
        output: OutputSpec,
        campaign_run_id: Optional[UUID] = None,
    ) -> None:
        self.store = store
        self.attack_name = attack_name
        self.output = output
        attack = store.create_attack(
            attack_type=attack_name,
            agent_id=agent_id,
            organization=store.get_context().org_id,
            configuration=sanitize_for_json(dict(configuration)),
        )
        run = store.create_run(
            attack_id=attack.id,
            agent_id=agent_id,
            run_config={"expected_total_goals": expected_goals},
            campaign_run_id=campaign_run_id,
        )
        self.run_id = run.id
        store.update_run(self.run_id, status=RunStatus.RUNNING.value)

    def record(self, attempt: Attempt) -> None:
        """Persist one attempt with its evaluation."""
        request = (
            {"messages": [dict(message) for message in attempt.messages]}
            if self.output.save_prompts
            else {}
        )
        identity = {
            "attack_type": self.attack_name,
            "request_index": attempt.request_index,
            **attempt.labels,
        }
        record = self.store.create_result(
            self.run_id,
            attempt.goal,
            attempt.goal_index,
            sanitize_for_json(request),
            identity,
        )
        if self.output.save_traces:
            for sequence, node in enumerate(attempt.trace, start=1):
                self.store.create_trace(
                    record.id,
                    sequence,
                    trace_step_type(node),
                    trace_payload(node, self.output),
                )
            trace: dict[str, Any] = {}
            if self.output.save_prompts:
                trace["request"] = request
            if self.output.save_responses and attempt.response is not None:
                trace["response"] = asdict(attempt.response)
            self.store.create_trace(
                record.id,
                len(attempt.trace) + 1,
                "interaction",
                sanitize_for_json(trace),
            )

        columns = eval_columns(attempt.verdict)
        # The store replaces the metadata wholesale, so carry the identity forward.
        details: dict[str, Any] = dict(identity)
        if attempt.error is not None:
            details["error"] = attempt.error
        if attempt.metadata:
            details["attack_metadata"] = dict(attempt.metadata)
        if self.output.save_responses and attempt.response is not None:
            details["response"] = attempt.response.text
            details["decoded_response"] = attempt.decoded
        response = attempt.response
        self.store.update_result(
            record.id,
            evaluation_status=_evaluation_status(attempt),
            evaluation_notes=attempt.verdict.explanation
            if attempt.verdict
            else attempt.error,
            evaluation_metrics={
                key: value
                for key, value in columns.items()
                if key.startswith(("eval_", "explanation_"))
            },
            agent_specific_data=sanitize_for_json(details),
            latency_ms=response.latency_ms if response else None,
            response_status_code=response.error.status_code
            if response and response.error
            else None,
        )

    def complete(self) -> None:
        self.store.update_run(self.run_id, status=RunStatus.COMPLETED.value)
        self.store.flush()

    def fail(self, error: BaseException) -> None:
        self.store.update_run(
            self.run_id,
            status=RunStatus.FAILED.value,
            run_notes=f"Execution failed: {error}",
        )
        self.store.flush()

    def cancel(self) -> None:
        self.store.update_run(
            self.run_id,
            status=RunStatus.CANCELLED.value,
            run_notes="Execution cancelled",
        )
        self.store.flush()


def _evaluation_status(attempt: Attempt) -> str | None:
    if attempt.error is not None:
        return EvalStatus.ERROR_TEST_FRAMEWORK.value
    if attempt.verdict is None:
        return None
    if attempt.verdict.error:
        return EvalStatus.ERROR_TEST_FRAMEWORK.value
    if attempt.verdict.success:
        return EvalStatus.SUCCESSFUL_JAILBREAK.value
    return EvalStatus.FAILED_JAILBREAK.value


__all__ = ["RunTracker", "open_store", "register_target"]
