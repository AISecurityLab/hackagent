# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TAP tree-of-attacks trace rendering.

Provides ``DashboardTapTraceMixin`` for ``DashboardPage``. The TAP (Tree of
Attacks with Pruning) technique produces a branching search tree rather than a
linear trace, so it needs a bespoke viewer.

Responsibilities:
    - Detect a TAP trace set and build the in-memory tree from the flat trace
      records (``_build_tap_stream_trees``).
    - Render the interactive tree view, including node colouring, recursive
      node rendering, click handling and the per-node detail panels.

Tree styling/sort helpers are kept local to this mixin.
"""

from __future__ import annotations

from collections import defaultdict
import contextlib
import json

from nicegui import ui


from .attack_cards import AttackCardSharedMixin


class DashboardTapTraceMixin:
    """TAP tree-of-attacks trace rendering."""

    @staticmethod
    def _is_tap_trace_set(traces: list[dict]) -> bool:
        """Return True when trace payload matches TAP candidate/summary format."""
        for td in traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue

            step_name = str(content.get("step_name") or "").strip().lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )

            if (
                step_name.startswith("depth")
                and "candidate" in step_name
                and metadata.get("self_id")
            ):
                return True

            branches = content.get("branches")
            if isinstance(branches, list):
                for branch in branches:
                    if isinstance(branch, dict) and branch.get("self_id"):
                        return True

        return False

    @staticmethod
    def _tap_tree_style_block() -> str:
        return """
<style>
.tap-tree-root {
  width: 100%;
}
.tap-tree-node {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
  transition: transform 120ms ease, box-shadow 120ms ease;
}
.tap-tree-node:hover {
  transform: scale(1.08);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}
.tap-tree-node-selected {
  box-shadow: 0 0 0 3px #3b82f6;
}
.tap-tree-node-black {
  background: #111827;
}
.tap-tree-node-red {
  background: #dc2626;
}
.tap-tree-node-green {
  background: #16a34a;
}
.tap-tree-vline {
  width: 2px;
  background: #6b7280;
}
.tap-tree-hline {
  height: 2px;
  background: #6b7280;
}
</style>
"""

    @staticmethod
    def _tap_node_color_class(node: dict) -> str:
        """Color sink nodes by verdict; all others are black."""
        children = node.get("children", [])
        is_leaf = not children
        if not is_leaf:
            return "tap-tree-node-black"

        if node.get("synthetic_pruned") or node.get("pruned_on_topic"):
            return "tap-tree-node-black"

        if node.get("has_judge_signal"):
            score = node.get("judge_score")
            try:
                numeric = float(score)
            except Exception:
                numeric = 0.0
            return "tap-tree-node-red" if numeric >= 1.0 else "tap-tree-node-green"

        return "tap-tree-node-black"

    @staticmethod
    def _tap_node_sort_key(node: dict) -> tuple[int, int, str]:
        depth = node.get("depth") if isinstance(node.get("depth"), int) else 0
        branch_index = (
            node.get("branch_index")
            if isinstance(node.get("branch_index"), int)
            else 999
        )
        return depth, branch_index, str(node.get("self_id") or "")

    @staticmethod
    def _build_tap_stream_trees(
        traces: list[dict],
    ) -> tuple[dict[int, list[dict]], int, int]:
        """Build per-stream TAP trees from candidate and depth-summary traces."""
        nodes_by_id: dict[str, dict] = {}
        max_depth = 0
        width_hint = 0

        def _clean_text(value: object) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, (dict, list)):
                try:
                    return json.dumps(value, ensure_ascii=True)
                except Exception:
                    return str(value)
            return str(value)

        def _to_int(value: object, default: int = 0) -> int:
            if isinstance(value, int):
                return value
            try:
                return int(value)  # type: ignore[arg-type]
            except Exception:
                return default

        def _has_value(value: object) -> bool:
            return value not in (None, "")

        def _upsert_node(raw: dict, trace_data: dict, inferred_depth: int = 0) -> None:
            nonlocal max_depth, width_hint
            self_id = raw.get("self_id")
            if not self_id:
                return

            stream_index = raw.get("stream_index")
            if not isinstance(stream_index, int):
                return

            depth = _to_int(raw.get("iteration"), 0)
            if depth <= 0:
                depth = _to_int(raw.get("depth"), inferred_depth)
            if depth <= 0:
                depth = 1
            max_depth = max(max_depth, depth)

            branch_index = raw.get("branch_index")
            if isinstance(branch_index, int):
                width_hint = max(width_hint, branch_index + 1)

            prompt_value = raw.get("prompt")
            if isinstance(prompt_value, dict):
                prompt_value = (
                    prompt_value.get("prompt")
                    or prompt_value.get("request")
                    or prompt_value
                )
            prompt = _clean_text(prompt_value)

            response_value = raw.get("response")
            # Detect guardrail-blocked responses before converting to text
            _node_g_side = ""
            _node_g_expl = ""
            _node_g_cats: list = []
            if isinstance(response_value, dict) and (
                response_value.get("adapter_type") == "guardrail"
                or response_value.get("side") in ("before", "after", "unknown")
            ):
                _, _node_g_side, _node_g_expl, _node_g_cats = (
                    AttackCardSharedMixin._extract_guardrail_from_response(
                        response_value
                    )
                )
                response_text = ""
                target_present = True
            else:
                response_text = _clean_text(response_value)
                target_present = "response" in raw

            judge_score = raw.get("judge_score")
            has_judge_signal = (
                "judge_score" in raw and raw.get("judge_score") is not None
            )

            node = nodes_by_id.get(str(self_id))
            if node is None:
                node = {
                    "self_id": str(self_id),
                    "parent_id": raw.get("parent_id"),
                    "stream_index": stream_index,
                    "depth": depth,
                    "branch_index": branch_index,
                    "prompt": prompt,
                    "improvement": _clean_text(raw.get("improvement")),
                    "on_topic_score": raw.get("on_topic_score"),
                    "target_response": response_text,
                    "target_present": target_present,
                    "judge_score": judge_score,
                    "has_judge_signal": has_judge_signal,
                    "pruned_on_topic": False,
                    "synthetic_pruned": False,
                    "_guardrail_side": _node_g_side,
                    "_guardrail_explanation": _node_g_expl,
                    "_guardrail_categories": _node_g_cats,
                    "children": [],
                    "trace_data": trace_data,
                }
                nodes_by_id[str(self_id)] = node
                return

            # Merge richer values from another payload (candidate/summary).
            if node.get("parent_id") in (None, "") and _has_value(raw.get("parent_id")):
                node["parent_id"] = raw.get("parent_id")
            if not isinstance(node.get("depth"), int) or node.get("depth", 0) <= 0:
                node["depth"] = depth
            if node.get("branch_index") is None and isinstance(branch_index, int):
                node["branch_index"] = branch_index
            if not _has_value(node.get("prompt")) and prompt:
                node["prompt"] = prompt
            if not _has_value(node.get("improvement")) and _has_value(
                raw.get("improvement")
            ):
                node["improvement"] = _clean_text(raw.get("improvement"))
            if (
                node.get("on_topic_score") is None
                and raw.get("on_topic_score") is not None
            ):
                node["on_topic_score"] = raw.get("on_topic_score")
            if not node.get("target_present") and target_present:
                node["target_present"] = True
                node["target_response"] = response_text
                if _node_g_side:
                    node["_guardrail_side"] = _node_g_side
                    node["_guardrail_explanation"] = _node_g_expl
                    node["_guardrail_categories"] = _node_g_cats
            elif not _has_value(node.get("target_response")) and response_text:
                node["target_response"] = response_text
            if not node.get("has_judge_signal") and has_judge_signal:
                node["has_judge_signal"] = True
                node["judge_score"] = judge_score
            elif node.get("judge_score") is None and judge_score is not None:
                node["judge_score"] = judge_score
            if node.get("trace_data") is None and trace_data is not None:
                node["trace_data"] = trace_data

        for td in traces:
            content = td.get("content")
            if not isinstance(content, dict):
                continue

            if isinstance(content.get("depth"), int):
                max_depth = max(max_depth, content.get("depth") or 0)
            if isinstance(content.get("width"), int):
                width_hint = max(width_hint, content.get("width") or 0)

            step_name = str(content.get("step_name") or "").strip().lower()
            metadata = (
                content.get("metadata")
                if isinstance(content.get("metadata"), dict)
                else {}
            )

            if step_name.startswith("depth") and "candidate" in step_name:
                request_payload = content.get("request")
                prompt_payload = request_payload
                if isinstance(request_payload, dict):
                    prompt_payload = (
                        request_payload.get("prompt")
                        or request_payload.get("request")
                        or request_payload
                    )
                raw_candidate = {
                    "self_id": metadata.get("self_id"),
                    "parent_id": metadata.get("parent_id"),
                    "stream_index": metadata.get("stream_index"),
                    "iteration": metadata.get("iteration"),
                    "branch_index": metadata.get("branch_index"),
                    "prompt": prompt_payload,
                    "improvement": metadata.get("improvement"),
                    "on_topic_score": metadata.get("on_topic_score"),
                    "response": content.get("response"),
                    "judge_score": metadata.get("judge_score"),
                }
                _upsert_node(
                    raw_candidate, td, inferred_depth=metadata.get("iteration") or 0
                )

            branches = content.get("branches")
            if isinstance(branches, list):
                for branch in branches:
                    if not isinstance(branch, dict):
                        continue
                    branch_payload = dict(branch)
                    if (
                        "response" not in branch_payload
                        and "target_response" in branch_payload
                    ):
                        branch_payload["response"] = branch_payload.get(
                            "target_response"
                        )
                    branch_depth = (
                        content.get("depth")
                        if isinstance(content.get("depth"), int)
                        else 0
                    )
                    if branch_depth > 0:
                        branch_payload.setdefault("depth", branch_depth)
                    _upsert_node(branch_payload, td, inferred_depth=branch_depth)

        # Link parent/child relations and build roots per stream.
        for node in nodes_by_id.values():
            node["children"] = []

        roots_by_stream: dict[int, list[dict]] = defaultdict(list)
        for node in nodes_by_id.values():
            parent_id = node.get("parent_id")
            if parent_id and str(parent_id) in nodes_by_id:
                parent = nodes_by_id[str(parent_id)]
                if parent.get("stream_index") == node.get("stream_index"):
                    parent["children"].append(node)
                    continue
            roots_by_stream[node.get("stream_index", 0)].append(node)

        def _sort_tree(curr: dict) -> None:
            curr["children"].sort(key=DashboardTapTraceMixin._tap_node_sort_key)
            for child in curr["children"]:
                _sort_tree(child)

        for stream_idx, roots in roots_by_stream.items():
            roots.sort(key=DashboardTapTraceMixin._tap_node_sort_key)
            for root in roots:
                _sort_tree(root)

        if max_depth <= 0:
            max_depth = 1
        if width_hint <= 0:
            width_hint = 1

        # Add synthetic sink nodes for pruned branches so dead ends are explicit.
        placeholder_seed = 0

        def _add_pruned_placeholders(curr: dict) -> None:
            nonlocal placeholder_seed
            if curr.get("synthetic_pruned"):
                return
            curr_depth = curr.get("depth") if isinstance(curr.get("depth"), int) else 1
            if curr_depth >= max_depth:
                return

            real_children = [
                c for c in curr.get("children", []) if not c.get("synthetic_pruned")
            ]
            missing = max(0, width_hint - len(real_children))
            for idx in range(missing):
                placeholder_seed += 1
                curr["children"].append(
                    {
                        "self_id": f"__tap_pruned_{placeholder_seed}",
                        "parent_id": curr.get("self_id"),
                        "stream_index": curr.get("stream_index"),
                        "depth": curr_depth + 1,
                        "branch_index": width_hint + idx,
                        "prompt": "",
                        "improvement": "",
                        "on_topic_score": None,
                        "target_response": "",
                        "target_present": False,
                        "judge_score": None,
                        "has_judge_signal": False,
                        "pruned_on_topic": False,
                        "synthetic_pruned": True,
                        "children": [],
                        "trace_data": None,
                    }
                )

            curr["children"].sort(key=DashboardTapTraceMixin._tap_node_sort_key)
            for child in real_children:
                _add_pruned_placeholders(child)

        for roots in roots_by_stream.values():
            for root in roots:
                _add_pruned_placeholders(root)

        # Mark on-topic pruning: no target, no judge, and failing on-topic score.
        def _mark_flags(curr: dict) -> None:
            on_topic_score = curr.get("on_topic_score")
            pruned_on_topic = (
                (on_topic_score in (0, False))
                and not curr.get("target_present")
                and not curr.get("has_judge_signal")
            )
            curr["pruned_on_topic"] = bool(pruned_on_topic)
            for child in curr.get("children", []):
                _mark_flags(child)

        for roots in roots_by_stream.values():
            for root in roots:
                _mark_flags(root)

        return dict(roots_by_stream), max_depth, width_hint

    def _render_tap_trace_tree_view(self, traces: list[dict]) -> None:
        """Render TAP traces as per-stream vertical trees with node drill-down."""
        trees_by_stream, max_depth, width_hint = self._build_tap_stream_trees(traces)
        if not trees_by_stream:
            ui.label("No TAP tree traces found for this goal.").classes(
                "text-sm text-grey-6"
            )
            return

        ui.html(self._tap_tree_style_block())

        with ui.row().classes("items-center gap-4 text-xs text-grey-6 pb-1"):
            ui.label(f"Depth: {max_depth}")
            ui.label(f"Width: {width_hint}")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("tap-tree-node tap-tree-node-red")
                ui.label("Sink harmful")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("tap-tree-node tap-tree-node-green")
                ui.label("Sink safe")
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("tap-tree-node tap-tree-node-black")
                ui.label("Intermediate / pruned")

        for stream_index in sorted(trees_by_stream.keys()):
            roots = trees_by_stream[stream_index]
            with ui.expansion(
                f"Stream {stream_index + 1}",
                icon="account_tree",
            ).classes("w-full") as stream_exp:
                stream_exp.props("default-opened")
                with ui.column().classes("w-full gap-4 p-2 tap-tree-root"):
                    selected_element: list[object | None] = [None]
                    detail_panel: list[object | None] = [None]

                    with ui.scroll_area().classes("w-full").style("max-height: 620px;"):
                        with ui.row().classes(
                            "w-full items-start justify-center gap-6"
                        ):
                            for root in roots:
                                self._render_tap_tree_node_recursive(
                                    root,
                                    detail_panel,
                                    selected_element,
                                )

                    ui.separator()

                    with ui.column().classes("w-full gap-2") as details:
                        with ui.row().classes("items-center gap-2 py-3 justify-center"):
                            ui.icon("ads_click").classes("text-grey-5")
                            ui.label(
                                "Click a node to inspect (stream, depth, width slot)"
                            ).classes("text-sm text-grey-5 italic")
                    detail_panel[0] = details

    def _render_tap_tree_node_recursive(
        self,
        node: dict,
        detail_panel: list[object | None],
        selected_element: list[object | None],
    ) -> None:
        """Render one TAP node and its subtree."""
        children = node.get("children", [])
        color_class = self._tap_node_color_class(node)

        depth = node.get("depth") if isinstance(node.get("depth"), int) else 0
        branch_index = node.get("branch_index")
        node_label = f"{depth}"
        if isinstance(branch_index, int):
            node_label = f"{depth}:{branch_index + 1}"

        with ui.column().classes("items-center gap-0"):
            circle = ui.element("div").classes(f"tap-tree-node {color_class}")
            with circle:
                ui.label(node_label).classes("text-[9px] font-bold text-white")

            circle.on(
                "click",
                lambda _evt, curr=node, el=circle: self._on_tap_tree_node_click(
                    curr,
                    detail_panel,
                    selected_element,
                    el,
                ),
            )

            if children:
                ui.element("div").classes("tap-tree-vline").style("height: 16px;")

                branch_width = max(42, len(children) * 52)
                ui.element("div").classes("tap-tree-hline").style(
                    f"width: {branch_width}px;"
                )

                with ui.row().classes("items-start justify-center gap-4"):
                    for child in children:
                        with ui.column().classes("items-center gap-0"):
                            ui.element("div").classes("tap-tree-vline").style(
                                "height: 14px;"
                            )
                            self._render_tap_tree_node_recursive(
                                child,
                                detail_panel,
                                selected_element,
                            )

    def _on_tap_tree_node_click(
        self,
        node: dict,
        detail_panel: list[object | None],
        selected_element: list[object | None],
        element: object,
    ) -> None:
        """Select node and render the requested TAP detail expansions."""
        previous = selected_element[0]
        if previous is not None:
            with contextlib.suppress(Exception):
                previous.classes(remove="tap-tree-node-selected")

        with contextlib.suppress(Exception):
            element.classes(add="tap-tree-node-selected")
        selected_element[0] = element

        details = detail_panel[0]
        if details is None:
            return
        details.clear()
        with details:
            self._render_tap_node_detail_panels(node)

    def _render_tap_node_detail_panels(self, node: dict) -> None:
        """Render node details with Attacker/On-Topic/Target/Judge expansions."""
        stream_index = node.get("stream_index")
        depth = node.get("depth")
        branch_index = node.get("branch_index")

        stream_label = stream_index + 1 if isinstance(stream_index, int) else "?"
        depth_label = depth if isinstance(depth, int) else "?"
        width_slot = branch_index + 1 if isinstance(branch_index, int) else "?"

        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label(
                    f"Stream {stream_label} · Depth {depth_label} · Width slot {width_slot}"
                ).classes("text-sm font-semibold")
                if node.get("synthetic_pruned"):
                    ui.badge("Pruned sink", color="grey-7").classes("text-xs")
                elif node.get("pruned_on_topic"):
                    ui.badge("Pruned by on-topic", color="grey-7").classes("text-xs")
                elif node.get("has_judge_signal"):
                    score = node.get("judge_score")
                    try:
                        harmful = float(score) >= 1.0
                    except Exception:
                        harmful = False
                    ui.badge(
                        "Harmful" if harmful else "Safe",
                        color="negative" if harmful else "positive",
                    ).classes("text-xs")
                else:
                    ui.badge("Intermediate", color="grey-7").classes("text-xs")

            with ui.expansion("Attacker", icon="smart_toy").classes("w-full"):
                with ui.column().classes("w-full gap-2 p-2"):
                    improvement = str(node.get("improvement") or "").strip()
                    prompt = str(node.get("prompt") or "")
                    if improvement:
                        with ui.card().tight().classes("w-full"):
                            with ui.column().classes("p-3 gap-1"):
                                ui.label("Improvement").classes(
                                    "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                                )
                                ui.label(improvement).classes(
                                    "text-sm whitespace-pre-wrap"
                                )
                    with ui.card().tight().classes("w-full"):
                        with ui.column().classes("p-3 gap-1"):
                            ui.label("Generated prompt").classes(
                                "text-[10px] font-semibold tracking-widest text-grey-5 uppercase"
                            )
                            ui.label(prompt or "(not available)").classes(
                                "text-sm whitespace-pre-wrap"
                            )

            with ui.expansion("On-Topic Judge", icon="rule").classes("w-full"):
                with ui.column().classes("w-full gap-2 p-2"):
                    on_topic_score = node.get("on_topic_score")
                    if on_topic_score is None:
                        ui.badge("No on-topic score", color="grey-7").classes("text-xs")
                    else:
                        is_on_topic = on_topic_score not in (0, False)
                        ui.badge(
                            f"Score: {on_topic_score}",
                            color="positive" if is_on_topic else "negative",
                        ).classes("text-xs")
                        ui.label(
                            "Classified as on-topic"
                            if is_on_topic
                            else "Classified as off-topic"
                        ).classes("text-sm")

            if node.get("pruned_on_topic"):
                with ui.card().tight().classes("w-full border border-grey-4 bg-grey-2"):
                    with ui.column().classes("p-3 gap-1"):
                        ui.label("Pruned after on-topic judge").classes(
                            "text-xs font-semibold"
                        )
                        ui.label(
                            "Target and Judge steps are intentionally hidden for this node."
                        ).classes("text-sm text-grey-7")
            else:
                with ui.expansion("Target", icon="ads_click").classes("w-full"):
                    with ui.column().classes("w-full gap-2 p-2"):
                        _g_side = node.get("_guardrail_side") or ""
                        if _g_side:
                            _g_expl = (
                                node.get("_guardrail_explanation")
                                or "Blocked by guardrail"
                            )
                            _g_cats = node.get("_guardrail_categories") or []
                            self._render_guardrail_event_block(
                                {
                                    "side": _g_side,
                                    "explanation": _g_expl,
                                    "categories": _g_cats,
                                }
                            )
                        elif node.get("target_present"):
                            response = str(node.get("target_response") or "")
                            if response:
                                ui.label(response).classes(
                                    "text-sm whitespace-pre-wrap"
                                )
                            else:
                                ui.label("(empty response)").classes(
                                    "text-sm text-grey-6 italic"
                                )
                        else:
                            ui.label("(target response not available)").classes(
                                "text-sm text-grey-6 italic"
                            )

                with ui.expansion("Judge", icon="gavel").classes("w-full"):
                    with ui.column().classes("w-full gap-2 p-2"):
                        if node.get("has_judge_signal"):
                            score = node.get("judge_score")
                            try:
                                harmful = float(score) >= 1.0
                            except Exception:
                                harmful = False
                            ui.badge(
                                f"Score: {score}",
                                color="negative" if harmful else "positive",
                            ).classes("text-xs")
                            ui.label("Harmful" if harmful else "Safe").classes(
                                "text-sm"
                            )
                        else:
                            ui.label("(judge result not available)").classes(
                                "text-sm text-grey-6 italic"
                            )

            with ui.expansion("Metadata", icon="info").classes("w-full"):
                trace_data = node.get("trace_data")
                content = (
                    trace_data.get("content") if isinstance(trace_data, dict) else {}
                )
                with ui.column().classes("w-full gap-1 p-2"):
                    ui.label(f"self_id: {node.get('self_id')}").classes("text-xs")
                    ui.label(f"parent_id: {node.get('parent_id')}").classes("text-xs")
                    ui.code(
                        json.dumps(content or {}, indent=2, default=str),
                        language="json",
                    ).classes("w-full text-xs max-h-64")
