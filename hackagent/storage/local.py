# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
LocalBackend — Store implementation backed by SQLite.

Selected automatically by HackAgent when no API key is available.  All data
is persisted in ~/.local/share/hackagent/hackagent.db with a stable schema
for TUI/SDK access.

Thread safety: a per-instance lock ensures safe concurrent writes from the
goal-batch parallel execution workers.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from uuid import UUID

from hackagent.storage.records import (
    AgentRecord,
    AttackRecord,
    CampaignRunRecord,
    OrganizationContext,
    PaginatedResult,
    ResultRecord,
    RunRecord,
    TraceRecord,
)
from hackagent.storage.buckets import result_bucket

logger = logging.getLogger("hackagent.storage.local")

_DEFAULT_DB_PATH = "~/.local/share/hackagent/hackagent.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_snapshots (
    campaign_id TEXT PRIMARY KEY REFERENCES campaign_runs(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    source_revision TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    finalized INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT NOT NULL,
    costs_json TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    goals_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS dashboard_worker (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    owner TEXT NOT NULL,
    lease_until REAL NOT NULL
);
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

CREATE TABLE IF NOT EXISTS campaign_runs (
    id                   TEXT PRIMARY KEY,
    agent_id             TEXT NOT NULL REFERENCES agents(id),
    name                 TEXT NOT NULL,
    campaign_config_json TEXT NOT NULL DEFAULT '{}',
    audit_json           TEXT,
    status               TEXT NOT NULL DEFAULT 'PENDING',
    run_notes            TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    campaign_run_id TEXT REFERENCES campaign_runs(id),
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

CREATE TABLE IF NOT EXISTS attack_builder_drafts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    canvas_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attacks_agent   ON attacks(agent_id);
CREATE INDEX IF NOT EXISTS idx_campaign_runs_agent ON campaign_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_runs_attack     ON runs(attack_id);
CREATE INDEX IF NOT EXISTS idx_results_run     ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_run_goal_order
    ON results(run_id, goal_index, created_at, id);
CREATE INDEX IF NOT EXISTS idx_traces_result   ON traces(result_id);
"""


def _now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _quantile(ordered: List[float], q: float) -> float:
    """Linear-interpolated quantile of an already sorted, non-empty list."""
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _to_dt(s: Optional[str]) -> datetime:
    if not s:
        return _now()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return _now()


class LocalBackend:
    """
    SQLite-backed Store.

    All tracking data (agents, attacks, runs, results, traces) is stored in a
    single SQLite database so TUI views and the SDK can access the same data.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path or _DEFAULT_DB_PATH).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.create_function(
            "result_bucket", 2, result_bucket, deterministic=True
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = PERSIST")
        self._conn.executescript(_SCHEMA)
        self._upgrade_schema()
        self._conn.commit()
        self._lock = threading.Lock()
        self._context: Optional[OrganizationContext] = None
        logger.info(f"LocalBackend initialised at {self._db_path}")

    def _upgrade_schema(self) -> None:
        """Apply additive migrations required by older local databases."""

        snapshot_columns = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(dashboard_snapshots)")
        }
        if "finalized" not in snapshot_columns:
            self._conn.execute(
                "ALTER TABLE dashboard_snapshots ADD COLUMN finalized INTEGER NOT NULL DEFAULT 0"
            )
        for column, default in (("detail_json", "{}"), ("goals_json", "[]")):
            if column not in snapshot_columns:
                self._conn.execute(
                    f"ALTER TABLE dashboard_snapshots ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'"
                )
        columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        if "campaign_run_id" not in columns:
            self._conn.execute(
                "ALTER TABLE runs ADD COLUMN campaign_run_id TEXT "
                "REFERENCES campaign_runs(id)"
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_campaign ON runs(campaign_run_id)"
        )

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Call this when the backend is no longer needed to release the file lock.
        Particularly important on Windows where open file handles prevent
        temporary directory cleanup.
        """
        self._conn.close()

    def flush(self) -> None:
        """No-op: local writes are synchronous (mirrors RemoteBackend.flush)."""

    @contextmanager
    def dashboard_read_snapshot(self) -> Iterator[LocalBackend]:
        """Copy a consistent source view; expensive aggregation never holds this store's lock."""
        snapshot = object.__new__(LocalBackend)
        snapshot._conn = sqlite3.connect(":memory:", check_same_thread=False)
        snapshot._conn.row_factory = sqlite3.Row
        snapshot._conn.create_function(
            "result_bucket", 2, result_bucket, deterministic=True
        )
        snapshot._lock = threading.Lock()
        snapshot._context = None
        try:
            if str(self._db_path) == ":memory:":
                with self._lock:
                    self._conn.backup(snapshot._conn)
            else:
                source = sqlite3.connect(
                    f"{self._db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=30
                )
                try:
                    source.backup(snapshot._conn)
                finally:
                    source.close()
            yield snapshot
        finally:
            snapshot.close()

    @contextmanager
    def dashboard_writer(self) -> Iterator[LocalBackend]:
        """Do not hold the HTTP store's mutex while waiting for cache write locks."""
        if str(self._db_path) == ":memory:":
            yield self
            return
        writer = LocalBackend(str(self._db_path))
        writer._conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield writer
        finally:
            writer.close()

    def dashboard_snapshots(self, ids: List[UUID]) -> Dict[str, Dict[str, Any]]:
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM dashboard_snapshots WHERE campaign_id IN ({marks})",
                [str(ident) for ident in ids],
            ).fetchall()
        return {
            row["campaign_id"]: {
                "version": row["version"],
                "source_revision": row["source_revision"],
                "generated_at": row["generated_at"],
                "finalized": bool(row["finalized"]),
                "summary": json.loads(row["summary_json"]),
                "costs": json.loads(row["costs_json"]),
                "detail": json.loads(row["detail_json"]),
                "goals": json.loads(row["goals_json"]),
            }
            for row in rows
        }

    def claim_dashboard_worker(
        self, owner: str, now: float, lease_until: float
    ) -> bool:
        with self._lock, self._conn:
            previous = self._conn.execute(
                "SELECT owner FROM dashboard_worker WHERE id=1"
            ).fetchone()
            if previous and previous["owner"] != owner:
                parts = previous["owner"].split(":", 2)
                if (
                    len(parts) == 3
                    and parts[0] == socket.gethostname()
                    and parts[1].isdigit()
                ):
                    try:
                        os.kill(int(parts[1]), 0)
                    except ProcessLookupError:
                        self._conn.execute(
                            "DELETE FROM dashboard_worker WHERE id=1 AND owner=?",
                            (previous["owner"],),
                        )
                    except PermissionError:
                        pass
            cursor = self._conn.execute(
                """INSERT INTO dashboard_worker VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,
                     lease_until=excluded.lease_until
                   WHERE dashboard_worker.lease_until < ? OR dashboard_worker.owner = ?""",
                (owner, lease_until, now, owner),
            )
            return cursor.rowcount == 1

    def release_dashboard_worker(self, owner: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM dashboard_worker WHERE owner=?", (owner,))

    def save_dashboard_snapshot(
        self,
        campaign_id: UUID,
        version: int,
        revision: str,
        generated_at: str,
        summary: Dict[str, Any],
        costs: Dict[str, Any],
        *,
        finalized: bool = False,
        detail: Dict[str, Any],
        goals: List[Any],
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO dashboard_snapshots
                   (campaign_id, version, source_revision, generated_at,
                    summary_json, costs_json, finalized, detail_json, goals_json)
                   SELECT id, ?, ?, ?, ?, ?, ?, ?, ? FROM campaign_runs WHERE id=?
                   ON CONFLICT(campaign_id) DO UPDATE SET version=excluded.version,
                     source_revision=excluded.source_revision,
                     generated_at=excluded.generated_at, summary_json=excluded.summary_json,
                     costs_json=excluded.costs_json, finalized=excluded.finalized,
                     detail_json=excluded.detail_json, goals_json=excluded.goals_json
                   WHERE excluded.generated_at >= dashboard_snapshots.generated_at""",
                (
                    version,
                    revision,
                    generated_at,
                    json.dumps(summary),
                    json.dumps(costs),
                    finalized,
                    json.dumps(detail),
                    json.dumps(goals),
                    str(campaign_id),
                ),
            )

    def dashboard_refresh_candidates(self, version: int) -> List[UUID]:
        """Only missing/outdated snapshots and campaigns not yet finalized."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT c.id FROM campaign_runs c
                   LEFT JOIN dashboard_snapshots d ON d.campaign_id=c.id
                   WHERE d.campaign_id IS NULL OR d.version != ? OR d.finalized = 0
                     OR c.status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
                     OR EXISTS (
                       SELECT 1 FROM runs n WHERE n.campaign_run_id=c.id
                       AND n.status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
                     )
                   ORDER BY c.created_at DESC, c.id""",
                (version,),
            ).fetchall()
        return [UUID(row["id"]) for row in rows]

    def dashboard_can_finalize(self, campaign_id: UUID) -> bool:
        with self._lock:
            row = self._conn.execute(
                """SELECT c.status IN ('COMPLETED', 'FAILED', 'CANCELLED')
                     AND NOT EXISTS (
                       SELECT 1 FROM runs n WHERE n.campaign_run_id=c.id
                       AND n.status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
                     ) AS finalized
                   FROM campaign_runs c WHERE c.id=?""",
                (str(campaign_id),),
            ).fetchone()
        return bool(row and row["finalized"])

    def dashboard_revision(self, campaign_id: UUID) -> str:
        """Fingerprint all inputs, including late traces and verdict updates."""
        ident = str(campaign_id)
        with self._lock:
            rows = [
                tuple(self._conn.execute(sql, (ident,)).fetchone())
                for sql in (
                    "SELECT updated_at FROM campaign_runs WHERE id=?",
                    "SELECT COUNT(*), MAX(updated_at) FROM runs WHERE campaign_run_id=?",
                    """SELECT COUNT(*), MAX(r.updated_at) FROM results r JOIN runs n
                       ON n.id=r.run_id WHERE n.campaign_run_id=?""",
                    """SELECT COUNT(*), MAX(t.created_at) FROM traces t JOIN results r
                       ON r.id=t.result_id JOIN runs n ON n.id=r.run_id
                       WHERE n.campaign_run_id=?""",
                    """SELECT a.name, a.updated_at FROM agents a JOIN campaign_runs c
                       ON c.agent_id=a.id WHERE c.id=?""",
                )
            ]
        return json.dumps(rows)

    def dashboard_run_ids(self, campaign_id: UUID) -> List[UUID]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM runs WHERE campaign_run_id=? ORDER BY created_at, id",
                (str(campaign_id),),
            ).fetchall()
        return [UUID(row["id"]) for row in rows]

    def panel_vote_rows(self, run_ids: List[UUID]) -> List[Dict[str, Any]]:
        if not run_ids:
            return []
        marks = ",".join("?" for _ in run_ids)
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT run_id, goal_index, metrics_json, evaluation_status, evaluation_notes
                    FROM results WHERE run_id IN ({marks})""",
                [str(ident) for ident in run_ids],
            ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "goal_index": row["goal_index"],
                "metrics": json.loads(row["metrics_json"]),
                "outcome": result_bucket(
                    row["evaluation_status"], row["evaluation_notes"]
                ),
            }
            for row in rows
        ]

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

    def create_or_update_agent(self, name: str, config: Dict[str, Any]) -> AgentRecord:
        ctx = self.get_context()
        now = _now_str()
        connection = config.get("connection") or {}
        agent_type = str(connection.get("type") or "")
        endpoint = str(connection.get("endpoint") or "")
        config_json = json.dumps(config)

        with self._lock:
            row = self._conn.execute(
                "SELECT id, created_at FROM agents WHERE name = ? LIMIT 1",
                (name,),
            ).fetchone()
            if row:
                agent_id = UUID(row["id"])
                created_at = row["created_at"]
                self._conn.execute(
                    "UPDATE agents SET agent_type=?, endpoint=?, metadata_json=?, updated_at=? WHERE id=?",
                    (agent_type, endpoint, config_json, now, str(agent_id)),
                )
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
                        config_json,
                        str(ctx.org_id),
                        "local",
                        now,
                        now,
                    ),
                )
            self._conn.commit()

        return AgentRecord(
            id=agent_id,
            name=name,
            agent_type=agent_type,
            endpoint=endpoint,
            metadata=json.loads(config_json),
            organization=ctx.org_id,
            owner="local",
            created_at=_to_dt(created_at),
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

    # ── Campaign run ──────────────────────────────────────────────────────────

    def start_campaign(self, agent_id: UUID, spec: Dict[str, Any]) -> CampaignRunRecord:
        campaign_run_id = uuid.uuid4()
        name = str((spec.get("campaign") or {}).get("name") or "Campaign")
        now = _now_str()
        with self._lock:
            self._conn.execute(
                "INSERT INTO campaign_runs "
                "(id, agent_id, name, campaign_config_json, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    str(campaign_run_id),
                    str(agent_id),
                    name,
                    json.dumps(spec),
                    "RUNNING",
                    now,
                    now,
                ),
            )
            self._conn.commit()
        return CampaignRunRecord(
            id=campaign_run_id,
            agent_id=agent_id,
            name=name,
            campaign_config=spec,
            audit=None,
            status="RUNNING",
            run_notes=None,
            created_at=_to_dt(now),
            updated_at=_to_dt(now),
        )

    def update_campaign_run(
        self,
        campaign_run_id: UUID,
        status: Optional[str] = None,
        audit: Optional[Dict[str, Any]] = None,
        run_notes: Optional[str] = None,
    ) -> CampaignRunRecord:
        now = _now_str()
        with self._lock:
            updates: Dict[str, Any] = {"updated_at": now}
            if status is not None:
                updates["status"] = status
            if audit is not None:
                updates["audit_json"] = json.dumps(audit)
            if run_notes is not None:
                updates["run_notes"] = run_notes
            set_clause = ", ".join(f"{key}=?" for key in updates)
            self._conn.execute(
                f"UPDATE campaign_runs SET {set_clause} WHERE id=?",
                [*updates.values(), str(campaign_run_id)],
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM campaign_runs WHERE id=? LIMIT 1",
                (str(campaign_run_id),),
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"LocalBackend: Campaign run {campaign_run_id} not found"
            )
        return self._row_to_campaign_run(row)

    def list_campaign_runs(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[CampaignRunRecord]:
        offset = (page - 1) * page_size
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM campaign_runs").fetchone()[
                0
            ]
            rows = self._conn.execute(
                "SELECT * FROM campaign_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
        return PaginatedResult(
            items=[self._row_to_campaign_run(row) for row in rows], total=total
        )

    def get_campaign_run(self, campaign_run_id: UUID) -> CampaignRunRecord:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM campaign_runs WHERE id=? LIMIT 1",
                (str(campaign_run_id),),
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"LocalBackend: Campaign run {campaign_run_id} not found"
            )
        return self._row_to_campaign_run(row)

    @staticmethod
    def _row_to_campaign_run(row: sqlite3.Row) -> CampaignRunRecord:
        return CampaignRunRecord(
            id=UUID(row["id"]),
            agent_id=UUID(row["agent_id"]),
            name=row["name"],
            campaign_config=json.loads(row["campaign_config_json"] or "{}"),
            audit=json.loads(row["audit_json"]) if row["audit_json"] else None,
            status=row["status"],
            run_notes=row["run_notes"],
            created_at=_to_dt(row["created_at"]),
            updated_at=_to_dt(row["updated_at"]),
        )

    # ── Attack run ────────────────────────────────────────────────────────────

    def create_run(
        self,
        attack_id: UUID,
        agent_id: UUID,
        run_config: Dict[str, Any],
        campaign_run_id: Optional[UUID] = None,
    ) -> RunRecord:
        run_id = uuid.uuid4()
        now = _now_str()
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs "
                "(id, campaign_run_id, attack_id, agent_id, config_json, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(run_id),
                    str(campaign_run_id) if campaign_run_id is not None else None,
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
            campaign_run_id=campaign_run_id,
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
        run_config: Optional[Dict[str, Any]] = None,
    ) -> RunRecord:
        now = _now_str()
        with self._lock:
            updates: Dict[str, Any] = {"updated_at": now}
            if status is not None:
                updates["status"] = status
            if run_notes is not None:
                updates["run_notes"] = run_notes
            if run_config is not None:
                updates["config_json"] = json.dumps(run_config)

            if len(updates) > 1:
                set_clause = ", ".join(f"{k}=?" for k in updates)
                values = list(updates.values()) + [str(run_id)]
                self._conn.execute(
                    f"UPDATE runs SET {set_clause} WHERE id=?",
                    values,
                )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM runs WHERE id=? LIMIT 1", (str(run_id),)
            ).fetchone()
        if row:
            return self._row_to_run(row)
        return RunRecord(
            id=run_id,
            campaign_run_id=None,
            attack_id=UUID("00000000-0000-0000-0000-000000000000"),
            agent_id=UUID("00000000-0000-0000-0000-000000000000"),
            run_config=run_config or {},
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
            campaign_run_id=UUID(row["campaign_run_id"])
            if row["campaign_run_id"]
            else None,
            attack_id=UUID(row["attack_id"]),
            agent_id=UUID(row["agent_id"]),
            run_config=json.loads(row["config_json"] or "{}"),
            status=row["status"],
            run_notes=row["run_notes"],
            created_at=_to_dt(row["created_at"]),
            updated_at=_to_dt(row["updated_at"]),
        )

    def campaign_results(
        self,
        run_ids: List[UUID],
        *,
        goal_index: Optional[int] = None,
        full: bool = False,
    ) -> List[ResultRecord]:
        """Read only summary fields unless a selected goal needs full conversations."""
        ids = [str(ident) for ident in run_ids]
        if not ids:
            return []
        if full and goal_index is None:
            raise ValueError("Full campaign results require a selected goal.")
        marks = ",".join("?" for _ in ids)
        fields = (
            "*"
            if full
            else """id, run_id, goal, goal_index,
            evaluation_status, evaluation_notes, created_at, updated_at,
            '{}' AS request_payload_json, '{}' AS metrics_json,
            json_object('category', json_extract(metadata_json, '$.category'),
                        'subcategory', json_extract(metadata_json, '$.subcategory'))
                AS metadata_json"""
        )
        where = f"run_id IN ({marks})"
        args: List[Any] = list(ids)
        if goal_index is not None:
            where += " AND goal_index=?"
            args.append(goal_index)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {fields} FROM results WHERE {where} ORDER BY created_at DESC",
                args,
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def campaign_attempts(
        self,
        run_ids: List[UUID],
        goal_index: int,
        *,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        """Page lightweight attempt rows after filtering a goal in SQLite."""
        ids = [str(ident) for ident in run_ids]
        if not ids:
            return {"items": [], "total": 0, "first_success": None}
        marks = ",".join("?" for _ in ids)
        query = f"""WITH ordered AS (
            SELECT id, run_id, evaluation_status, evaluation_notes, created_at,
                ROW_NUMBER() OVER (ORDER BY created_at, id) AS ordinal
            FROM results WHERE run_id IN ({marks}) AND goal_index=?
        ) """
        args = [*ids, goal_index]
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM results WHERE run_id IN ({marks}) AND goal_index=?",
                args,
            ).fetchone()[0]
            first = self._conn.execute(
                query
                + """SELECT id, ordinal FROM ordered
                    WHERE result_bucket(evaluation_status, evaluation_notes)='jailbreak'
                    ORDER BY ordinal LIMIT 1""",
                args,
            ).fetchone()
            rows = self._conn.execute(
                query + "SELECT * FROM ordered ORDER BY ordinal LIMIT ? OFFSET ?",
                [*args, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [
                {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "ordinal": row["ordinal"],
                    "bucket": result_bucket(
                        row["evaluation_status"], row["evaluation_notes"]
                    ),
                    "notes": row["evaluation_notes"],
                    "created_at": _to_dt(row["created_at"]).isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "first_success": {
                "id": first["id"],
                "page": (first["ordinal"] - 1) // page_size + 1,
            }
            if first
            else None,
        }

    def campaign_outcomes(self, campaign_ids: List[UUID]) -> Dict[str, Dict[str, int]]:
        """Summary counts without materializing result payloads or metadata."""
        ids = [str(ident) for ident in campaign_ids]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        with self._lock:
            runs = self._conn.execute(
                f"""SELECT n.campaign_run_id, COUNT(*) AS attack_runs,
                           MIN(n.status = 'COMPLETED' AND c.status = 'COMPLETED') AS completed
                    FROM runs n JOIN campaign_runs c ON c.id = n.campaign_run_id
                    WHERE n.campaign_run_id IN ({marks})
                    GROUP BY n.campaign_run_id""",
                ids,
            ).fetchall()
            goals = self._conn.execute(
                f"""WITH per_goal AS (
                    SELECT n.campaign_run_id, r.goal_index, COUNT(*) AS attempts,
                        MAX(result_bucket(r.evaluation_status, r.evaluation_notes)
                            = 'jailbreak') AS jailbroken,
                        MIN(result_bucket(r.evaluation_status, r.evaluation_notes)
                            = 'mitigated') AS mitigated
                    FROM results r JOIN runs n ON n.id = r.run_id
                    WHERE n.campaign_run_id IN ({marks})
                    GROUP BY n.campaign_run_id, r.goal_index
                )
                SELECT campaign_run_id, COUNT(*) AS recorded_goals,
                       SUM(attempts) AS attempts, SUM(jailbroken) AS jailbroken,
                       SUM(CASE WHEN jailbroken = 0 THEN mitigated ELSE 0 END) AS mitigated
                FROM per_goal GROUP BY campaign_run_id""",
                ids,
            ).fetchall()
        counts = {
            sid: {
                "attack_runs": 0,
                "recorded_goals": 0,
                "attempts": 0,
                "jailbroken": 0,
                "mitigated": 0,
                "unresolved": 0,
            }
            for sid in ids
        }
        completed = {}
        for row in runs:
            counts[row["campaign_run_id"]]["attack_runs"] = row["attack_runs"]
            completed[row["campaign_run_id"]] = bool(row["completed"])
        for row in goals:
            item = counts[row["campaign_run_id"]]
            for key in ("recorded_goals", "attempts", "jailbroken", "mitigated"):
                item[key] = row[key]
            if not completed.get(row["campaign_run_id"], True):
                item["mitigated"] = 0
        for item in counts.values():
            item["unresolved"] = (
                item["recorded_goals"] - item["jailbroken"] - item["mitigated"]
            )
        return counts

    def delete_campaign_run(self, campaign_run_id: UUID) -> None:
        self.delete_campaign_runs([campaign_run_id])

    def delete_campaign_runs(self, campaign_run_ids: List[UUID]) -> None:
        ids = list(dict.fromkeys(str(ident) for ident in campaign_run_ids))
        if not ids:
            raise ValueError("Select at least one campaign execution.")
        placeholders = ",".join("?" for _ in ids)
        terminal = {"COMPLETED", "FAILED", "CANCELLED"}
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            campaigns = self._conn.execute(
                f"SELECT status FROM campaign_runs WHERE id IN ({placeholders})", ids
            ).fetchall()
            if len(campaigns) != len(ids):
                raise RuntimeError(
                    "LocalBackend: Selected campaign execution not found"
                )
            runs = self._conn.execute(
                f"SELECT status FROM runs WHERE campaign_run_id IN ({placeholders})",
                ids,
            ).fetchall()
            if any(row["status"] not in terminal for row in [*campaigns, *runs]):
                raise ValueError("An active campaign execution cannot be deleted.")
            self._conn.execute(
                "DELETE FROM traces WHERE result_id IN "
                "(SELECT id FROM results WHERE run_id IN "
                f"(SELECT id FROM runs WHERE campaign_run_id IN ({placeholders})))",
                ids,
            )
            self._conn.execute(
                "DELETE FROM results WHERE run_id IN "
                f"(SELECT id FROM runs WHERE campaign_run_id IN ({placeholders}))",
                ids,
            )
            self._conn.execute(
                f"DELETE FROM runs WHERE campaign_run_id IN ({placeholders})", ids
            )
            self._conn.execute(
                f"DELETE FROM campaign_runs WHERE id IN ({placeholders})", ids
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
        """Return {total, jailbreaks, mitigated, error, pending} via SQL."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT evaluation_status, evaluation_notes FROM results"
            ).fetchall()
        buckets = {
            "total": 0,
            "jailbreaks": 0,
            "mitigated": 0,
            "error": 0,
            "pending": 0,
        }
        for r in rows:
            buckets["total"] += 1
            b = result_bucket(r["evaluation_status"], r["evaluation_notes"])
            if b == "jailbreak":
                buckets["jailbreaks"] += 1
            elif b == "mitigated":
                buckets["mitigated"] += 1
            elif b in {"failed", "error"}:
                buckets["error"] += 1
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
        if request_payload:
            metadata["request_payload"] = request_payload
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
        latency_ms: Optional[int] = None,
        response_status_code: Optional[int] = None,
    ) -> ResultRecord:
        now = _now_str()
        updates: Dict[str, Any] = {"updated_at": now}
        if evaluation_status is not None:
            updates["evaluation_status"] = evaluation_status
        if evaluation_notes is not None:
            updates["evaluation_notes"] = evaluation_notes
        if evaluation_metrics is not None:
            updates["metrics_json"] = json.dumps(evaluation_metrics)
        # There are no columns for the target's latency and status code; the
        # web layer reads them from the metadata, as it does the other
        # response fields.
        response = {
            key: value
            for key, value in (
                ("latency_ms", latency_ms),
                ("response_status_code", response_status_code),
            )
            if value is not None
        }

        with self._lock:
            if response and agent_specific_data is None:
                row = self._conn.execute(
                    "SELECT metadata_json FROM results WHERE id=? LIMIT 1",
                    (str(result_id),),
                ).fetchone()
                agent_specific_data = json.loads(row["metadata_json"] if row else "{}")
            if agent_specific_data is not None:
                updates["metadata_json"] = json.dumps(
                    {**agent_specific_data, **response}
                )
            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [str(result_id)]
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
        metadata = json.loads(row["metadata_json"] or "{}")
        payload = json.loads(row["request_payload_json"] or "{}")
        if payload:
            metadata["request_payload"] = payload
        return ResultRecord(
            id=UUID(row["id"]),
            run_id=UUID(row["run_id"]),
            goal=row["goal"] or "",
            goal_index=row["goal_index"] or 0,
            evaluation_status=row["evaluation_status"],
            evaluation_notes=row["evaluation_notes"],
            evaluation_metrics=json.loads(row["metrics_json"] or "{}"),
            metadata=metadata,
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

    def run_costs(self, run_ids: List[UUID]) -> Dict[str, Dict[str, Any]]:
        """What each run spent, aggregated from its stored results and traces.

        ``call`` trace nodes are labelled with the role that made them
        (``target``, ``panel``, ``attacker`` or a helper such as ``on_topic``).
        Runs that record no call nodes only have their target interactions,
        so their judge and attacker calls are reported as ``None``: not traced,
        rather than zero.

        Goal samples include the first successful conversation ordinal and, when
        every successful reply carries an active goal clock, the earliest response time.
        Local scheduling waits are excluded; legacy wall clocks are not substituted.
        Persistence timestamps cannot recover the latter for batched searches.
        Token totals are unknown when any target call or attempt lacks usage.
        """
        ids = [str(run_id) for run_id in run_ids]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        with self._lock:
            totals = self._conn.execute(
                f"""SELECT run_id, COUNT(*) AS attempts,
                       COUNT(DISTINCT goal_index) AS goals,
                       MIN(created_at) AS started, MAX(updated_at) AS finished
                    FROM results WHERE run_id IN ({marks}) GROUP BY run_id""",
                ids,
            ).fetchall()
            latencies = self._conn.execute(
                f"""SELECT run_id, json_extract(metadata_json, '$.latency_ms') AS ms
                    FROM results WHERE run_id IN ({marks}) AND ms IS NOT NULL""",
                ids,
            ).fetchall()
            calls = self._conn.execute(
                f"""SELECT r.run_id AS run_id,
                       CASE WHEN t.step_type = 'interaction' THEN '' ELSE
                         json_extract(t.content_json, '$.label') END AS label,
                       COUNT(*) AS n
                    FROM traces t JOIN results r ON r.id = t.result_id
                    WHERE r.run_id IN ({marks})
                      AND (t.step_type = 'interaction'
                           OR json_extract(t.content_json, '$.node') = 'call')
                    GROUP BY 1, 2""",
                ids,
            ).fetchall()
            goal_totals = self._conn.execute(
                f"""WITH ordered AS (
                       SELECT *, ROW_NUMBER() OVER (
                         PARTITION BY run_id, goal_index ORDER BY created_at, id
                       ) AS ordinal,
                       result_bucket(evaluation_status, evaluation_notes) AS bucket
                       FROM results WHERE run_id IN ({marks}) AND goal_index IS NOT NULL
                    )
                    SELECT run_id, goal_index, COUNT(*) AS attempts,
                       MIN(CASE WHEN bucket = 'jailbreak' THEN ordinal END) AS first_jailbreak_attempt,
                       SUM(bucket = 'jailbreak') AS successes,
                       COUNT(CASE WHEN bucket = 'jailbreak' THEN
                         json_extract(metadata_json, '$.attack_metadata.goal_active_target_elapsed_s')
                       END) AS timed_successes,
                       MIN(CASE WHEN bucket = 'jailbreak' THEN
                         json_extract(metadata_json, '$.attack_metadata.goal_active_target_elapsed_s')
                       END) AS first_jailbreak_elapsed_s,
                       SUM(EXISTS(SELECT 1 FROM traces t WHERE t.result_id = results.id
                         AND json_extract(t.content_json, '$.node') = 'call'
                         AND COALESCE(json_extract(t.content_json, '$.label'), '') != ''
                       )) AS traced_attempts,
                       SUM(EXISTS(SELECT 1 FROM traces t WHERE t.result_id = results.id
                         AND json_extract(t.content_json, '$.node') = 'call'
                         AND json_extract(t.content_json, '$.label') = 'target'
                       )) AS target_traced_attempts,
                       SUM(EXISTS(SELECT 1 FROM traces t WHERE t.result_id = results.id
                         AND t.step_type = 'interaction'
                       )) AS interaction_attempts,
                       MIN(created_at) AS started, MAX(updated_at) AS finished
                    FROM ordered AS results
                    GROUP BY run_id, goal_index""",
                ids,
            ).fetchall()
            goal_calls = self._conn.execute(
                f"""SELECT r.run_id, r.goal_index,
                       CASE WHEN t.step_type = 'interaction' THEN '' ELSE
                         json_extract(t.content_json, '$.label') END AS label,
                       COUNT(*) AS n,
                       SUM(CASE WHEN json_extract(t.content_json, '$.scope') = 'goal'
                         THEN 1 ELSE 0 END) AS goal_scoped_n,
                       SUM(COALESCE(json_extract(t.content_json, '$.data.usage.prompt_tokens'),
                                    json_extract(t.content_json, '$.response.usage.prompt_tokens'))) AS prompt,
                       SUM(COALESCE(json_extract(t.content_json, '$.data.usage.completion_tokens'),
                                    json_extract(t.content_json, '$.response.usage.completion_tokens'))) AS completion,
                       SUM(COALESCE(json_extract(t.content_json, '$.data.usage.prompt_tokens'),
                                    json_extract(t.content_json, '$.response.usage.prompt_tokens'), 0)
                         + COALESCE(json_extract(t.content_json, '$.data.usage.completion_tokens'),
                                    json_extract(t.content_json, '$.response.usage.completion_tokens'), 0)) AS tokens,
                       COUNT(CASE WHEN COALESCE(
                         json_extract(t.content_json, '$.data.usage.prompt_tokens'),
                         json_extract(t.content_json, '$.response.usage.prompt_tokens')) IS NOT NULL
                         AND COALESCE(
                         json_extract(t.content_json, '$.data.usage.completion_tokens'),
                         json_extract(t.content_json, '$.response.usage.completion_tokens')) IS NOT NULL
                         THEN 1 END) AS usage_samples
                    FROM traces t JOIN results r ON r.id = t.result_id
                    WHERE r.run_id IN ({marks}) AND r.goal_index IS NOT NULL
                      AND (t.step_type = 'interaction'
                           OR json_extract(t.content_json, '$.node') = 'call')
                    GROUP BY 1, 2, 3""",
                ids,
            ).fetchall()

        by_run: Dict[str, Dict[str, Any]] = {}
        for row in totals:
            started, finished = _to_dt(row["started"]), _to_dt(row["finished"])
            by_run[row["run_id"]] = {
                "attempts": row["attempts"],
                "goals": row["goals"],
                "elapsed_s": max((finished - started).total_seconds(), 0.0),
                "calls": {"target": 0, "attacker": None, "judge": None},
                "calls_traced": False,
                "target_tokens": None,
                "target_latency_ms": None,
            }
        labelled: Dict[str, Dict[str, Any]] = {}
        for row in calls:
            labelled.setdefault(row["run_id"], {})[row["label"] or ""] = row
        for run_id, labels in labelled.items():
            cost = by_run.get(run_id)
            if cost is None:
                continue
            nodes = {label: row for label, row in labels.items() if label}
            interactions = labels.get("")
            if nodes:
                cost["calls_traced"] = True
                target = nodes.get("target")
                cost["calls"] = {
                    "target": target["n"] if target else 0,
                    "attacker": sum(
                        row["n"]
                        for label, row in nodes.items()
                        if label not in ("target", "panel")
                    ),
                    "judge": nodes["panel"]["n"] if "panel" in nodes else 0,
                }
            elif interactions:
                cost["calls"]["target"] = interactions["n"]
        samples: Dict[str, List[float]] = {}
        for row in latencies:
            samples.setdefault(row["run_id"], []).append(float(row["ms"]))
        for run_id, values in samples.items():
            if run_id not in by_run:
                continue
            values.sort()
            by_run[run_id]["target_latency_ms"] = {
                "median": _quantile(values, 0.5),
                "p90": _quantile(values, 0.9),
                "samples": len(values),
            }
        goal_labels: Dict[Any, Dict[str, Any]] = {}
        for row in goal_calls:
            goal_labels.setdefault((row["run_id"], row["goal_index"]), {})[
                row["label"] or ""
            ] = row
        for cost in by_run.values():
            cost["goal_samples"] = []
        token_totals = {run_id: {"prompt": 0, "completion": 0} for run_id in by_run}
        incomplete_usage: set[str] = set()
        for row in goal_totals:
            labels = goal_labels.get((row["run_id"], row["goal_index"]), {})
            nodes = {label: item for label, item in labels.items() if label}
            target = nodes.get("target") if nodes else labels.get("")
            usage = target
            if usage is None or not usage["usage_samples"]:
                usage = labels.get("")
            usage_complete = usage is not None and usage["usage_samples"] == usage["n"]
            if usage is not None:
                usage_complete = usage_complete and (
                    row["interaction_attempts"] == row["attempts"]
                    if usage["label"] == ""
                    else row["target_traced_attempts"] == row["attempts"]
                    or usage["goal_scoped_n"] >= row["attempts"]
                )
            if not usage_complete:
                incomplete_usage.add(row["run_id"])
            else:
                token_totals[row["run_id"]]["prompt"] += int(usage["prompt"])
                token_totals[row["run_id"]]["completion"] += int(usage["completion"])
            started, finished = _to_dt(row["started"]), _to_dt(row["finished"])
            # A batched phase can attach all its goal-scoped calls to one result.
            calls_complete = row["traced_attempts"] == row["attempts"] or (
                target is not None and target["goal_scoped_n"] >= row["attempts"]
            )
            by_run[row["run_id"]]["goal_samples"].append(
                {
                    "goal_index": row["goal_index"],
                    "first_jailbreak_attempt": row["first_jailbreak_attempt"],
                    "first_jailbreak_elapsed_s": row["first_jailbreak_elapsed_s"]
                    if row["successes"] and row["timed_successes"] == row["successes"]
                    else None,
                    "attempts": row["attempts"],
                    "calls": sum(item["n"] for item in nodes.values())
                    if nodes and calls_complete
                    else None,
                    "target_tokens": usage["tokens"] if usage_complete else None,
                    "elapsed_s": max((finished - started).total_seconds(), 0.0),
                }
            )
        for run_id, cost in by_run.items():
            if run_id not in incomplete_usage:
                cost["target_tokens"] = token_totals[run_id]
        return by_run

    # ── Attack builder drafts ─────────────────────────────────────────────────

    def save_builder_draft(
        self,
        name: str,
        canvas: Dict[str, Any],
        draft_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or update a dashboard attack-builder draft canvas.

        Args:
            name: User-facing draft name.
            canvas: Canvas dict (node layout plus the underlying config).
            draft_id: Existing draft id to overwrite; a new one is created
                when omitted or unknown.

        Returns:
            The stored draft as ``{id, name, canvas, created_at, updated_at}``.
        """
        now = _now_str()
        canvas_json = json.dumps(canvas)
        with self._lock:
            row = None
            if draft_id:
                row = self._conn.execute(
                    "SELECT created_at FROM attack_builder_drafts WHERE id=? LIMIT 1",
                    (draft_id,),
                ).fetchone()
            if row:
                created_at = row["created_at"]
                self._conn.execute(
                    "UPDATE attack_builder_drafts SET name=?, canvas_json=?, updated_at=? WHERE id=?",
                    (name, canvas_json, now, draft_id),
                )
            else:
                draft_id = draft_id or str(uuid.uuid4())
                created_at = now
                self._conn.execute(
                    "INSERT INTO attack_builder_drafts (id, name, canvas_json, created_at, updated_at) VALUES (?,?,?,?,?)",
                    (draft_id, name, canvas_json, now, now),
                )
            self._conn.commit()
        return {
            "id": draft_id,
            "name": name,
            "canvas": canvas,
            "created_at": created_at,
            "updated_at": now,
        }

    def list_builder_drafts(self) -> List[Dict[str, Any]]:
        """Return all saved builder drafts, most recently updated first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM attack_builder_drafts ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_draft(r) for r in rows]

    def get_builder_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Return one draft by id, or None if it does not exist."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM attack_builder_drafts WHERE id=? LIMIT 1",
                (draft_id,),
            ).fetchone()
        return self._row_to_draft(row) if row else None

    def delete_builder_draft(self, draft_id: str) -> None:
        """Delete a draft by id. No-op if it does not exist."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM attack_builder_drafts WHERE id=?", (draft_id,)
            )
            self._conn.commit()

    @staticmethod
    def _row_to_draft(row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "canvas": json.loads(row["canvas_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
