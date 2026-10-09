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
from typing import Any, Mapping
from uuid import UUID

from hackagent.core.contracts import EvalStatus, RunStatus
from hackagent.core.settings import Settings
from hackagent.models.config import ModelConfig
from hackagent.orchestrator.campaign.results import (
    Attempt,
    trace_payload,
    trace_step_type,
)
from hackagent.orchestrator.campaign.spec import OutputSpec, StorageSpec
from hackagent.storage.store import Store
from hackagent.tracking.evaluation import eval_columns
from hackagent.tracking.serialize import sanitize_for_json


def open_store(storage: StorageSpec) -> Store:
    """Open the local database or connect to the remote API."""
    if storage.backend == "local":
        from hackagent.storage.local import LocalBackend

        return LocalBackend(db_path=Settings.resolve(api_key="").db_path)

    from hackagent.storage.remote import RemoteBackend

    assert storage.base_url and storage.api_key_env  # enforced by StorageSpec
    api_key = os.environ.get(storage.api_key_env, "").strip()
    if not api_key:
        raise ValueError(
            f"Environment variable {storage.api_key_env!r} required for remote storage is not set."
        )
    return RemoteBackend.connect(storage.base_url, api_key)


def register_target(store: Store, target: ModelConfig) -> UUID:
    """Create or update the agent record that runs are attached to."""
    agent = store.create_or_update_agent(
        name=target.name,
        agent_type=target.connection.type.value,
        endpoint=target.connection.endpoint or "",
        metadata=target.generation.model_dump(exclude_none=True),
        overwrite_metadata=True,
    )
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
