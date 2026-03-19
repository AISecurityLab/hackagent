# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""REST API route registration for the HackAgent dashboard."""

from __future__ import annotations

from nicegui import app as _fastapi_app

from ._helpers import _serialize


def register_api(backend) -> None:
    """Register all ``/api/*`` FastAPI routes on the NiceGUI application."""

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
        runs_p = backend.list_runs(page=1, page_size=200)
        total_results = jailbreaks = passed = errors = not_evaluated = 0
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
        risk_pct = (
            round(100 * jailbreaks / max(total_results, 1)) if total_results else 0
        )
        return {
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
            rp = backend.list_results(run_id=run.id, page=1, page_size=500)
            d["total_results"] = rp.total
            d["successful_jailbreaks"] = sum(
                1
                for r in rp.items
                if "SUCCESSFUL_JAILBREAK" in r.evaluation_status.upper()
            )
            items.append(d)
        return {"items": items, "total": result.total}
