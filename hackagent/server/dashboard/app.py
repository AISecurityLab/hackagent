# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Community Edition Dashboard — Flask application factory.

Exposes a JSON REST API over the HackAgent storage backend and serves the
built-in SPA dashboard at ``/``.  Designed for zero-config local use: when no
API key is available the LocalBackend (SQLite) is used automatically.

Public API:
    create_app(backend=None, db_path=None) -> Flask
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from flask import Flask, jsonify, render_template, request


def _serialize(record) -> dict:
    """Convert a Pydantic v2 BaseModel record to a JSON-safe dict.

    Uses ``model_dump(mode='json')`` which natively converts UUID → str and
    datetime → ISO-8601 string.
    """
    return record.model_dump(mode="json")


def create_app(
    backend=None,
    db_path: Optional[str] = None,
) -> Flask:
    """Create and return the Flask dashboard application.

    Args:
        backend: Any ``StorageBackend``-compatible instance.  When *None* a
            fresh ``LocalBackend`` is created (pointing at the default SQLite
            path, or *db_path* if given).
        db_path: Optional override for the SQLite database file path.  Only
            used when *backend* is *None*.

    Returns:
        A configured Flask application ready to be ``run()`` or handed to a
        WSGI server.
    """
    templates_dir = Path(__file__).parent / "templates"
    app = Flask(__name__, template_folder=str(templates_dir))

    if backend is None:
        from hackagent.server.storage.local import LocalBackend

        backend = LocalBackend(db_path=db_path)

    # ── SPA ──────────────────────────────────────────────────────────────────

    @app.get("/")
    def index():
        return render_template("index.html")

    # ── API: Status ───────────────────────────────────────────────────────────

    @app.get("/api/status")
    def api_status():
        ctx = backend.get_context()
        db_path_str = (
            str(backend._db_path) if hasattr(backend, "_db_path") else None
        )
        return jsonify(
            {
                "status": "ok",
                "mode": "local" if backend.get_api_key() is None else "remote",
                "org_id": str(ctx.org_id),
                "user_id": ctx.user_id,
                "db_path": db_path_str,
            }
        )

    # ── API: Stats ────────────────────────────────────────────────────────────

    @app.get("/api/stats")
    def api_stats():
        agents_p = backend.list_agents(page=1, page_size=1)
        attacks_p = backend.list_attacks(page=1, page_size=1)
        runs_p = backend.list_runs(page=1, page_size=200)

        total_results = 0
        jailbreaks = 0
        passed = 0
        errors = 0
        not_evaluated = 0

        for run in runs_p.items:
            rp = backend.list_results(run_id=run.id, page=1, page_size=500)
            total_results += rp.total
            for r in rp.items:
                s = r.evaluation_status.upper()
                if "SUCCESSFUL_JAILBREAK" in s:
                    jailbreaks += 1
                elif "PASSED" in s:
                    passed += 1
                elif "ERROR" in s:
                    errors += 1
                elif "NOT_EVALUATED" in s:
                    not_evaluated += 1

        risk_pct = round(100 * jailbreaks / max(total_results, 1))
        return jsonify(
            {
                "total_agents": agents_p.total,
                "total_attacks": attacks_p.total,
                "total_runs": runs_p.total,
                "total_results": total_results,
                "successful_jailbreaks": jailbreaks,
                "passed": passed,
                "errors": errors,
                "not_evaluated": not_evaluated,
                "risk_percentage": risk_pct,
            }
        )

    # ── API: Agents ───────────────────────────────────────────────────────────

    @app.get("/api/agents")
    def api_agents():
        page = int(request.args.get("page", 1))
        page_size = min(int(request.args.get("page_size", 50)), 200)
        result = backend.list_agents(page=page, page_size=page_size)
        return jsonify(
            {
                "items": [_serialize(a) for a in result.items],
                "total": result.total,
                "page": page,
                "page_size": page_size,
            }
        )

    # ── API: Attacks ──────────────────────────────────────────────────────────

    @app.get("/api/attacks")
    def api_attacks():
        page = int(request.args.get("page", 1))
        page_size = min(int(request.args.get("page_size", 50)), 200)
        result = backend.list_attacks(page=page, page_size=page_size)
        return jsonify(
            {
                "items": [_serialize(a) for a in result.items],
                "total": result.total,
                "page": page,
                "page_size": page_size,
            }
        )

    # ── API: Runs ─────────────────────────────────────────────────────────────

    @app.get("/api/runs")
    def api_runs():
        page = int(request.args.get("page", 1))
        page_size = min(int(request.args.get("page_size", 20)), 200)
        attack_id_str = request.args.get("attack_id")
        attack_id = UUID(attack_id_str) if attack_id_str else None
        result = backend.list_runs(
            attack_id=attack_id, page=page, page_size=page_size
        )

        # Annotate each run with aggregated result counts
        items = []
        for run in result.items:
            d = _serialize(run)
            rp = backend.list_results(run_id=run.id, page=1, page_size=500)
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
            )
            items.append(d)

        return jsonify(
            {
                "items": items,
                "total": result.total,
                "page": page,
                "page_size": page_size,
            }
        )

    @app.get("/api/runs/<run_id>")
    def api_get_run(run_id: str):
        try:
            run = backend.get_run(UUID(run_id))
            return jsonify(_serialize(run))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404

    # ── API: Results ──────────────────────────────────────────────────────────

    @app.get("/api/results")
    def api_results():
        page = int(request.args.get("page", 1))
        page_size = min(int(request.args.get("page_size", 100)), 500)
        run_id_str = request.args.get("run_id")
        run_id = UUID(run_id_str) if run_id_str else None
        result = backend.list_results(run_id=run_id, page=page, page_size=page_size)
        return jsonify(
            {
                "items": [_serialize(r) for r in result.items],
                "total": result.total,
                "page": page,
                "page_size": page_size,
            }
        )

    # ── API: Traces ───────────────────────────────────────────────────────────

    @app.get("/api/traces")
    def api_traces():
        result_id_str = request.args.get("result_id")
        if not result_id_str:
            return jsonify({"error": "result_id is required"}), 400
        try:
            traces = backend.list_traces(result_id=UUID(result_id_str))
            return jsonify(
                {
                    "items": [_serialize(t) for t in traces],
                    "total": len(traces),
                }
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404

    return app
