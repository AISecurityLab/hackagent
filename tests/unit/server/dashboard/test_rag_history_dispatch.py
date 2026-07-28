# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the RAG/indirect-injection dispatch branches in the History and
Reports views.

These lock in the fix for a regression where History/Reports goal detail
dispatch dropped the ``rag`` (and legacy ``indirect_prompt_injection``) attack
type branch, silently falling back to the generic goal card and losing the
poisoning/query panel visualization.
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.server.dashboard import _trace_analysis_mixin
from hackagent.server.dashboard._reports_mixin import DashboardReportsMixin
from hackagent.server.dashboard._run_history_results_mixin import (
    DashboardRunHistoryResultsMixin,
)
from hackagent.server.dashboard._trace_analysis_mixin import (
    DashboardTraceAnalysisMixin,
)


class _ReportsPage(DashboardReportsMixin):
    """Minimal double exposing only what ``_render_history_goal_detail`` needs."""

    def __init__(self) -> None:
        self.rendered_indirect_injection_calls: list[tuple] = []

    def _render_indirect_injection_view(self, row, traces) -> None:
        self.rendered_indirect_injection_calls.append((row, traces))


class TestRenderHistoryGoalDetailDispatchesRag(unittest.TestCase):
    def test_rag_attack_type_uses_indirect_injection_view(self):
        page = _ReportsPage()
        row = {"id": "r1", "goal": "leak secrets"}
        traces = [{"content": {"step_name": "Document Poisoning"}}]

        page._render_history_goal_detail(row, traces, "rag")

        self.assertEqual(page.rendered_indirect_injection_calls, [(row, traces)])

    def test_legacy_indirect_prompt_injection_alias_uses_same_view(self):
        page = _ReportsPage()
        row = {"id": "r2", "goal": "leak secrets"}
        traces = [{"content": {"step_name": "RAG Query #1"}}]

        page._render_history_goal_detail(row, traces, "indirect_prompt_injection")

        self.assertEqual(page.rendered_indirect_injection_calls, [(row, traces)])

    def test_is_case_insensitive(self):
        page = _ReportsPage()
        row = {"id": "r3"}
        traces = []

        page._render_history_goal_detail(row, traces, "RAG")

        self.assertEqual(len(page.rendered_indirect_injection_calls), 1)


class _HistoryResultsPage(DashboardRunHistoryResultsMixin):
    """Minimal double for ``_build_history_goal_detail_data``."""


class TestBuildHistoryGoalDetailDataForRag(unittest.TestCase):
    def test_rag_keeps_raw_serialized_traces(self):
        page = _HistoryResultsPage()
        rows = [{"id": "res-1", "goal": "g1"}]
        generic_map = {"res-1": [{"content": {"step_name": "RAG Query #1"}}]}

        result = page._build_history_goal_detail_data("rag", rows, {}, {}, generic_map)

        self.assertEqual(result, {"res-1": generic_map["res-1"]})

    def test_legacy_alias_also_keeps_raw_traces(self):
        page = _HistoryResultsPage()
        rows = [{"id": "res-2"}]
        generic_map = {"res-2": [{"content": {"step_name": "Document Poisoning"}}]}

        result = page._build_history_goal_detail_data(
            "indirect_prompt_injection", rows, {}, {}, generic_map
        )

        self.assertEqual(result, {"res-2": generic_map["res-2"]})

    def test_missing_traces_default_to_empty_list(self):
        page = _HistoryResultsPage()
        rows = [{"id": "missing"}]

        result = page._build_history_goal_detail_data("rag", rows, {}, {}, {})

        self.assertEqual(result, {"missing": []})


class _TraceAnalysisPage(DashboardTraceAnalysisMixin):
    """Minimal double for ``_load_attack_specific_traces``."""

    def __init__(self, traces_by_result: dict) -> None:
        self._traces_by_result = traces_by_result
        self.backend = MagicMock()
        self.backend.list_traces.side_effect = lambda result_id: (
            self._traces_by_result.get(str(result_id), [])
        )
        self.rendered_indirect_injection_calls: list[tuple] = []

    def _render_indirect_injection_view(self, row, traces) -> None:
        self.rendered_indirect_injection_calls.append((row, traces))


class TestLoadAttackSpecificTracesDispatchesRag(unittest.TestCase):
    def test_rag_attack_renders_indirect_injection_view(self):
        result_id = uuid4()
        raw_trace = {"content": {"step_name": "RAG Query #1"}}
        page = _TraceAnalysisPage({str(result_id): [raw_trace]})
        row = {"id": str(result_id), "goal": "leak secrets"}
        container = MagicMock()

        with patch.object(_trace_analysis_mixin, "_serialize", lambda t: t):
            asyncio.run(page._load_attack_specific_traces(row, container, "rag"))

        self.assertEqual(page.rendered_indirect_injection_calls, [(row, [raw_trace])])

    def test_legacy_alias_renders_indirect_injection_view(self):
        result_id = uuid4()
        raw_trace = {"content": {"step_name": "Document Poisoning"}}
        page = _TraceAnalysisPage({str(result_id): [raw_trace]})
        row = {"id": str(result_id)}
        container = MagicMock()

        with patch.object(_trace_analysis_mixin, "_serialize", lambda t: t):
            asyncio.run(
                page._load_attack_specific_traces(
                    row, container, "indirect_prompt_injection"
                )
            )

        self.assertEqual(page.rendered_indirect_injection_calls, [(row, [raw_trace])])


if __name__ == "__main__":
    unittest.main()
