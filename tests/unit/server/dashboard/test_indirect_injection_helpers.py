# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.server.dashboard._page import DashboardPage


class TestIsIndirectInjectionTraceSet(unittest.TestCase):
    def test_detects_document_poisoning(self):
        traces = [{"content": {"step_name": "Document Poisoning"}}]
        self.assertTrue(DashboardPage._is_indirect_injection_trace_set(traces))

    def test_detects_rag_query_step(self):
        traces = [{"content": {"step_name": "RAG Query #1"}}]
        self.assertTrue(DashboardPage._is_indirect_injection_trace_set(traces))

    def test_detects_attack_type(self):
        traces = [{"content": {"step_name": "x", "attack_type": "rag"}}]
        self.assertTrue(DashboardPage._is_indirect_injection_trace_set(traces))

    def test_detects_rag_judge_evaluator(self):
        traces = [{"content": {"step_name": "x", "evaluator": "rag_judge"}}]
        self.assertTrue(DashboardPage._is_indirect_injection_trace_set(traces))

    def test_returns_false_for_other_traces(self):
        traces = [{"content": {"step_name": "Iteration 1"}}, {"content": None}]
        self.assertFalse(DashboardPage._is_indirect_injection_trace_set(traces))


class TestIndirectQueryVerdictStyle(unittest.TestCase):
    def test_success(self):
        label, color, _ = DashboardPage._indirect_query_verdict_style("SUCCESS")
        self.assertEqual(label, "HARMFUL")
        self.assertEqual(color, "negative")

    def test_failure(self):
        label, color, _ = DashboardPage._indirect_query_verdict_style("failure")
        self.assertEqual(label, "SAFE")
        self.assertEqual(color, "positive")

    def test_inconclusive_default(self):
        label, color, _ = DashboardPage._indirect_query_verdict_style(None)
        self.assertEqual(label, "INCONCLUSIVE")
        self.assertEqual(color, "warning")


class TestCollectIndirectInjectionTraceData(unittest.TestCase):
    def test_collects_queries_and_poisonings(self):
        traces = [
            {
                "sequence": 1,
                "content": {
                    "step_name": "Document Poisoning",
                    "injected_payload": "evil text",
                    "query_anchor": "what is the policy",
                    "insertion_paragraph_index": 2,
                },
            },
            {
                "sequence": 2,
                "content": {
                    "step_name": "RAG Query #1",
                    "request": {"prompt": "What is the policy"},
                    "response": {"content": "Here is the answer"},
                    "metadata": {"query_index": 1},
                },
            },
            {
                "sequence": 3,
                "content": {
                    "step_name": "Evaluation",
                    "metadata": {"query_index": 1, "classification": "SUCCESS"},
                    "result": {"rationale": "model complied"},
                },
            },
        ]
        poisonings, panels = DashboardPage._collect_indirect_injection_trace_data(
            traces
        )
        self.assertEqual(len(poisonings), 1)
        self.assertEqual(len(panels), 1)
        panel = panels[0]
        self.assertEqual(panel["query"], "What is the policy")
        self.assertEqual(panel["response"], "Here is the answer")
        self.assertEqual(panel["classification"], "SUCCESS")
        self.assertEqual(panel["rationale"], "model complied")
        self.assertEqual(len(panel["poisonings"]), 1)

    def test_query_index_from_step_name(self):
        traces = [
            {
                "sequence": 1,
                "content": {
                    "step_name": "RAG Query #3",
                    "request": "raw query string",
                    "response": "raw response string",
                    "metadata": {},
                },
            }
        ]
        _, panels = DashboardPage._collect_indirect_injection_trace_data(traces)
        self.assertEqual(panels[0]["query_index"], 3)
        self.assertEqual(panels[0]["query"], "raw query string")
        self.assertEqual(panels[0]["response"], "raw response string")

    def test_single_panel_poisoning_fallback(self):
        traces = [
            {
                "sequence": 1,
                "content": {
                    "step_name": "Document Poisoning",
                    "injected_payload": "evil",
                    "query_anchor": "",
                },
            },
            {
                "sequence": 2,
                "content": {
                    "step_name": "RAG Query #1",
                    "request": {"prompt": "q"},
                    "response": {"content": "r"},
                    "metadata": {"query_index": 1},
                },
            },
        ]
        _, panels = DashboardPage._collect_indirect_injection_trace_data(traces)
        self.assertEqual(len(panels[0]["poisonings"]), 1)

    def test_ignores_non_dict_content(self):
        traces = [{"sequence": 1, "content": None}]
        poisonings, panels = DashboardPage._collect_indirect_injection_trace_data(
            traces
        )
        self.assertEqual(poisonings, [])
        self.assertEqual(panels, [])


if __name__ == "__main__":
    unittest.main()
