# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""LocalBackend: the :class:`~hackagent.storage.store.Store` backed by SQLite.

Used when the local backend is selected (the default; see
:attr:`hackagent.core.settings.Settings.mode`). All data is persisted in
``~/.local/share/hackagent/hackagent.db`` unless another path is given, with
a stable schema that the TUI, the web dashboard and the SDK all read. Besides
the Store protocol it keeps per-goal tallies and a revision counter per
campaign run, updated in the transaction of every write, so the reporting
reads (``report_*``) never recount results.

Thread safety: a per-instance lock serialises access to the one connection,
so goal-batch workers may write concurrently.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from hackagent.reporting import (
    TERMINAL_STATUSES,
    AttackRun,
    Attempt,
    CampaignRun,
    FirstSuccess,
    GoalOutcome,
    GoalTotal,
    GoalUsage,
    Latency,
    ResultRow,
    StructureResult,
    StructureTrace,
    TraceCoverage,
    TraceRow,
    add_trace,
    goal_outcome,
    goal_usage,
    result_bucket,
    trace_coverage,
    trace_flags,
)
from hackagent.reporting.tallies import usage_label
from hackagent.storage.records import (
    AgentRecord,
    AttackRecord,
    CampaignRecord,
    CampaignRunRecord,
    OrganizationContext,
    PaginatedResult,
    ResultRecord,
    RunRecord,
    TraceRecord,
    canonical_attack_type,
)

logger = logging.getLogger("hackagent.storage.local")

_DEFAULT_DB_PATH = "~/.local/share/hackagent/hackagent.db"

#: ``PRAGMA user_version`` once the per-goal tallies cover every result. A
#: database written before them has its tallies computed when it is opened.
_TALLY_VERSION = 1


def _json_number(column: str, path: str) -> str:
    """SQL for the JSON value at ``path`` of ``column`` when it is a number,
    else NULL, as :mod:`hackagent.reporting` reads numbers."""
    return (
        f"CASE WHEN json_type({column}, '{path}') IN ('integer', 'real') "
        f"THEN json_extract({column}, '{path}') END"
    )


#: The light columns of :class:`hackagent.reporting.ResultRow`.
_RESULT_ROW = f"""r.id, r.run_id, r.goal_index, r.goal, r.evaluation_status,
    r.evaluation_notes, r.created_at, r.updated_at,
    json_extract(r.metadata_json, '$.category') AS category,
    json_extract(r.metadata_json, '$.subcategory') AS subcategory,
    {_json_number("r.metadata_json", "$.attack_metadata.goal_active_target_elapsed_s")}
        AS active_elapsed_s"""

#: The light columns of :class:`hackagent.reporting.TraceRow`.
_TRACE_ROW = f"""t.result_id, t.step_type,
    json_extract(t.content_json, '$.node') AS node,
    json_extract(t.content_json, '$.label') AS label,
    json_extract(t.content_json, '$.scope') AS scope,
    COALESCE({_json_number("t.content_json", "$.data.usage.prompt_tokens")},
             {_json_number("t.content_json", "$.response.usage.prompt_tokens")})
        AS prompt_tokens,
    COALESCE({_json_number("t.content_json", "$.data.usage.completion_tokens")},
             {_json_number("t.content_json", "$.response.usage.completion_tokens")})
        AS completion_tokens"""

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

CREATE TABLE IF NOT EXISTS campaigns (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    spec_json   TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_runs (
    id                   TEXT PRIMARY KEY,
    agent_id             TEXT NOT NULL REFERENCES agents(id),
    campaign_id          TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    launched             INTEGER NOT NULL DEFAULT 0,
    name                 TEXT NOT NULL,
    campaign_config_json TEXT NOT NULL DEFAULT '{}',
    audit_json           TEXT,
    status               TEXT NOT NULL DEFAULT 'PENDING',
    run_notes            TEXT,
    revision             INTEGER NOT NULL DEFAULT 0,
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

-- Per-goal tallies (hackagent.reporting.tallies), kept on every write.
CREATE TABLE IF NOT EXISTS goal_outcomes (
    campaign_run_id         TEXT,
    run_id                  TEXT NOT NULL,
    goal_index              INTEGER NOT NULL,
    goal                    TEXT NOT NULL,
    category                TEXT NOT NULL,
    subcategory             TEXT NOT NULL,
    attempts                INTEGER NOT NULL,
    jailbreak               INTEGER NOT NULL,
    mitigated               INTEGER NOT NULL,
    error                   INTEGER NOT NULL,
    pending                 INTEGER NOT NULL,
    first_jailbreak_attempt INTEGER,
    min_jailbreak_elapsed_s REAL,
    timed_jailbreaks        INTEGER NOT NULL,
    first_created_at        TEXT NOT NULL,
    last_updated_at         TEXT NOT NULL,
    labelled_call_attempts  INTEGER NOT NULL,
    target_call_attempts    INTEGER NOT NULL,
    interaction_attempts    INTEGER NOT NULL,
    PRIMARY KEY (run_id, goal_index)
);

CREATE TABLE IF NOT EXISTS goal_usage (
    campaign_run_id   TEXT,
    run_id            TEXT NOT NULL,
    goal_index        INTEGER NOT NULL,
    label             TEXT NOT NULL,
    calls             INTEGER NOT NULL,
    goal_scoped_calls INTEGER NOT NULL,
    prompt_tokens     INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    usage_calls       INTEGER NOT NULL,
    PRIMARY KEY (run_id, goal_index, label)
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
CREATE INDEX IF NOT EXISTS idx_traces_result_sequence
    ON traces(result_id, sequence);
CREATE INDEX IF NOT EXISTS idx_goal_outcomes_campaign
    ON goal_outcomes(campaign_run_id, run_id, goal_index);
CREATE INDEX IF NOT EXISTS idx_goal_usage_campaign
    ON goal_usage(campaign_run_id, run_id, goal_index);
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


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _label(value: Any) -> Optional[str]:
    return None if value is None or value == "" else str(value)


def _result_row(row: sqlite3.Row) -> ResultRow:
    return ResultRow(
        id=row["id"],
        goal=row["goal"] or "",
        evaluation_status=row["evaluation_status"],
        evaluation_notes=row["evaluation_notes"],
        category=_label(row["category"]),
        subcategory=_label(row["subcategory"]),
        active_elapsed_s=row["active_elapsed_s"],
        created_at=_to_dt(row["created_at"]),
        updated_at=_to_dt(row["updated_at"]),
    )


def _trace_row(row: sqlite3.Row) -> TraceRow:
    return TraceRow(
        result_id=row["result_id"],
        step_type=row["step_type"],
        node=_label(row["node"]),
        label=_label(row["label"]),
        scope=_label(row["scope"]),
        prompt_tokens=None
        if row["prompt_tokens"] is None
        else int(row["prompt_tokens"]),
        completion_tokens=None
        if row["completion_tokens"] is None
        else int(row["completion_tokens"]),
    )


def _row_to_outcome(row: sqlite3.Row) -> GoalOutcome:
    return GoalOutcome(
        campaign_run_id=row["campaign_run_id"],
        run_id=row["run_id"],
        goal_index=row["goal_index"],
        goal=row["goal"],
        category=row["category"],
        subcategory=row["subcategory"],
        attempts=row["attempts"],
        jailbreak=row["jailbreak"],
        mitigated=row["mitigated"],
        error=row["error"],
        pending=row["pending"],
        first_jailbreak_attempt=row["first_jailbreak_attempt"],
        min_jailbreak_elapsed_s=row["min_jailbreak_elapsed_s"],
        timed_jailbreaks=row["timed_jailbreaks"],
        first_created_at=_to_dt(row["first_created_at"]),
        last_updated_at=_to_dt(row["last_updated_at"]),
        labelled_call_attempts=row["labelled_call_attempts"],
        target_call_attempts=row["target_call_attempts"],
        interaction_attempts=row["interaction_attempts"],
    )


def _row_to_usage(row: sqlite3.Row) -> GoalUsage:
    return GoalUsage(
        campaign_run_id=row["campaign_run_id"],
        run_id=row["run_id"],
        goal_index=row["goal_index"],
        label=row["label"],
        calls=row["calls"],
        goal_scoped_calls=row["goal_scoped_calls"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        usage_calls=row["usage_calls"],
    )


def _marks(values: List[Any]) -> str:
    return ",".join("?" for _ in values)


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
        columns = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(campaign_runs)").fetchall()
        }
        if "campaign_id" not in columns:
            self._conn.execute(
                "ALTER TABLE campaign_runs ADD COLUMN campaign_id TEXT "
                "REFERENCES campaigns(id) ON DELETE SET NULL"
            )
        if "launched" not in columns:
            self._conn.execute(
                "ALTER TABLE campaign_runs ADD COLUMN launched INTEGER NOT NULL "
                "DEFAULT 0"
            )
            # Until now only a dashboard launch linked a run to a campaign.
            self._conn.execute(
                "UPDATE campaign_runs SET launched=1 WHERE campaign_id IS NOT NULL"
            )
        if "revision" not in columns:
            self._conn.execute(
                "ALTER TABLE campaign_runs ADD COLUMN revision INTEGER NOT NULL "
                "DEFAULT 0"
            )
        self._conn.execute("DROP INDEX IF EXISTS idx_traces_result")
        if self._conn.execute("PRAGMA user_version").fetchone()[0] < _TALLY_VERSION:
            self._rebuild_tallies()
            self._conn.execute(f"PRAGMA user_version = {_TALLY_VERSION}")

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Call this when the backend is no longer needed to release the file lock.
        Particularly important on Windows where open file handles prevent
        temporary directory cleanup.
        """
        self._conn.close()

    def flush(self) -> None:
        """No-op: local writes are synchronous (mirrors RemoteBackend.flush)."""

    # ── Context ──────────────────────────────────────────────────────────────

    def get_api_key(self) -> Optional[str]:
        """Return None: local storage has no API key."""
        return None

    def get_context(self) -> OrganizationContext:
        """Return the local organization context, creating it on first use.

        The organization id is generated once and kept in the database, so every
        record written by this database shares it. ``user_id`` is ``"local"``.
        """
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
        """Insert the agent ``name``, or replace the config of the existing one.

        Agent names are unique in the local database. ``agent_type`` and
        ``endpoint`` are taken from ``config["connection"]``.
        """
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
        """Return one page of agents, newest first."""
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
        """Return the agent ``agent_id``.

        Raises:
            RuntimeError: When no such agent exists.
        """
        ctx = self.get_context()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM agents WHERE id = ? LIMIT 1", (str(agent_id),)
            ).fetchone()
        if row:
            return self._row_to_agent(row, ctx.org_id)
        raise RuntimeError(f"LocalBackend: Agent {agent_id} not found")

    def delete_agent(self, agent_id: UUID) -> None:
        """Delete the agent row; a missing agent is not an error."""
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
        """Insert an attack row and return it."""
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
        """Return one page of attacks, newest first."""
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
        """Insert a RUNNING campaign run for ``spec``.

        The run is named after ``spec["campaign"]["name"]``, or ``"Campaign"``.
        """
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
        """Change the given fields of a campaign run and return it.

        ``None`` leaves a field unchanged. Every update counts as a new report
        revision of the campaign run.

        Raises:
            RuntimeError: When no such campaign run exists.
        """
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
            self._bump([str(campaign_run_id)])
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
        """Return one page of campaign runs, newest first."""
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
        """Return the campaign run ``campaign_run_id``.

        Raises:
            RuntimeError: When no such campaign run exists.
        """
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

    def link_campaign_run(self, campaign_run_id: UUID, campaign_id: UUID) -> None:
        """Record that the dashboard launched a campaign run, and from which
        saved campaign. The launch stays recorded if the campaign is deleted."""
        with self._lock:
            self._conn.execute(
                "UPDATE campaign_runs SET campaign_id=?, launched=1 WHERE id=?",
                (str(campaign_id), str(campaign_run_id)),
            )
            self._bump([str(campaign_run_id)])
            self._conn.commit()

    @staticmethod
    def _row_to_campaign_run(row: sqlite3.Row) -> CampaignRunRecord:
        campaign_id = row["campaign_id"]
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
            campaign_id=UUID(campaign_id) if campaign_id else None,
            launched=bool(row["launched"]),
        )

    # ── Saved campaign ────────────────────────────────────────────────────────

    def create_campaign(
        self, name: str, description: str, agent_id: UUID, spec: Dict[str, Any]
    ) -> CampaignRecord:
        """Save a dashboard campaign and return it."""
        campaign_id = uuid.uuid4()
        now = _now_str()
        with self._lock:
            self._conn.execute(
                "INSERT INTO campaigns "
                "(id, name, description, agent_id, spec_json, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    str(campaign_id),
                    name,
                    description,
                    str(agent_id),
                    json.dumps(spec),
                    now,
                    now,
                ),
            )
            self._conn.commit()
        return self.get_campaign(campaign_id)

    def update_campaign(
        self,
        campaign_id: UUID,
        name: str,
        description: str,
        agent_id: UUID,
        spec: Dict[str, Any],
    ) -> CampaignRecord:
        """Replace a saved campaign's name, description, agent and spec.

        Raises:
            RuntimeError: When no such campaign exists.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE campaigns SET name=?, description=?, agent_id=?, spec_json=?, "
                "updated_at=? WHERE id=?",
                (
                    name,
                    description,
                    str(agent_id),
                    json.dumps(spec),
                    _now_str(),
                    str(campaign_id),
                ),
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise RuntimeError(f"LocalBackend: Campaign {campaign_id} not found")
        return self.get_campaign(campaign_id)

    def get_campaign(self, campaign_id: UUID) -> CampaignRecord:
        """Return the saved campaign ``campaign_id``.

        Raises:
            RuntimeError: When no such campaign exists.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM campaigns WHERE id=? LIMIT 1", (str(campaign_id),)
            ).fetchone()
        if row is None:
            raise RuntimeError(f"LocalBackend: Campaign {campaign_id} not found")
        return self._row_to_campaign(row)

    def list_campaigns(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[CampaignRecord]:
        """Return one page of saved campaigns, most recently updated first."""
        offset = (page - 1) * page_size
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
            rows = self._conn.execute(
                "SELECT * FROM campaigns ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
        return PaginatedResult(
            items=[self._row_to_campaign(row) for row in rows], total=total
        )

    def delete_campaign(self, campaign_id: UUID) -> None:
        """Delete a saved campaign; the runs launched from it are kept, and
        their reports, which name the campaign, change."""
        with self._lock:
            self._bump(
                row["id"]
                for row in self._conn.execute(
                    "SELECT id FROM campaign_runs WHERE campaign_id=?",
                    (str(campaign_id),),
                )
            )
            cursor = self._conn.execute(
                "DELETE FROM campaigns WHERE id=?", (str(campaign_id),)
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise RuntimeError(f"LocalBackend: Campaign {campaign_id} not found")

    @staticmethod
    def _row_to_campaign(row: sqlite3.Row) -> CampaignRecord:
        return CampaignRecord(
            id=UUID(row["id"]),
            name=row["name"],
            description=row["description"],
            agent_id=UUID(row["agent_id"]),
            spec=json.loads(row["spec_json"] or "{}"),
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
        """Insert a PENDING attack run, linked to ``campaign_run_id`` if given.

        Unlike the remote backend, a run without a campaign run is allowed.
        """
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
            self._bump([str(campaign_run_id) if campaign_run_id else None])
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
        """Change the given fields of an attack run and return it.

        ``None`` leaves a field unchanged. When the run does not exist, a
        placeholder record carrying only the passed fields is returned.
        """
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
                self._bump([self._parent_of(str(run_id))])
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
        """Return one page of attack runs, newest first, optionally of one attack."""
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
        """Return the attack run ``run_id``.

        Raises:
            RuntimeError: When no such run exists.
        """
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

    def delete_campaign_run(self, campaign_run_id: UUID) -> None:
        """Delete one campaign run; see :meth:`delete_campaign_runs`."""
        self.delete_campaign_runs([campaign_run_id])

    def delete_campaign_runs(self, campaign_run_ids: List[UUID]) -> None:
        """Delete campaign runs with their attack runs, results, traces and tallies.

        All deletions happen in one transaction.

        Args:
            campaign_run_ids: The campaign runs to delete; duplicates are ignored.

        Raises:
            ValueError: When the list is empty, or a campaign run or one of its
                attack runs has not reached a final status.
            RuntimeError: When one of the campaign runs does not exist.
        """
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
                raise ValueError("An active campaign run cannot be deleted.")
            self._drop_tallies(f"campaign_run_id IN ({placeholders})", ids)
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
        """Delete an attack run with its results, traces and per-goal tallies."""
        sid = str(run_id)
        with self._lock:
            self._bump([self._parent_of(sid)])
            self._drop_tallies("id = ?", [sid])
            # traces → results → run
            self._conn.execute(
                "DELETE FROM traces WHERE result_id IN (SELECT id FROM results WHERE run_id = ?)",
                (sid,),
            )
            self._conn.execute("DELETE FROM results WHERE run_id = ?", (sid,))
            self._conn.execute("DELETE FROM runs WHERE id = ?", (sid,))
            self._conn.commit()

    def delete_attack(self, attack_id: UUID) -> None:
        """Delete an attack with its runs, results, traces and per-goal tallies."""
        sid = str(attack_id)
        with self._lock:
            self._bump(
                row["campaign_run_id"]
                for row in self._conn.execute(
                    "SELECT campaign_run_id FROM runs WHERE attack_id = ?", (sid,)
                )
            )
            self._drop_tallies("attack_id = ?", [sid])
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
        """Count all results by reporting bucket.

        Returns:
            A dict with the keys ``total``, ``jailbreaks``, ``mitigated``,
            ``error`` and ``pending``.
        """
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
        """Insert an unevaluated result and update its goal's tally.

        The returned record's metadata merges ``request_payload`` and
        ``agent_specific_data`` and keeps the payload under ``request_payload``.
        """
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
            self._refresh_outcome(str(run_id), goal_index)
            self._bump([self._parent_of(str(run_id))])
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
        """Change the given fields of a result and update its goal's tally.

        ``latency_ms`` and ``response_status_code`` have no columns locally and
        are merged into the metadata. When the result does not exist, a
        placeholder record carrying only the passed fields is returned.
        """
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
            row = self._conn.execute(
                "SELECT * FROM results WHERE id=? LIMIT 1", (str(result_id),)
            ).fetchone()
            if row:
                self._refresh_outcome(row["run_id"], row["goal_index"])
                self._bump([self._parent_of(row["run_id"])])
            self._conn.commit()
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
        """Return one page of results, newest first, optionally of one run."""
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
        """Return the result ``result_id``.

        Raises:
            RuntimeError: When no such result exists.
        """
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
        """Insert a trace step and add it to its goal's usage tally."""
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
            self._bump(
                [
                    self._count_trace(
                        str(trace_id),
                        TraceRow.from_content(str(result_id), step_type, content),
                    )
                ]
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
        """Return the trace steps of a result, ordered by ``sequence``."""
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

    # ── Per-goal tallies ──────────────────────────────────────────────────────
    # Kept by hackagent.reporting's functions in the transaction of every write
    # that changes them, so reports never recount results or scan traces.
    # These helpers run with the lock held and leave the commit to the caller.

    def _bump(self, campaign_run_ids: Iterable[Optional[str]]) -> None:
        """Count a write that changes what a campaign run's reports return."""
        ids = sorted({ident for ident in campaign_run_ids if ident})
        if ids:
            self._conn.execute(
                f"UPDATE campaign_runs SET revision = revision + 1 "
                f"WHERE id IN ({_marks(ids)})",
                ids,
            )

    def _parent_of(self, run_id: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT campaign_run_id FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        return row["campaign_run_id"] if row else None

    def _store_outcome(self, outcome: GoalOutcome) -> None:
        values = {
            "campaign_run_id": outcome.campaign_run_id,
            "run_id": outcome.run_id,
            "goal_index": outcome.goal_index,
            "goal": outcome.goal,
            "category": outcome.category,
            "subcategory": outcome.subcategory,
            "attempts": outcome.attempts,
            "jailbreak": outcome.jailbreak,
            "mitigated": outcome.mitigated,
            "error": outcome.error,
            "pending": outcome.pending,
            "first_jailbreak_attempt": outcome.first_jailbreak_attempt,
            "min_jailbreak_elapsed_s": outcome.min_jailbreak_elapsed_s,
            "timed_jailbreaks": outcome.timed_jailbreaks,
            "first_created_at": _iso(outcome.first_created_at),
            "last_updated_at": _iso(outcome.last_updated_at),
            "labelled_call_attempts": outcome.labelled_call_attempts,
            "target_call_attempts": outcome.target_call_attempts,
            "interaction_attempts": outcome.interaction_attempts,
        }
        self._conn.execute(
            f"INSERT OR REPLACE INTO goal_outcomes ({', '.join(values)}) "
            f"VALUES ({_marks(list(values))})",
            list(values.values()),
        )

    def _store_usage(self, usage: GoalUsage) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO goal_usage (campaign_run_id, run_id, goal_index, "
            "label, calls, goal_scoped_calls, prompt_tokens, completion_tokens, "
            "usage_calls) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                usage.campaign_run_id,
                usage.run_id,
                usage.goal_index,
                usage.label,
                usage.calls,
                usage.goal_scoped_calls,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.usage_calls,
            ),
        )

    def _goal_results(self, run_id: str, goal_index: int) -> List[ResultRow]:
        rows = self._conn.execute(
            f"SELECT {_RESULT_ROW} FROM results r WHERE r.run_id=? AND r.goal_index=?",
            (run_id, goal_index),
        ).fetchall()
        return [_result_row(row) for row in rows]

    def _refresh_outcome(self, run_id: str, goal_index: int) -> None:
        """Recompute a goal's outcome from its results, keeping its coverage."""
        stored = self._conn.execute(
            "SELECT * FROM goal_outcomes WHERE run_id=? AND goal_index=?",
            (run_id, goal_index),
        ).fetchone()
        outcome = goal_outcome(
            campaign_run_id=self._parent_of(run_id),
            run_id=run_id,
            goal_index=goal_index,
            results=self._goal_results(run_id, goal_index),
            coverage=_row_to_outcome(stored).coverage if stored else TraceCoverage(),
        )
        if outcome is not None:
            self._store_outcome(outcome)

    def _count_trace(self, trace_id: str, trace: TraceRow) -> Optional[str]:
        """Count a new trace step in its goal's tallies; returns the goal's
        campaign run."""
        owner = self._conn.execute(
            "SELECT r.run_id, r.goal_index FROM results r WHERE r.id=?",
            (trace.result_id,),
        ).fetchone()
        if owner is None:
            return None
        run_id, goal_index = owner["run_id"], owner["goal_index"]
        stored = self._conn.execute(
            "SELECT * FROM goal_outcomes WHERE run_id=? AND goal_index=?",
            (run_id, goal_index),
        ).fetchone()
        if stored is None:
            self._rebuild_goal(run_id, goal_index)
            return self._parent_of(run_id)
        earlier = self._conn.execute(
            f"SELECT {_TRACE_ROW} FROM traces t WHERE t.result_id=? AND t.id != ?",
            (trace.result_id, trace_id),
        ).fetchall()
        label = usage_label(trace)
        usage = (
            self._conn.execute(
                "SELECT * FROM goal_usage WHERE run_id=? AND goal_index=? AND label=?",
                (run_id, goal_index, label),
            ).fetchone()
            if label is not None
            else None
        )
        outcome, counted = add_trace(
            _row_to_outcome(stored),
            _row_to_usage(usage) if usage else None,
            trace,
            trace_flags(_trace_row(row) for row in earlier),
        )
        self._store_outcome(outcome)
        if counted is not None:
            self._store_usage(counted)
        return outcome.campaign_run_id

    def _rebuild_goal(self, run_id: str, goal_index: int) -> None:
        """Recompute both tallies of a goal from its results and traces."""
        self._conn.execute(
            "DELETE FROM goal_outcomes WHERE run_id=? AND goal_index=?",
            (run_id, goal_index),
        )
        self._conn.execute(
            "DELETE FROM goal_usage WHERE run_id=? AND goal_index=?",
            (run_id, goal_index),
        )
        traces = [
            _trace_row(row)
            for row in self._conn.execute(
                f"SELECT {_TRACE_ROW} FROM traces t JOIN results r ON r.id = t.result_id "
                "WHERE r.run_id=? AND r.goal_index=?",
                (run_id, goal_index),
            ).fetchall()
        ]
        self._store_goal(
            self._parent_of(run_id),
            run_id,
            goal_index,
            self._goal_results(run_id, goal_index),
            traces,
        )

    def _store_goal(
        self,
        campaign_run_id: Optional[str],
        run_id: str,
        goal_index: int,
        results: List[ResultRow],
        traces: List[TraceRow],
    ) -> None:
        outcome = goal_outcome(
            campaign_run_id=campaign_run_id,
            run_id=run_id,
            goal_index=goal_index,
            results=results,
            coverage=trace_coverage(traces),
        )
        if outcome is None:
            return
        self._store_outcome(outcome)
        for usage in goal_usage(
            campaign_run_id=campaign_run_id,
            run_id=run_id,
            goal_index=goal_index,
            traces=traces,
        ):
            self._store_usage(usage)

    def _rebuild_tallies(self) -> None:
        """Compute every goal's tallies, for a database written before them."""
        self._conn.execute("DELETE FROM goal_outcomes")
        self._conn.execute("DELETE FROM goal_usage")
        parents = {
            row["id"]: row["campaign_run_id"]
            for row in self._conn.execute("SELECT id, campaign_run_id FROM runs")
        }
        results: Dict[Tuple[str, int], List[ResultRow]] = {}
        goal_of: Dict[str, Tuple[str, int]] = {}
        for row in self._conn.execute(f"SELECT {_RESULT_ROW} FROM results r"):
            key = (row["run_id"], row["goal_index"])
            results.setdefault(key, []).append(_result_row(row))
            goal_of[row["id"]] = key
        traces: Dict[Tuple[str, int], List[TraceRow]] = {}
        for row in self._conn.execute(f"SELECT {_TRACE_ROW} FROM traces t"):
            goal = goal_of.get(row["result_id"])
            if goal is not None:
                traces.setdefault(goal, []).append(_trace_row(row))
        for (run_id, goal_index), rows in results.items():
            self._store_goal(
                parents.get(run_id),
                run_id,
                goal_index,
                rows,
                traces.get((run_id, goal_index), []),
            )

    def _drop_tallies(self, where: str, args: List[Any]) -> None:
        """Delete the tallies of the attack runs ``where`` selects in ``runs``."""
        for table in ("goal_outcomes", "goal_usage"):
            self._conn.execute(
                f"DELETE FROM {table} WHERE run_id IN (SELECT id FROM runs WHERE {where})",
                args,
            )

    # ── Campaign run reports ──────────────────────────────────────────────────
    # The rows hackagent.reporting builds the dashboard's campaign run routes
    # from. Light columns only; the tallies stand in for results and traces.

    _REPORT_RUN = """SELECT c.*, COALESCE(a.name, c.agent_id) AS target
        FROM campaign_runs c LEFT JOIN agents a ON a.id = c.agent_id"""

    @staticmethod
    def _row_to_report_run(row: sqlite3.Row) -> CampaignRun:
        updated_at = _to_dt(row["updated_at"])
        return CampaignRun(
            id=row["id"],
            name=row["name"],
            campaign=row["campaign_id"],
            agent=row["agent_id"],
            target=row["target"],
            status=row["status"],
            executor="local" if row["launched"] else "cli",
            created_at=_to_dt(row["created_at"]),
            updated_at=updated_at,
            finished_at=updated_at if row["status"] in TERMINAL_STATUSES else None,
            revision=row["revision"],
            configuration=json.loads(row["campaign_config_json"] or "{}"),
            audit=json.loads(row["audit_json"]) if row["audit_json"] else None,
            notes=row["run_notes"],
        )

    def report_campaign_runs(
        self,
        *,
        campaign: Optional[str] = None,
        agent: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[CampaignRun]:
        """Campaign runs, newest first (``created_at`` desc, then ``id``)."""
        clauses, args = [], []
        for column, value in (
            ("c.campaign_id", campaign),
            ("c.agent_id", agent),
            ("c.status", status),
        ):
            if value:
                clauses.append(f"{column}=?")
                args.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM campaign_runs c{where}", args
            ).fetchone()[0]
            rows = self._conn.execute(
                f"{self._REPORT_RUN}{where} ORDER BY c.created_at DESC, c.id "
                "LIMIT ? OFFSET ?",
                [*args, page_size, (page - 1) * page_size],
            ).fetchall()
        return PaginatedResult(
            items=[self._row_to_report_run(row) for row in rows], total=total
        )

    def report_campaign_run(self, campaign_run_id: str) -> Optional[CampaignRun]:
        """Return the campaign run ``campaign_run_id`` as a report row, or None."""
        with self._lock:
            row = self._conn.execute(
                f"{self._REPORT_RUN} WHERE c.id=?", (campaign_run_id,)
            ).fetchone()
        return self._row_to_report_run(row) if row else None

    def report_previous_candidates(self, current: CampaignRun) -> List[CampaignRun]:
        """The completed runs of ``current``'s campaign created up to it, newest
        first: a superset of its ``previous`` that the reporting rule narrows."""
        if current.campaign is not None:
            where, args = "c.campaign_id=?", [current.campaign]
        else:
            where = "c.campaign_id IS NULL AND c.agent_id=? AND c.name=?"
            args = [current.agent, current.name]
        with self._lock:
            rows = self._conn.execute(
                f"{self._REPORT_RUN} WHERE {where} AND c.status='COMPLETED' "
                "AND c.id != ? AND c.created_at <= ? "
                "ORDER BY c.created_at DESC, c.id DESC LIMIT 5",
                [*args, current.id, _iso(current.created_at)],
            ).fetchall()
        return [self._row_to_report_run(row) for row in rows]

    def report_revisions(self, campaign_run_ids: List[str]) -> Dict[str, int]:
        """The current revision of each campaign run that exists."""
        if not campaign_run_ids:
            return {}
        with self._lock:
            rows = self._conn.execute(
                f"SELECT id, revision FROM campaign_runs "
                f"WHERE id IN ({_marks(campaign_run_ids)})",
                campaign_run_ids,
            ).fetchall()
        return {row["id"]: row["revision"] for row in rows}

    def report_attack_runs(
        self, campaign_run_ids: List[str], *, full: bool = False
    ) -> List[AttackRun]:
        """The attack runs of campaign runs. Without ``full`` only id, parent,
        status and creation are read. With it, ``attack_configuration`` is the
        attack's stored configuration, unredacted, and ``family`` is unset:
        the caller completes both."""
        if not campaign_run_ids:
            return []
        columns = (
            "n.*, a.type AS technique, a.config_json AS attack_config_json"
            if full
            else "n.id, n.campaign_run_id, n.status, n.created_at"
        )
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {columns} FROM runs n LEFT JOIN attacks a ON a.id = n.attack_id "
                f"WHERE n.campaign_run_id IN ({_marks(campaign_run_ids)})",
                campaign_run_ids,
            ).fetchall()
        runs = []
        for row in rows:
            light = AttackRun(
                id=row["id"],
                campaign_run=row["campaign_run_id"],
                status=row["status"],
                created_at=_to_dt(row["created_at"]),
            )
            if full:
                light = AttackRun(
                    id=light.id,
                    campaign_run=light.campaign_run,
                    status=light.status,
                    created_at=light.created_at,
                    attack=row["attack_id"],
                    technique=canonical_attack_type(row["technique"])
                    if row["technique"] is not None
                    else "Unknown",
                    notes=row["run_notes"],
                    configuration=json.loads(row["config_json"] or "{}"),
                    attack_configuration=json.loads(row["attack_config_json"] or "{}")
                    if row["attack_config_json"] is not None
                    else None,
                )
            runs.append(light)
        return runs

    def report_goal_totals(self, campaign_run_ids: List[str]) -> List[GoalTotal]:
        """Return each goal's attempt and bucket totals per campaign run.

        Summed over the campaign run's attack runs, from the stored tallies.
        """
        if not campaign_run_ids:
            return []
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT campaign_run_id, goal_index, SUM(attempts) AS attempts,
                       SUM(jailbreak) AS jailbreak, SUM(mitigated) AS mitigated,
                       SUM(error) AS error, SUM(pending) AS pending
                    FROM goal_outcomes
                    WHERE campaign_run_id IN ({_marks(campaign_run_ids)})
                    GROUP BY campaign_run_id, goal_index""",
                campaign_run_ids,
            ).fetchall()
        return [
            GoalTotal(
                campaign_run=row["campaign_run_id"],
                goal_index=row["goal_index"],
                attempts=row["attempts"],
                jailbreak=row["jailbreak"],
                mitigated=row["mitigated"],
                error=row["error"],
                pending=row["pending"],
            )
            for row in rows
        ]

    def report_goal_outcomes(self, campaign_run_id: str) -> List[GoalOutcome]:
        """Return the per-goal outcome tallies of a campaign run's attack runs."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM goal_outcomes WHERE campaign_run_id=?",
                (campaign_run_id,),
            ).fetchall()
        return [_row_to_outcome(row) for row in rows]

    def report_goal_usage(self, campaign_run_id: str) -> List[GoalUsage]:
        """Return the per-goal call and token tallies of a campaign run.

        One row per attack run, goal and call label.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM goal_usage WHERE campaign_run_id=?", (campaign_run_id,)
            ).fetchall()
        return [_row_to_usage(row) for row in rows]

    def report_latencies(self, run_ids: List[str]) -> List[Latency]:
        """Return the distinct target latencies recorded per run.

        Each row is one run and latency (milliseconds) with how many results
        recorded it.
        """
        if not run_ids:
            return []
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT run_id, latency_ms, COUNT(*) AS count FROM (
                        SELECT run_id,
                            {_json_number("metadata_json", "$.latency_ms")} AS latency_ms
                        FROM results WHERE run_id IN ({_marks(run_ids)})
                    ) WHERE latency_ms IS NOT NULL GROUP BY run_id, latency_ms""",
                run_ids,
            ).fetchall()
        return [
            Latency(
                run_id=row["run_id"], latency_ms=row["latency_ms"], count=row["count"]
            )
            for row in rows
        ]

    def report_attempts(
        self, run_ids: List[str], goal_index: int, *, page: int, page_size: int
    ) -> Tuple[List[Attempt], int, Optional[FirstSuccess]]:
        """One page of a goal's attempts in ``created_at``, ``id`` order, their
        count, and the first jailbreak with its position."""
        if not run_ids:
            return [], 0, None
        where = f"run_id IN ({_marks(run_ids)}) AND goal_index=?"
        args: List[Any] = [*run_ids, goal_index]
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM results WHERE {where}", args
            ).fetchone()[0]
            rows = self._conn.execute(
                f"""SELECT id, run_id, evaluation_status, evaluation_notes, created_at
                    FROM results WHERE {where} ORDER BY created_at, id
                    LIMIT ? OFFSET ?""",
                [*args, page_size, (page - 1) * page_size],
            ).fetchall()
            first = self._conn.execute(
                f"""SELECT id, created_at FROM results WHERE {where}
                    AND result_bucket(evaluation_status, evaluation_notes)='jailbreak'
                    ORDER BY created_at, id LIMIT 1""",
                args,
            ).fetchone()
            success = None
            if first:
                position = self._conn.execute(
                    f"""SELECT COUNT(*) FROM results WHERE {where}
                        AND (created_at < ? OR (created_at = ? AND id <= ?))""",
                    [*args, first["created_at"], first["created_at"], first["id"]],
                ).fetchone()[0]
                success = FirstSuccess(id=first["id"], position=position)
        attempts = [
            Attempt(
                id=row["id"],
                run_id=row["run_id"],
                bucket=result_bucket(row["evaluation_status"], row["evaluation_notes"]),
                notes=row["evaluation_notes"],
                created_at=_to_dt(row["created_at"]),
            )
            for row in rows
        ]
        return attempts, total, success

    def report_structure(
        self, run_id: str, goal_index: int
    ) -> Tuple[List[StructureResult], List[StructureTrace]]:
        """Every attempt of a goal in one attack run, in full, and their traces."""
        with self._lock:
            results = self._conn.execute(
                "SELECT * FROM results WHERE run_id=? AND goal_index=?",
                (run_id, goal_index),
            ).fetchall()
            traces = self._conn.execute(
                """SELECT t.* FROM traces t JOIN results r ON r.id = t.result_id
                   WHERE r.run_id=? AND r.goal_index=?""",
                (run_id, goal_index),
            ).fetchall()
        return (
            [
                StructureResult(
                    id=row["id"],
                    run_id=row["run_id"],
                    evaluation_status=row["evaluation_status"],
                    evaluation_notes=row["evaluation_notes"],
                    request_payload=json.loads(row["request_payload_json"] or "{}"),
                    agent_specific_data=json.loads(row["metadata_json"] or "{}"),
                    created_at=_to_dt(row["created_at"]),
                )
                for row in results
            ],
            [
                StructureTrace(
                    id=row["id"],
                    result_id=row["result_id"],
                    sequence=row["sequence"],
                    step_type=row["step_type"],
                    content=json.loads(row["content_json"] or "{}"),
                    timestamp=_to_dt(row["created_at"]),
                )
                for row in traces
            ],
        )

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
