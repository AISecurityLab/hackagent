# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Load the conformance sample into a ``LocalBackend``.

Agents, campaigns, attacks and runs are inserted as they are. Results and
traces go through the backend's own write methods, with ids and clock
pinned to the sample's, so their per-goal tallies are kept by the same code
that keeps them for a real campaign. Revisions and run timestamps, which
those writes move, are then set to the sample's values.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator
from unittest import mock
from uuid import UUID

from hackagent.storage.local import LocalBackend


@contextmanager
def _pinned(ident: str, at: str) -> Iterator[None]:
    with (
        mock.patch("hackagent.storage.local._now_str", return_value=at),
        mock.patch("hackagent.storage.local.uuid.uuid4", return_value=UUID(ident)),
    ):
        yield


def load_sample(backend: LocalBackend, sample: dict[str, Any]) -> None:
    conn = backend._conn
    org = str(backend.get_context().org_id)
    for agent in sample["agents"]:
        conn.execute(
            "INSERT INTO agents (id, name, agent_type, endpoint, metadata_json, "
            "organization_id, owner, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                agent["id"],
                agent["name"],
                "OPENAI_SDK",
                "http://127.0.0.1:9999/v1",
                "{}",
                org,
                "local",
                agent["created_at"],
                agent["created_at"],
            ),
        )
    for campaign in sample["campaigns"]:
        conn.execute(
            "INSERT INTO campaigns (id, name, description, agent_id, spec_json, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                campaign["id"],
                campaign["name"],
                "",
                campaign["agent"],
                "{}",
                campaign["created_at"],
                campaign["created_at"],
            ),
        )
    for attack in sample["attacks"]:
        conn.execute(
            "INSERT INTO attacks (id, type, agent_id, organization_id, config_json, "
            "created_at) VALUES (?,?,?,?,?,?)",
            (
                attack["id"],
                attack["type"],
                attack["agent"],
                org,
                json.dumps(attack["configuration"]),
                attack["created_at"],
            ),
        )
    for run in sample["campaign_runs"]:
        conn.execute(
            "INSERT INTO campaign_runs (id, agent_id, campaign_id, launched, name, "
            "campaign_config_json, audit_json, status, run_notes, revision, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run["id"],
                run["agent"],
                run["campaign"],
                int(run["executor"] == "local"),
                run["name"],
                json.dumps(run["configuration"]),
                json.dumps(run["audit"]) if run["audit"] is not None else None,
                run["status"],
                run["notes"],
                0,
                run["created_at"],
                run["updated_at"],
            ),
        )
    for run in sample["attack_runs"]:
        conn.execute(
            "INSERT INTO runs (id, campaign_run_id, attack_id, agent_id, config_json, "
            "status, run_notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                run["id"],
                run["campaign_run"],
                run["attack"],
                run["agent"],
                json.dumps(run["configuration"]),
                run["status"],
                run["notes"],
                run["created_at"],
                run["updated_at"],
            ),
        )
    conn.commit()

    traces: dict[str, list[dict[str, Any]]] = {}
    for trace in sample["traces"]:
        traces.setdefault(trace["result"], []).append(trace)
    # As the runner records an attempt: the result, its traces, its verdict.
    for result in sample["results"]:
        with _pinned(result["id"], result["created_at"]):
            backend.create_result(
                UUID(result["run"]),
                result["goal"],
                result["goal_index"],
                result["request_payload"],
                result["agent_specific_data"],
            )
        for trace in traces.get(result["id"], []):
            with _pinned(trace["id"], trace["timestamp"]):
                backend.create_trace(
                    UUID(result["id"]),
                    trace["sequence"],
                    trace["step_type"],
                    trace["content"],
                )
        with _pinned(result["id"], result["updated_at"]):
            backend.update_result(
                UUID(result["id"]),
                evaluation_status=result["evaluation_status"],
                evaluation_notes=result["evaluation_notes"],
                agent_specific_data=result["agent_specific_data"],
                latency_ms=result["latency_ms"],
            )

    for run in sample["campaign_runs"]:
        conn.execute(
            "UPDATE campaign_runs SET revision=?, updated_at=? WHERE id=?",
            (run["revision"], run["updated_at"], run["id"]),
        )
    conn.commit()
