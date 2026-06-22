# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Trace classification and evaluation-trace synthesis.

Provides ``DashboardTraceAnalysisMixin`` for ``DashboardPage``. It inspects raw
trace records and prepares them for display, sitting between the storage layer
and the trace-rendering mixins.

Responsibilities:
    - Classify each trace step into a phase/kind (``_classify_trace_step``).
    - Detect harmful-evaluation traces and, when an evaluation trace is missing
      or incomplete, synthesise/repair its request/response pair so the UI can
      still show a verdict.
    - Load attack-specific traces for a goal.

The produced structures are consumed by ``DashboardTraceRenderMixin`` and
``DashboardTapTraceMixin`` for the actual rendering.
"""

from __future__ import annotations

from uuid import UUID

from nicegui import ui


from ._helpers import (
    _result_bucket,
    _serialize,
)
from .attack_cards import GenericCardMixin


class DashboardTraceAnalysisMixin:
    """Trace classification and evaluation-trace synthesis."""

    @staticmethod
    def _classify_trace_step(trace_data: dict) -> tuple[str, str]:
        """Classify a trace step into a semantic group and human label."""
        step_type = (trace_data.get("step_type") or "").upper()
        content = trace_data.get("content")

        if "GOAL" in step_type:
            return "goal", "Goal"
        if "EVALUATION" in step_type:
            return "evaluation", "Evaluation"
        if "TOOL" in step_type:
            return "tools", "Tools"
        if "TAP" in step_type or "DEPTH" in step_type or "ATTACK" in step_type:
            return "generation", "Attack / Generation"

        if isinstance(content, dict):
            step_name = str(content.get("step_name") or "").strip().lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )
            nested_result = (
                content.get("result") if isinstance(content.get("result"), dict) else {}
            )
            display_type = str(metadata.get("display_type") or "").strip().lower()
            _, response_value = GenericCardMixin._extract_request_response_candidates(
                content
            )
            has_target_response = response_value not in (None, "")
            if isinstance(response_value, str):
                has_target_response = response_value.strip().lower() not in {
                    "(response not available)",
                    "response not available",
                }

            def _has_eval_columns(source: dict) -> bool:
                return any(str(k).startswith("eval_") for k in source.keys())

            has_eval_columns = any(
                _has_eval_columns(source)
                for source in (content, metadata, nested_result)
                if isinstance(source, dict)
            )

            has_harm_judge_signal = has_eval_columns or any(
                source.get(key) is not None
                for source in (content, metadata, nested_result)
                if isinstance(source, dict)
                for key in (
                    "judge_score",
                    "best_score",
                    "judge_success",
                    "success",
                    "evaluation_status",
                    "explanation",
                    "scorer_explanation",
                )
            )

            on_topic_only = (
                metadata.get("on_topic_score") is not None
                and content.get("judge_score") is None
                and metadata.get("judge_score") is None
                and nested_result.get("judge_score") is None
                and not has_eval_columns
            )

            # TAP candidate traces carry per-candidate judge scores in metadata.
            # Surface them under Evaluation so users can inspect each scored prompt.
            if step_name.startswith("depth") and "candidate" in step_name:
                if on_topic_only:
                    return "generation", "Attack / Generation"
                if has_target_response and has_harm_judge_signal:
                    return "evaluation", "Evaluation"
                return "generation", "Attack / Generation"
            if (
                step_name in {"evaluation", "judge", "scoring"}
                or step_name.startswith("evaluation")
                or display_type == "bon_evaluation"
            ):
                return "evaluation", "Evaluation"
            if (
                "goal" in content
                and "request" not in content
                and "response" not in content
            ):
                return "goal", "Goal"
            if any(
                key in content
                for key in (
                    "judge_score",
                    "best_score",
                    "success",
                    "judge_model",
                    "evaluator",
                    "explanation",
                )
            ):
                return "evaluation", "Evaluation"
            # Prefix/completion judged by a model are evaluation payloads.
            if "prefix" in content and "completion" in content:
                return "evaluation", "Evaluation"
            if any(
                key in content
                for key in (
                    "attack_type",
                    "request",
                    "response",
                    "depth",
                    "width",
                    "iteration",
                    "improvement",
                )
            ):
                return "generation", "Attack / Generation"

        if step_type:
            return "other", step_type.replace("_", " ").title()
        return "other", "Other"

    @staticmethod
    def _is_harmful_evaluation_trace(trace_data: dict) -> bool:
        """Return True if an evaluation trace indicates harmful/successful outcome."""
        content = trace_data.get("content")
        if not isinstance(content, dict):
            return False

        nested_result = (
            content.get("result") if isinstance(content.get("result"), dict) else {}
        )
        metadata = (
            content.get("metadata") if isinstance(content.get("metadata"), dict) else {}
        )
        response_payload = (
            content.get("response") if isinstance(content.get("response"), dict) else {}
        )

        def _as_bool_harmful_marker(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value > 0
            if isinstance(value, str):
                token = value.strip().lower()
                if token in {
                    "1",
                    "1.0",
                    "true",
                    "yes",
                    "y",
                    "harmful",
                    "unsafe",
                    "jailbreak",
                    "successful_jailbreak",
                    "1_violating",
                }:
                    return True
            return False

        def _contains_harmful_text(value: object) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            negative_phrases = (
                "not harmful",
                "non harmful",
                "harmless",
                "safe",
                "not unsafe",
                "no jailbreak",
            )
            if any(phrase in text for phrase in negative_phrases):
                return False
            return any(token in text for token in ("harmful", "unsafe", "jailbreak"))

        explanation = str(content.get("explanation") or "").lower()
        if not explanation and nested_result:
            explanation = str(nested_result.get("explanation") or "").lower()
        if _contains_harmful_text(explanation):
            return True

        success = content.get("success")
        if success is None:
            success = content.get("is_success")
        if success is None and nested_result:
            success = nested_result.get("success")
        if success is None and nested_result:
            success = nested_result.get("is_success")
        if success is None and metadata:
            success = metadata.get("success")
        if success is None and metadata:
            success = metadata.get("is_jailbreak")
        if _as_bool_harmful_marker(success):
            return True

        eval_status = str(
            content.get("evaluation_status")
            or nested_result.get("evaluation_status")
            or ""
        ).upper()
        if "SUCCESSFUL_JAILBREAK" in eval_status:
            return True

        judge_columns = (
            metadata.get("judge_columns")
            if isinstance(metadata.get("judge_columns"), dict)
            else {}
        )
        response_judge_columns = (
            response_payload.get("judge_columns")
            if isinstance(response_payload.get("judge_columns"), dict)
            else {}
        )

        for source in (
            content,
            nested_result,
            metadata,
            judge_columns,
            response_judge_columns,
        ):
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                if key.startswith("eval_"):
                    if _as_bool_harmful_marker(value):
                        return True

        for source in (content, nested_result, metadata):
            if not isinstance(source, dict):
                continue
            for key in ("explanation", "scorer_explanation", "evaluation_notes"):
                if _contains_harmful_text(source.get(key)):
                    return True

        return False

    @staticmethod
    def _build_synthetic_evaluation_trace(result: dict) -> dict | None:
        """Build a fallback evaluation trace from result fields when none exists."""
        eval_status = str(result.get("evaluation_status") or "")
        eval_notes = result.get("evaluation_notes")
        metrics = result.get("evaluation_metrics")
        metadata = result.get("metadata")

        has_eval_payload = bool(eval_status or eval_notes or metrics)
        if not has_eval_payload:
            return None

        metrics_dict = metrics if isinstance(metrics, dict) else {}
        metadata_dict = metadata if isinstance(metadata, dict) else {}

        request_value = (
            metadata_dict.get("request")
            or metadata_dict.get("request_payload")
            or metadata_dict.get("prompt")
            or metadata_dict.get("prefix")
        )
        response_value = (
            metadata_dict.get("response")
            or metadata_dict.get("response_body")
            or metadata_dict.get("completion")
            or metadata_dict.get("raw_response_body")
        )

        best_score = metrics_dict.get("best_score")
        if best_score is None:
            best_score = metadata_dict.get("best_score")

        bucket = _result_bucket(eval_status, eval_notes)
        success = bucket == "jailbreak"

        content = {
            "step_name": "Evaluation",
            "evaluation_status": eval_status,
            "success": success,
            "explanation": eval_notes,
            "judge_score": best_score,
            "request": request_value,
            "response": response_value,
            "metadata": metrics_dict or metadata_dict,
        }

        return {
            "id": str(result.get("id") or "synthetic-evaluation"),
            "result_id": result.get("id"),
            "sequence": 1,
            "step_type": "EVALUATION",
            "content": content,
            "created_at": result.get("updated_at") or result.get("created_at"),
        }

    def _ensure_evaluation_request_response(
        self, serialized_traces: list[dict], result: dict
    ) -> list[dict]:
        """Inject Request/Response in evaluation traces so they are always visible."""

        def _trace_locators(content: object) -> dict[str, object]:
            if not isinstance(content, dict):
                return {}
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )
            return {
                "branch_index": metadata.get(
                    "branch_index", content.get("branch_index")
                ),
                "stream_index": metadata.get(
                    "stream_index", content.get("stream_index")
                ),
                "iteration": metadata.get("iteration", content.get("iteration")),
            }

        # Gather all traces that already carry usable request/response payloads.
        payload_sources: list[dict[str, object]] = []
        for td in serialized_traces:
            req, resp = self._extract_request_response_candidates(td.get("content"))
            if req in (None, "") and resp in (None, ""):
                continue
            payload_sources.append(
                {
                    "sequence": int(td.get("sequence") or 0),
                    "request": req,
                    "response": resp,
                    **_trace_locators(td.get("content")),
                }
            )

        fallback_request = None
        fallback_response = None
        if payload_sources:
            # Prefer the latest observed payload as global fallback.
            last_payload = max(
                payload_sources, key=lambda p: int(p.get("sequence") or 0)
            )
            fallback_request = last_payload.get("request")
            fallback_response = last_payload.get("response")

        # Fall back to result-level metadata/payload.
        result_meta = (
            result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        )
        if fallback_request in (None, ""):
            fallback_request = (
                result_meta.get("request")
                or result_meta.get("request_payload")
                or result_meta.get("prompt")
                or result_meta.get("prefix")
                or result.get("goal")
            )
        if fallback_response in (None, ""):
            fallback_response = (
                result_meta.get("response")
                or result_meta.get("response_body")
                or result_meta.get("completion")
                or result_meta.get("answer")
                or result_meta.get("raw_response_body")
            )

        # Hard guarantee: keep blocks visible even when upstream payload is incomplete.
        if fallback_request in (None, ""):
            fallback_request = "(request not available)"
        if fallback_response in (None, ""):
            fallback_response = "(response not available)"

        for td in serialized_traces:
            group, _ = self._classify_trace_step(td)
            if group != "evaluation":
                continue
            content = td.get("content")
            if not isinstance(content, dict):
                content = {"value": content}
                td["content"] = content

            if content.get("request") not in (None, "") and content.get(
                "response"
            ) not in (
                None,
                "",
            ):
                continue

            current_seq = int(td.get("sequence") or 0)
            current_loc = _trace_locators(content)

            matched_payload = None

            # 1) Strongest match: same branch+stream and closest previous sequence.
            branch_value = current_loc.get("branch_index")
            stream_value = current_loc.get("stream_index")
            if branch_value is not None and stream_value is not None:
                same_branch_stream = [
                    p
                    for p in payload_sources
                    if p.get("branch_index") == branch_value
                    and p.get("stream_index") == stream_value
                ]
                if same_branch_stream:
                    same_branch_stream.sort(
                        key=lambda p: (
                            abs(int(p.get("sequence") or 0) - current_seq),
                            int(p.get("sequence") or 0) > current_seq,
                        )
                    )
                    matched_payload = same_branch_stream[0]

            # 2) Next best: same iteration and closest sequence.
            if matched_payload is None and current_loc.get("iteration") is not None:
                same_iteration = [
                    p
                    for p in payload_sources
                    if p.get("iteration") == current_loc.get("iteration")
                ]
                if same_iteration:
                    same_iteration.sort(
                        key=lambda p: (
                            abs(int(p.get("sequence") or 0) - current_seq),
                            int(p.get("sequence") or 0) > current_seq,
                        )
                    )
                    matched_payload = same_iteration[0]

            # 3) Fallback: nearest previous payload by sequence.
            if matched_payload is None and payload_sources:
                previous = [
                    p
                    for p in payload_sources
                    if int(p.get("sequence") or 0) <= current_seq
                ]
                if previous:
                    matched_payload = max(
                        previous, key=lambda p: int(p.get("sequence") or 0)
                    )
                else:
                    matched_payload = min(
                        payload_sources,
                        key=lambda p: abs(int(p.get("sequence") or 0) - current_seq),
                    )

            if content.get("request") in (None, ""):
                content["request"] = (
                    matched_payload.get("request")
                    if isinstance(matched_payload, dict)
                    and matched_payload.get("request") not in (None, "")
                    else fallback_request
                )
            if content.get("response") in (None, ""):
                content["response"] = (
                    matched_payload.get("response")
                    if isinstance(matched_payload, dict)
                    and matched_payload.get("response") not in (None, "")
                    else fallback_response
                )

        return serialized_traces

    async def _load_attack_specific_traces(
        self, row: dict, container: ui.column, attack_str: str
    ) -> None:
        """Load traces and render attack-specific goal card in detail_mode=True."""
        try:
            result_id = row.get("id")
            if not result_id:
                container.clear()
                with container:
                    ui.label("No result ID available.").classes("text-sm text-grey-6")
                return

            traces_raw = self.backend.list_traces(result_id=UUID(result_id))
            serialized_traces = [_serialize(t) for t in traces_raw]

            container.clear()
            atk = attack_str.lower()

            with container:
                if atk == "baseline":
                    detail_data = self._parse_baseline_traces(
                        serialized_traces, str(row.get("goal") or "")
                    )
                    self._render_baseline_goal_card(row, detail_data, detail_mode=True)
                elif atk == "bon":
                    detail_data = self._parse_bon_traces(serialized_traces)
                    self._render_bon_goal_card(row, detail_data, detail_mode=True)
                elif atk == "pap":
                    detail_data = self._parse_pap_traces(serialized_traces)
                    self._render_pap_goal_card(row, detail_data, detail_mode=True)
                elif atk == "pair":
                    detail_data = self._parse_pair_traces(serialized_traces)
                    self._render_pair_goal_card(row, detail_data, detail_mode=True)
                elif atk == "tap":
                    nodes, depth_stats = self._parse_tap_traces(serialized_traces)
                    self._render_tap_goal_card(
                        row, nodes, depth_stats, detail_mode=True
                    )
                elif atk == "advprefix":
                    prefix_rows, gen_stats = self._parse_advprefix_traces(
                        serialized_traces
                    )
                    self._render_advprefix_goal_card(
                        row, prefix_rows, gen_stats, detail_mode=True
                    )
                elif atk == "autodanturbo":
                    detail_data = self._parse_autodan_traces(serialized_traces)
                    self._render_autodan_goal_card(row, detail_data, detail_mode=True)
                elif atk == "mml":
                    detail_data = self._parse_mml_traces(serialized_traces)
                    self._render_mml_goal_card(row, detail_data, detail_mode=True)
                elif atk in ("fc", "tfc"):
                    if atk == "fc":
                        detail_data = self._parse_fc_traces(serialized_traces)
                        self._render_fc_goal_card(row, detail_data, detail_mode=True)
                    else:
                        detail_data = self._parse_tfc_traces(serialized_traces)
                        self._render_tfc_goal_card(row, detail_data, detail_mode=True)
                else:
                    req_text, resp_text, _generic_guardrail = (
                        self._extract_prompt_response_from_traces(serialized_traces)
                    )
                    self._render_generic_goal_card(
                        row,
                        req_text,
                        resp_text,
                        detail_mode=True,
                        guardrail_event=_generic_guardrail,
                    )

        except Exception as exc:
            container.clear()
            with container:
                with ui.row().classes("gap-2 items-center py-4"):
                    ui.icon("error_outline", color="negative")
                    ui.label(f"Error loading traces: {exc}").classes(
                        "text-sm text-negative"
                    )
