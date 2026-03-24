# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""REST API route registration for the HackAgent dashboard."""

from __future__ import annotations

from nicegui import app as _fastapi_app

from ._helpers import _result_bucket, _serialize

_RESULTS_FETCH_LIMIT = 20
_DASHBOARD_RUN_SCAN_LIMIT = 10


def register_api(backend) -> None:
    """Register all ``/api/*`` FastAPI routes on the NiceGUI application."""

    def _derive_run_status(
        result_statuses: list[tuple[str, str | None]],
        fallback: str = "",
    ) -> str:
        buckets = [_result_bucket(status=s, notes=n) for s, n in result_statuses]
        has_pending = any(b == "pending" for b in buckets)
        has_failed = any(b == "failed" for b in buckets)
        if has_pending:
            return "RUNNING"
        if has_failed:
            return "FAILED"
        if buckets:
            return "COMPLETED"
        return fallback or "PENDING"

    @_fastapi_app.get("/api/status")
    async def api_status():
        ctx = backend.get_context()
        return {
            "status": "ok",
            "mode": "local" if backend.get_api_key() is None else "remote",
            "org_id": str(ctx.org_id),
            "user_id": ctx.user_id,
            "db_path": str(backend._db_path) if hasattr(backend, "_db_path") else None,
        }

    @_fastapi_app.get("/api/stats")
    async def api_stats():
        agents_p = backend.list_agents(page=1, page_size=1)
        attacks_p = backend.list_attacks(page=1, page_size=1)
        runs_p = backend.list_runs(page=1, page_size=_DASHBOARD_RUN_SCAN_LIMIT)
        total_results = jailbreaks = mitigated = failed = not_evaluated = 0
        for run in runs_p.items:
            rp = backend.list_results(
                run_id=run.id, page=1, page_size=_RESULTS_FETCH_LIMIT
            )
            total_results += rp.total
            for r in rp.items:
                bucket = _result_bucket(r.evaluation_status, r.evaluation_notes)
                if bucket == "jailbreak":
                    jailbreaks += 1
                elif bucket == "mitigated":
                    mitigated += 1
                elif bucket == "failed":
                    failed += 1
                elif bucket == "pending":
                    not_evaluated += 1
        risk_pct = (
            round(100 * jailbreaks / max(total_results, 1)) if total_results else 0
        )
        return {
            "total_agents": agents_p.total,
            "total_attacks": attacks_p.total,
            "total_runs": runs_p.total,
            "total_results": total_results,
            "successful_jailbreaks": jailbreaks,
            "passed": mitigated,
            "errors": failed,
            "not_evaluated": not_evaluated,
            "risk_percentage": risk_pct,
        }

    @_fastapi_app.get("/api/agents")
    async def api_agents():
        result = backend.list_agents(page=1, page_size=100)
        return {"items": [_serialize(a) for a in result.items], "total": result.total}

    @_fastapi_app.get("/api/attacks")
    async def api_attacks():
        result = backend.list_attacks(page=1, page_size=100)
        return {"items": [_serialize(a) for a in result.items], "total": result.total}

    @_fastapi_app.get("/api/runs")
    async def api_runs():
        result = backend.list_runs(page=1, page_size=50)
        items = []
        for run in result.items:
            d = _serialize(run)
            rp = backend.list_results(
                run_id=run.id, page=1, page_size=_RESULTS_FETCH_LIMIT
            )
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if _result_bucket(r.evaluation_status, r.evaluation_notes)
                == "jailbreak"
            )
            d["status"] = _derive_run_status(
                [(r.evaluation_status, r.evaluation_notes) for r in rp.items],
                fallback=str(d.get("status", "")),
            )
            items.append(d)
        return {"items": items, "total": result.total}
