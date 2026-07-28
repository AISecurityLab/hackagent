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


class _AllParsersHistoryResultsPage(DashboardRunHistoryResultsMixin):
    """Double with a stub for every ``_parse_*_traces`` collaborator.

    Used to exercise *every* branch of ``_build_history_goal_detail_data``
    (not just the rag/indirect_prompt_injection one), since the method
    dispatches on attack type to sibling mixins normally composed onto the
    real dashboard page class.
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def _parse_static_template_traces(self, traces, goal=""):
        self.calls.append(("static_template", traces, goal))
        return "ST_RESULT"

    def _parse_bon_traces(self, traces):
        self.calls.append(("bon", traces))
        return "BON_RESULT"

    def _parse_pap_traces(self, traces):
        self.calls.append(("pap", traces))
        return "PAP_RESULT"

    def _parse_pair_traces(self, traces):
        self.calls.append(("pair", traces))
        return "PAIR_RESULT"

    def _parse_tap_traces(self, traces):
        self.calls.append(("tap", traces))
        return "TAP_RESULT"

    def _parse_advprefix_traces(self, traces):
        self.calls.append(("advprefix", traces))
        return "ADVPREFIX_RESULT"

    def _parse_autodan_traces(self, traces):
        self.calls.append(("autodan", traces))
        return "AUTODAN_RESULT"

    def _parse_mml_traces(self, traces):
        self.calls.append(("mml", traces))
        return "MML_RESULT"

    def _parse_fc_traces(self, traces):
        self.calls.append(("fc", traces))
        return "FC_RESULT"

    def _parse_tfc_traces(self, traces):
        self.calls.append(("tfc", traces))
        return "TFC_RESULT"

    def _extract_prompt_response_from_traces(self, traces):
        self.calls.append(("generic", traces))
        return ("req", "resp", None)


class TestBuildHistoryGoalDetailDataAllBranches(unittest.TestCase):
    """Covers every dispatch branch of ``_build_history_goal_detail_data``,
    not only the rag one, so the whole extracted method is exercised."""

    def setUp(self):
        self.rows = [{"id": "r1", "goal": "g1"}]
        self.static_template_map = {"r1": ["st-trace"]}
        self.bon_map = {"r1": ["bon-trace"]}
        self.generic_map = {"r1": ["generic-trace"]}

    def _build(self, attack_type_str):
        page = _AllParsersHistoryResultsPage()
        result = page._build_history_goal_detail_data(
            attack_type_str,
            self.rows,
            self.static_template_map,
            self.bon_map,
            self.generic_map,
        )
        return page, result

    def test_static_template(self):
        page, result = self._build("static_template")
        self.assertEqual(result, {"r1": "ST_RESULT"})
        self.assertEqual(page.calls, [("static_template", ["st-trace"], "g1")])

    def test_statictemplate_alias(self):
        page, result = self._build("statictemplate")
        self.assertEqual(result, {"r1": "ST_RESULT"})

    def test_bon(self):
        page, result = self._build("bon")
        self.assertEqual(result, {"r1": "BON_RESULT"})
        self.assertEqual(page.calls, [("bon", ["bon-trace"])])

    def test_pap(self):
        page, result = self._build("pap")
        self.assertEqual(result, {"r1": "PAP_RESULT"})
        self.assertEqual(page.calls, [("pap", ["generic-trace"])])

    def test_pair(self):
        page, result = self._build("pair")
        self.assertEqual(result, {"r1": "PAIR_RESULT"})

    def test_tap(self):
        page, result = self._build("tap")
        self.assertEqual(result, {"r1": "TAP_RESULT"})

    def test_advprefix(self):
        page, result = self._build("advprefix")
        self.assertEqual(result, {"r1": "ADVPREFIX_RESULT"})

    def test_autodanturbo(self):
        page, result = self._build("autodanturbo")
        self.assertEqual(result, {"r1": "AUTODAN_RESULT"})

    def test_mml(self):
        page, result = self._build("mml")
        self.assertEqual(result, {"r1": "MML_RESULT"})

    def test_fc(self):
        page, result = self._build("fc")
        self.assertEqual(result, {"r1": "FC_RESULT"})

    def test_tfc(self):
        page, result = self._build("tfc")
        self.assertEqual(result, {"r1": "TFC_RESULT"})

    def test_unknown_attack_type_falls_back_to_generic(self):
        page, result = self._build("some_unknown_attack")
        self.assertEqual(result, {"r1": ("req", "resp", None)})
        self.assertEqual(page.calls, [("generic", ["generic-trace"])])


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
