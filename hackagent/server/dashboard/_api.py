# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""REST API route registration for the HackAgent dashboard."""

from __future__ import annotations

from nicegui import app as _fastapi_app

from ._helpers import _result_bucket, _serialize

_DASHBOARD_RUN_SCAN_LIMIT = 10


def register_api(backend) -> None:
    """Register all ``/api/*`` FastAPI routes on the NiceGUI application."""

    def _derive_run_status(
        result_statuses: list[tuple[str, str | None]],
        observed_total_results: int,
        expected_total_goals: int | None = None,
        fallback: str = "",
    ) -> str:
        if (
            isinstance(expected_total_goals, int)
            and expected_total_goals > 0
            and observed_total_results < expected_total_goals
        ):
            fallback_status = str(fallback or "").upper()
            if fallback_status in {"FAILED", "CANCELLED"}:
                return fallback_status
            return "RUNNING"

        buckets = [_result_bucket(status=s, notes=n) for s, n in result_statuses]
        has_pending = any(b == "pending" for b in buckets)
        has_failed = any(b in {"failed", "error"} for b in buckets)
        if has_pending:
            return "RUNNING"
        if has_failed:
            return "FAILED"
        if buckets:
            return "COMPLETED"
        return fallback or "PENDING"

    def _extract_expected_total_goals(run_data: dict) -> int | None:
        run_cfg = run_data.get("run_config")
        if not isinstance(run_cfg, dict):
            return None

        candidates = (
            run_cfg.get("expected_total_goals"),
            run_cfg.get("expected_goal_count"),
            run_cfg.get("total_goals"),
            run_cfg.get("goal_count"),
        )
        for value in candidates:
            try:
                parsed = int(value)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                continue
        return None

    def _iter_run_results(run_id):
        """Yield all paginated results for a run."""
        page = 1
        page_size = 100
        fetched = 0
        total = 0

        while True:
            rp = backend.list_results(run_id=run_id, page=page, page_size=page_size)
            if page == 1:
                total = int(rp.total or 0)
            if not rp.items:
                break

            for result in rp.items:
                yield result

            fetched += len(rp.items)
            if total > 0 and fetched >= total:
                break
            page += 1

    @_fastapi_app.get("/api/status")
    async def api_status():
        ctx = backend.get_context()
        mode = "remote" if backend.get_api_key() else "local"
        return {
            "status": "ok",
            "mode": mode,
            "org_id": str(ctx.org_id),
            "user_id": ctx.user_id,
            "db_path": str(backend._db_path)
            if mode == "local" and hasattr(backend, "_db_path")
            else None,
        }

    @_fastapi_app.get("/api/stats")
    async def api_stats():
        agents_p = backend.list_agents(page=1, page_size=1)
        attacks_p = backend.list_attacks(page=1, page_size=1)
        runs_p = backend.list_runs(page=1, page_size=1)

        total_results = jailbreaks = mitigated = failed = not_evaluated = 0

        def _recompute_from_results() -> tuple[int, int, int, int, int]:
            _total = _jb = _mit = _fail = _pending = 0
            runs_scan = backend.list_runs(page=1, page_size=_DASHBOARD_RUN_SCAN_LIMIT)
            for run in runs_scan.items:
                run_total = 0
                for r in _iter_run_results(run.id):
                    run_total += 1
                    bucket = _result_bucket(r.evaluation_status, r.evaluation_notes)
                    if bucket == "jailbreak":
                        _jb += 1
                    elif bucket == "mitigated":
                        _mit += 1
                    elif bucket in {"failed", "error"}:
                        _fail += 1
                    elif bucket == "pending":
                        _pending += 1
                _total += run_total
            return _total, _jb, _mit, _fail, _pending

        try:
            bucket_counts = backend.count_result_buckets()
            total_results = int(bucket_counts.get("total", 0) or 0)
            jailbreaks = int(bucket_counts.get("jailbreaks", 0) or 0)
            mitigated = int(bucket_counts.get("mitigated", 0) or 0)
            failed = int(
                bucket_counts.get("failed", bucket_counts.get("error", 0)) or 0
            )
            not_evaluated = int(bucket_counts.get("pending", 0) or 0)

            accounted = jailbreaks + mitigated + failed + not_evaluated
            if total_results > 0 and accounted < total_results:
                (
                    total_results,
                    jailbreaks,
                    mitigated,
                    failed,
                    not_evaluated,
                ) = _recompute_from_results()
        except Exception:
            (
                total_results,
                jailbreaks,
                mitigated,
                failed,
                not_evaluated,
            ) = _recompute_from_results()
        risk_pct = (
            round(100 * jailbreaks / max(total_results, 1)) if total_results else 0
        )
        return {
            "total_agents": agents_p.total,
            "total_attacks": attacks_p.total,
            "total_runs": runs_p.total,
            "total_results": total_results,
            "successful_jailbreaks": jailbreaks,
            "jailbreaks": jailbreaks,
            "mitigations": mitigated,
            "failed_attacks": mitigated,
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
            result_statuses: list[tuple[str, str | None]] = []
            successful_jailbreaks = 0
            total_results = 0
            for r in _iter_run_results(run.id):
                total_results += 1
                bucket = _result_bucket(r.evaluation_status, r.evaluation_notes)
                if bucket == "jailbreak":
                    successful_jailbreaks += 1
                result_statuses.append((r.evaluation_status, r.evaluation_notes))

            expected_total_goals = _extract_expected_total_goals(d)
            d["total_results"] = total_results
            d["successful_jailbreaks"] = successful_jailbreaks
            d["expected_total_goals"] = expected_total_goals
            d["status"] = _derive_run_status(
                result_statuses,
                observed_total_results=total_results,
                expected_total_goals=expected_total_goals,
                fallback=str(d.get("status", "")),
            )
            items.append(d)
        return {"items": items, "total": result.total}
