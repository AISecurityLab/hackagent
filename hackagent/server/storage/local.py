# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
LocalBackend — StorageBackend implementation backed by SQLite.

Selected automatically by HackAgent when no API key is available.  All data
is persisted in ~/.local/share/hackagent/hackagent.db with the same schema
as the remote Django models, enabling identical TUI/SDK behaviour offline.

Thread safety: a per-instance lock ensures safe concurrent writes from the
goal-batch parallel execution workers.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from hackagent.server.storage.base import (
    AgentRecord,
    AttackRecord,
    OrganizationContext,
    PaginatedResult,
    ResultRecord,
    RunRecord,
    TraceRecord,
)

logger = logging.getLogger("hackagent.server.storage.local")

_DEFAULT_DB_PATH = "~/.local/share/hackagent/hackagent.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS local_context (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    agent_type      TEXT NOT NULL,
    endpoint        TEXT NOT NULL DEFAULT '',
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    organization_id TEXT NOT NULL,
    owner           TEXT NOT NULL DEFAULT 'local',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS attacks (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    organization_id TEXT NOT NULL,
    config_json     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    attack_id   TEXT NOT NULL REFERENCES attacks(id),
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    config_json TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'PENDING',
    run_notes   TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(id),
    goal                TEXT NOT NULL DEFAULT '',
    goal_index          INTEGER NOT NULL DEFAULT 0,
    request_payload_json TEXT NOT NULL DEFAULT '{}',
    evaluation_status   TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
    evaluation_notes    TEXT,
    metrics_json        TEXT NOT NULL DEFAULT '{}',
    metadata_json       TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traces (
    id           TEXT PRIMARY KEY,
    result_id    TEXT NOT NULL REFERENCES results(id),
    sequence     INTEGER NOT NULL,
    step_type    TEXT NOT NULL,
    content_json TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attacks_agent   ON attacks(agent_id);
CREATE INDEX IF NOT EXISTS idx_runs_attack     ON runs(attack_id);
CREATE INDEX IF NOT EXISTS idx_results_run     ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_traces_result   ON traces(result_id);
"""


def _now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(s: Optional[str]) -> datetime:
    if not s:
        return _now()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return _now()


class LocalBackend:
    """
    SQLite-backed StorageBackend.

    All tracking data (agents, attacks, runs, results, traces) is stored in a
    single SQLite database.  The schema mirrors the remote Django models so that
    TUI views and the SDK work identically in both online and offline modes.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path or _DEFAULT_DB_PATH).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._lock = threading.Lock()
        self._context: Optional[OrganizationContext] = None
        logger.info(f"LocalBackend initialised at {self._db_path}")

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Call this when the backend is no longer needed to release the file lock.
        Particularly important on Windows where open file handles prevent
        temporary directory cleanup.
        """
        self._conn.close()

    # ── Context ──────────────────────────────────────────────────────────────

    def get_api_key(self) -> Optional[str]:
        return None  # no API key in local mode

    def get_context(self) -> OrganizationContext:
        if self._context is not None:
            return self._context
        with self._lock:
            cur = self._conn.execute("SELECT id FROM local_context LIMIT 1")
            row = cur.fetchone()
            if row:
                org_id = UUID(row["id"])
            else:
                org_id = uuid.uuid4()
                self._conn.execute(
                    "INSERT INTO local_context (id, user_id, created_at) VALUES (?,?,?)",
                    (str(org_id), "local", _now_str()),
                )
                self._conn.commit()
            self._context = OrganizationContext(org_id=org_id, user_id="local")
        return self._context

    # ── Agent ─────────────────────────────────────────────────────────────────

    def create_or_update_agent(
        self,
        name: str,
        agent_type: str,
        endpoint: str,
        metadata: Dict[str, Any],
        overwrite_metadata: bool = True,
    ) -> AgentRecord:
        ctx = self.get_context()
        now = _now_str()
        meta_json = json.dumps({k: v for k, v in metadata.items() if v is not None})

        with self._lock:
            cur = self._conn.execute(
                "SELECT id, metadata_json, created_at FROM agents WHERE name = ? LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
            if row:
                agent_id = UUID(row["id"])
                created_at = row["created_at"]
                if overwrite_metadata:
                    existing_meta = json.loads(row["metadata_json"] or "{}")
                    merged = {**existing_meta, **metadata}
                    merged_json = json.dumps(
                        {k: v for k, v in merged.items() if v is not None}
                    )
                    self._conn.execute(
                        "UPDATE agents SET agent_type=?, endpoint=?, metadata_json=?, updated_at=? WHERE id=?",
                        (agent_type, endpoint, merged_json, now, str(agent_id)),
                    )
                    self._conn.commit()
                    final_meta = json.loads(merged_json)
                else:
                    final_meta = json.loads(row["metadata_json"] or "{}")
            else:
                agent_id = uuid.uuid4()
                created_at = now
                self._conn.execute(
                    """INSERT INTO agents
                       (id, name, agent_type, endpoint, metadata_json, organization_id, owner, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        str(agent_id),
                        name,
                        agent_type,
                        endpoint,
                        meta_json,
                        str(ctx.org_id),
                        "local",
                        now,
                        now,
                    ),
                )
                self._conn.commit()
                final_meta = metadata

        return AgentRecord(
            id=agent_id,
            name=name,
            agent_type=agent_type,
            endpoint=endpoint,
            metadata=final_meta,
            organization=ctx.org_id,
            owner="local",
            created_at=_to_dt(
                created_at if not isinstance(created_at, str) else created_at
            ),
            updated_at=_to_dt(now),
        )

    def list_agents(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AgentRecord]:
        ctx = self.get_context()
        offset = (page - 1) * page_size
        with self._lock:
            total_row = self._conn.execute("SELECT COUNT(*) FROM agents").fetchone()
            total = total_row[0] if total_row else 0
            rows = self._conn.execute(
                "SELECT * FROM agents ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
        items = [self._row_to_agent(r, ctx.org_id) for r in rows]
        return PaginatedResult(items=items, total=total)

    def get_agent(self, agent_id: UUID) -> AgentRecord:
        ctx = self.get_context()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM agents WHERE id = ? LIMIT 1", (str(agent_id),)
            ).fetchone()
        if row:
            return self._row_to_agent(row, ctx.org_id)
        raise RuntimeError(f"LocalBackend: Agent {agent_id} not found")

    def delete_agent(self, agent_id: UUID) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM agents WHERE id = ?", (str(agent_id),))
            self._conn.commit()

    def _row_to_agent(self, row, org_id: UUID) -> AgentRecord:
        return AgentRecord(
            id=UUID(row["id"]),
            name=row["name"],
            agent_type=row["agent_type"],
            endpoint=row["endpoint"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            organization=org_id,
            owner=row["owner"],
            created_at=_to_dt(row["created_at"]),
            updated_at=_to_dt(row["updated_at"]),
        )

    # ── Attack ────────────────────────────────────────────────────────────────

    def create_attack(
        self,
        attack_type: str,
        agent_id: UUID,
        organization: UUID,
        configuration: Dict[str, Any],
    ) -> AttackRecord:
        attack_id = uuid.uuid4()
        now = _now_str()
        with self._lock:
            self._conn.execute(
                "INSERT INTO attacks (id, type, agent_id, organization_id, config_json, created_at) VALUES (?,?,?,?,?,?)",
                (
                    str(attack_id),
                    attack_type,
                    str(agent_id),
                    str(organization),
                    json.dumps(configuration),
                    now,
                ),
            )
            self._conn.commit()
        return AttackRecord(
            id=attack_id,
            type=attack_type,
            agent_id=agent_id,
            organization=organization,
            configuration=configuration,
            created_at=_to_dt(now),
        )

    def list_attacks(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AttackRecord]:
        offset = (page - 1) * page_size
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM attacks").fetchone()[0]
            rows = self._conn.execute(
                "SELECT * FROM attacks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
        items = [
            AttackRecord(
                id=UUID(r["id"]),
                type=r["type"],
                agent_id=UUID(r["agent_id"]),
                organization=UUID(r["organization_id"]),
                configuration=json.loads(r["config_json"] or "{}"),
                created_at=_to_dt(r["created_at"]),
            )
            for r in rows
        ]
        return PaginatedResult(items=items, total=total)

    # ── Run ───────────────────────────────────────────────────────────────────

    def create_run(
        self,
        attack_id: UUID,
        agent_id: UUID,
        run_config: Dict[str, Any],
    ) -> RunRecord:
        run_id = uuid.uuid4()
        now = _now_str()
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs (id, attack_id, agent_id, config_json, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    str(run_id),
                    str(attack_id),
                    str(agent_id),
                    json.dumps(run_config),
                    "PENDING",
                    now,
                    now,
                ),
            )
            self._conn.commit()
        return RunRecord(
            id=run_id,
            attack_id=attack_id,
            agent_id=agent_id,
            run_config=run_config,
            status="PENDING",
            run_notes=None,
            created_at=_to_dt(now),
            updated_at=_to_dt(now),
        )

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
    ) -> RunRecord:
        now = _now_str()
        with self._lock:
            if status is not None and run_notes is not None:
                self._conn.execute(
                    "UPDATE runs SET status=?, run_notes=?, updated_at=? WHERE id=?",
                    (status, run_notes, now, str(run_id)),
                )
            elif status is not None:
                self._conn.execute(
                    "UPDATE runs SET status=?, updated_at=? WHERE id=?",
                    (status, now, str(run_id)),
                )
            elif run_notes is not None:
                self._conn.execute(
                    "UPDATE runs SET run_notes=?, updated_at=? WHERE id=?",
                    (run_notes, now, str(run_id)),
                )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM runs WHERE id=? LIMIT 1", (str(run_id),)
            ).fetchone()
        if row:
            return self._row_to_run(row)
        return RunRecord(
            id=run_id,
            attack_id=UUID("00000000-0000-0000-0000-000000000000"),
            agent_id=UUID("00000000-0000-0000-0000-000000000000"),
            run_config={},
            status=status or "",
            run_notes=run_notes,
            created_at=_to_dt(now),
            updated_at=_to_dt(now),
        )

    def list_runs(
        self,
        attack_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[RunRecord]:
        offset = (page - 1) * page_size
        with self._lock:
            if attack_id:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM runs WHERE attack_id=?", (str(attack_id),)
                ).fetchone()[0]
                rows = self._conn.execute(
                    "SELECT * FROM runs WHERE attack_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (str(attack_id), page_size, offset),
                ).fetchall()
            else:
                total = self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                rows = self._conn.execute(
                    "SELECT * FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (page_size, offset),
                ).fetchall()
        return PaginatedResult(items=[self._row_to_run(r) for r in rows], total=total)

    def get_run(self, run_id: UUID) -> RunRecord:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE id=? LIMIT 1", (str(run_id),)
            ).fetchone()
        if row:
            return self._row_to_run(row)
        raise RuntimeError(f"LocalBackend: Run {run_id} not found")

    def _row_to_run(self, row) -> RunRecord:
        return RunRecord(
            id=UUID(row["id"]),
            attack_id=UUID(row["attack_id"]),
            agent_id=UUID(row["agent_id"]),
            run_config=json.loads(row["config_json"] or "{}"),
            status=row["status"],
            run_notes=row["run_notes"],
            created_at=_to_dt(row["created_at"]),
            updated_at=_to_dt(row["updated_at"]),
        )

    def delete_run(self, run_id: UUID) -> None:
        sid = str(run_id)
        with self._lock:
            # traces → results → run
            self._conn.execute(
                "DELETE FROM traces WHERE result_id IN (SELECT id FROM results WHERE run_id = ?)",
                (sid,),
            )
            self._conn.execute("DELETE FROM results WHERE run_id = ?", (sid,))
            self._conn.execute("DELETE FROM runs WHERE id = ?", (sid,))
            self._conn.commit()

    def delete_attack(self, attack_id: UUID) -> None:
        sid = str(attack_id)
        with self._lock:
            # traces → results → runs → attack
            self._conn.execute(
                "DELETE FROM traces WHERE result_id IN "
                "(SELECT id FROM results WHERE run_id IN "
                "(SELECT id FROM runs WHERE attack_id = ?))",
                (sid,),
            )
            self._conn.execute(
                "DELETE FROM results WHERE run_id IN (SELECT id FROM runs WHERE attack_id = ?)",
                (sid,),
            )
            self._conn.execute("DELETE FROM runs WHERE attack_id = ?", (sid,))
            self._conn.execute("DELETE FROM attacks WHERE id = ?", (sid,))
            self._conn.commit()

    def count_result_buckets(self) -> dict:
        """Return {total, jailbreaks, mitigated, failed, pending} via SQL."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT evaluation_status, evaluation_notes FROM results"
            ).fetchall()
        from hackagent.server.dashboard._helpers import _result_bucket

        buckets = {
            "total": 0,
            "jailbreaks": 0,
            "mitigated": 0,
            "failed": 0,
            "pending": 0,
        }
        for r in rows:
            buckets["total"] += 1
            b = _result_bucket(r["evaluation_status"], r["evaluation_notes"])
            if b == "jailbreak":
                buckets["jailbreaks"] += 1
            elif b == "mitigated":
                buckets["mitigated"] += 1
            elif b == "failed":
                buckets["failed"] += 1
            elif b == "pending":
                buckets["pending"] += 1
        return buckets

    # ── Result ────────────────────────────────────────────────────────────────

    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> ResultRecord:
        result_id = uuid.uuid4()
        now = _now_str()
        metadata = {**request_payload, **agent_specific_data}
        with self._lock:
            self._conn.execute(
                """INSERT INTO results
                   (id, run_id, goal, goal_index, request_payload_json,
                    evaluation_status, metadata_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    str(result_id),
                    str(run_id),
                    goal,
                    goal_index,
                    json.dumps(request_payload),
                    "NOT_EVALUATED",
                    json.dumps(agent_specific_data),
                    now,
                    now,
                ),
            )
            self._conn.commit()
        return ResultRecord(
            id=result_id,
            run_id=run_id,
            goal=goal,
            goal_index=goal_index,
            evaluation_status="NOT_EVALUATED",
            evaluation_notes=None,
            evaluation_metrics={},
            metadata=metadata,
            created_at=_to_dt(now),
            updated_at=_to_dt(now),
        )

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> ResultRecord:
        now = _now_str()
        updates: Dict[str, Any] = {"updated_at": now}
        if evaluation_status is not None:
            updates["evaluation_status"] = evaluation_status
        if evaluation_notes is not None:
            updates["evaluation_notes"] = evaluation_notes
        if evaluation_metrics is not None:
            updates["metrics_json"] = json.dumps(evaluation_metrics)
        if agent_specific_data is not None:
            updates["metadata_json"] = json.dumps(agent_specific_data)

        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [str(result_id)]
        with self._lock:
            self._conn.execute(f"UPDATE results SET {set_clause} WHERE id=?", values)
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM results WHERE id=? LIMIT 1", (str(result_id),)
            ).fetchone()
        if row:
            return self._row_to_result(row)
        return ResultRecord(
            id=result_id,
            run_id=UUID("00000000-0000-0000-0000-000000000000"),
            goal="",
            goal_index=0,
            evaluation_status=evaluation_status or "NOT_EVALUATED",
            evaluation_notes=evaluation_notes,
            evaluation_metrics=evaluation_metrics or {},
            metadata=agent_specific_data or {},
            created_at=_to_dt(now),
            updated_at=_to_dt(now),
        )

    def list_results(
        self,
        run_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[ResultRecord]:
        offset = (page - 1) * page_size
        with self._lock:
            if run_id:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM results WHERE run_id=?", (str(run_id),)
                ).fetchone()[0]
                rows = self._conn.execute(
                    "SELECT * FROM results WHERE run_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (str(run_id), page_size, offset),
                ).fetchall()
            else:
                total = self._conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
                rows = self._conn.execute(
                    "SELECT * FROM results ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (page_size, offset),
                ).fetchall()
        return PaginatedResult(
            items=[self._row_to_result(r) for r in rows], total=total
        )

    def get_result(self, result_id: UUID) -> ResultRecord:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM results WHERE id=? LIMIT 1", (str(result_id),)
            ).fetchone()
        if row:
            return self._row_to_result(row)
        raise RuntimeError(f"LocalBackend: Result {result_id} not found")

    def _row_to_result(self, row) -> ResultRecord:
        return ResultRecord(
            id=UUID(row["id"]),
            run_id=UUID(row["run_id"]),
            goal=row["goal"] or "",
            goal_index=row["goal_index"] or 0,
            evaluation_status=row["evaluation_status"],
            evaluation_notes=row["evaluation_notes"],
            evaluation_metrics=json.loads(row["metrics_json"] or "{}"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=_to_dt(row["created_at"]),
            updated_at=_to_dt(row["updated_at"]),
        )

    # ── Trace ─────────────────────────────────────────────────────────────────

    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> TraceRecord:
        trace_id = uuid.uuid4()
        now = _now_str()
        with self._lock:
            self._conn.execute(
                "INSERT INTO traces (id, result_id, sequence, step_type, content_json, created_at) VALUES (?,?,?,?,?,?)",
                (
                    str(trace_id),
                    str(result_id),
                    sequence,
                    step_type,
                    json.dumps(content),
                    now,
                ),
            )
            self._conn.commit()
        return TraceRecord(
            id=trace_id,
            result_id=result_id,
            sequence=sequence,
            step_type=step_type,
            content=content,
            created_at=_to_dt(now),
        )

    def list_traces(self, result_id: UUID) -> List[TraceRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM traces WHERE result_id=? ORDER BY sequence ASC",
                (str(result_id),),
            ).fetchall()
        return [
            TraceRecord(
                id=UUID(r["id"]),
                result_id=result_id,
                sequence=r["sequence"],
                step_type=r["step_type"],
                content=json.loads(r["content_json"] or "{}"),
                created_at=_to_dt(r["created_at"]),
            )
            for r in rows
        ]
