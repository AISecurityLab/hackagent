# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A campaign run of 100k results and 300k traces reports in well under a second.

The data is inserted with plain SQL and its tallies computed the way an
existing database's are when it is opened, which is the slow part of the
test; the reads it times touch only the tallies. Each read is timed as the
best of a few, with coverage paused: its tracer and a busy CI runner would
otherwise be what gets measured.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from hackagent import HackAgent, Settings
from hackagent.interfaces.web import _static, create_app
from hackagent.storage.local import LocalBackend

ATTACK_RUNS = 5
GOALS = 2_000
ATTEMPTS = 10  # per attack run and goal: 5 * 2000 * 10 = 100k results
STEPS = 3  # per attempt: 300k traces
BUDGET_S = 1.0
TRIES = 3
CAMPAIGN = "c0000000-0000-4000-8000-000000000100"


@contextmanager
def _untraced():
    """Pause coverage, if it is measuring this test, for the timed reads."""
    try:
        import coverage
    except ImportError:
        cov = None
    else:
        cov = coverage.Coverage.current()
    if cov is None:
        yield
        return
    cov.stop()
    try:
        yield
    finally:
        cov.start()


def _best_time(client, path: str) -> float:
    best = float("inf")
    for _ in range(TRIES):
        start = time.perf_counter()
        response = client.get(path)
        best = min(best, time.perf_counter() - start)
        assert response.status_code == 200, path
    return best


def _seed(backend: LocalBackend) -> str:
    conn = backend._conn
    org = str(backend.get_context().org_id)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    conn.execute(
        "INSERT INTO agents (id, name, agent_type, organization_id, created_at, "
        "updated_at) VALUES ('agent', 'bot', 'OPENAI_SDK', ?, ?, ?)",
        (org, t0.isoformat(), t0.isoformat()),
    )
    conn.execute(
        "INSERT INTO attacks (id, type, agent_id, organization_id, created_at) "
        "VALUES ('attack', 'tap', 'agent', ?, ?)",
        (org, t0.isoformat()),
    )
    conn.execute(
        "INSERT INTO campaign_runs (id, agent_id, name, status, created_at, "
        "updated_at) VALUES (?, 'agent', 'Big', 'COMPLETED', ?, ?)",
        (CAMPAIGN, t0.isoformat(), t0.isoformat()),
    )
    statuses = ("SUCCESSFUL_JAILBREAK", "FAILED_JAILBREAK", "ERROR_AGENT_RESPONSE")
    results, traces = [], []
    for run in range(ATTACK_RUNS):
        run_id = f"e0000000-0000-4000-8000-{run:012d}"
        conn.execute(
            "INSERT INTO runs (id, campaign_run_id, attack_id, agent_id, status, "
            "created_at, updated_at) VALUES (?, ?, 'attack', 'agent', "
            "'COMPLETED', ?, ?)",
            (run_id, CAMPAIGN, t0.isoformat(), t0.isoformat()),
        )
        for goal in range(GOALS):
            for attempt in range(ATTEMPTS):
                result_id = f"{run_id}-{goal}-{attempt}"
                at = (t0 + timedelta(seconds=goal * ATTEMPTS + attempt)).isoformat()
                metadata = {
                    "category": f"Category {goal % 7}",
                    "subcategory": f"Sub {goal % 3}",
                    "latency_ms": 100 + attempt,
                    "response": "reply " * 40,
                }
                results.append(
                    (
                        result_id,
                        run_id,
                        f"Goal {goal}",
                        goal,
                        statuses[(goal + attempt + run) % 3],
                        json.dumps(metadata),
                        at,
                        at,
                    )
                )
                for step, label in enumerate(("attacker", "target", "panel")[:STEPS]):
                    traces.append(
                        (
                            f"{result_id}-{step}",
                            result_id,
                            step,
                            "TOOL_CALL",
                            json.dumps(
                                {
                                    "node": "call",
                                    "label": label,
                                    "data": {
                                        "usage": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                        }
                                    },
                                }
                            ),
                            at,
                        )
                    )
    conn.executemany(
        "INSERT INTO results (id, run_id, goal, goal_index, evaluation_status, "
        "metadata_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        results,
    )
    conn.executemany(
        "INSERT INTO traces (id, result_id, sequence, step_type, content_json, "
        "created_at) VALUES (?,?,?,?,?,?)",
        traces,
    )
    backend._rebuild_tallies()
    conn.commit()
    return CAMPAIGN


@pytest.mark.slow
def test_large_campaign_runs_report_in_well_under_a_second():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        bundle = root / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("<html>index</html>")
        real_static_dir = _static.static_dir
        _static.static_dir = lambda: bundle
        backend = LocalBackend(str(root / "big.db"))
        try:
            campaign = _seed(backend)
            session = HackAgent(
                Settings.resolve(
                    backend="local",
                    db_path=":memory:",
                    env={},
                    config_path="/nonexistent",
                ),
                backend=backend,
            )
            client = create_app(session).test_client()
            paths = (
                "/api/proxy/run/summary",
                f"/api/proxy/run/{campaign}/summary",
                f"/api/proxy/run/{campaign}/report",
                f"/api/proxy/run/{campaign}/matrix",
            )
            with _untraced():
                timings = {path: _best_time(client, path) for path in paths}
            summary = client.get(f"/api/proxy/run/{campaign}/summary").get_json()
            assert summary["attempts"] == ATTACK_RUNS * GOALS * ATTEMPTS
            assert summary["recorded_goals"] == GOALS
            slow = {path: f"{seconds:.3f}s" for path, seconds in timings.items()}
            assert all(seconds < BUDGET_S for seconds in timings.values()), slow
        finally:
            backend.close()
            _static.static_dir = real_static_dir
