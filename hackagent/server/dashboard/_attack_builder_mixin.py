# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack builder panel — assemble and launch an attack from the dashboard.

Provides ``DashboardAttackBuilderMixin``, the first place in
``hackagent/server/dashboard/`` where an attack is *launched* rather than
reviewed. It renders a small canvas of blocks that map 1:1 onto the config
sections the CLI already builds:

    Target block      → ``agent-name`` / ``agent-type`` / ``endpoint``
    Goals block       → ``goals`` list or a ``dataset`` section
    Attack block(s)   → one per ``ATTACK_CATALOG`` entry (drag from the palette)
    Guardrail blocks  → optional before/after, same three fields as the CLI

Two or more attack blocks form a fallback ladder and are submitted through
``HackAgent.hack_chain()``; a single block goes through ``HackAgent.hack()``.
The translation itself lives in :mod:`._builder_config` so it stays testable
without a browser.

Local vs remote: the builder always runs against the dashboard's own
``StorageBackend``. Since ``hackagent web`` redirects to the cloud dashboard
whenever an API key is configured, that backend is in practice the local
SQLite one, and submitted runs show up in the existing Runs/History/Reports
panels with no special-casing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from nicegui import ui

from ._builder_config import (
    AGENT_TYPES,
    CanvasValidationError,
    attack_label,
    attack_palette,
    build_run_payload,
    canvas_summary,
    new_canvas,
)

logger = logging.getLogger("hackagent.server.dashboard.builder")

_MAX_LOG_LINES = 300


class DashboardAttackBuilderMixin:
    """Canvas-style attack builder panel and its in-process run submission."""

    # ── Panel skeleton ────────────────────────────────────────────────────────

    def _build_builder_panel(self, panel: ui.column) -> None:
        with panel:
            with ui.row().classes("w-full items-start gap-4 flex-nowrap"):
                self._build_builder_palette()
                with ui.column().classes("flex-1 gap-4 min-w-0"):
                    self._build_builder_toolbar()
                    self._build_builder_target_card()
                    self._build_builder_goals_card()
                    self._build_builder_chain_card()
                    self._build_builder_guardrails_card()
                    self._build_builder_progress_card()
        self._builder_render_chain()

    def _build_builder_palette(self) -> None:
        with ui.card().classes("w-64 shrink-0"):
            ui.label("Attack palette").classes("font-semibold text-sm")
            ui.label("Drag onto the chain, or click to append.").classes(
                "text-xs text-grey-6 mb-2"
            )
            with ui.column().classes("w-full gap-2"):
                for entry in attack_palette():
                    attack_type = entry["attack_type"]
                    card = (
                        ui.card()
                        .classes("w-full p-2 cursor-grab hover:shadow-md")
                        .props('draggable="true"')
                    )
                    with card:
                        ui.label(entry["label"]).classes("text-sm font-medium")
                        ui.label(entry["description"]).classes(
                            "text-xs text-grey-6 whitespace-normal"
                        )
                    card.on(
                        "dragstart",
                        lambda _e, t=attack_type: self._builder_set_drag(t),
                    )
                    card.on(
                        "click", lambda _e, t=attack_type: self._builder_add_attack(t)
                    )

    def _build_builder_toolbar(self) -> None:
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                self._builder_name_input = (
                    ui.input("Draft name", value=self._builder_canvas["name"])
                    .props("dense outlined")
                    .classes("w-56")
                )
                self._builder_drafts_select = (
                    ui.select({}, label="Saved drafts")
                    .props("dense outlined")
                    .classes("w-56")
                )
                ui.button("Save draft", icon="save", on_click=self._builder_save_draft)
                ui.button(
                    "Open", icon="folder_open", on_click=self._builder_load_draft
                ).props("outline")
                ui.button(
                    "Delete", icon="delete", on_click=self._builder_delete_draft
                ).props("outline color=grey-7")
                ui.space()
                ui.button(
                    "Preview config", icon="code", on_click=self._builder_preview
                ).props("outline")
                self._builder_run_btn = ui.button(
                    "Run attack", icon="play_arrow", on_click=self._builder_run
                ).props("color=primary")

    def _build_builder_target_card(self) -> None:
        target = self._builder_canvas["target"]
        with ui.card().classes("w-full"):
            ui.label("Target").classes("font-semibold text-sm")
            with ui.row().classes("w-full gap-3 flex-wrap"):
                ui.input("Agent name", value=target["agent_name"]).props(
                    "dense outlined"
                ).classes("w-56").bind_value(target, "agent_name")
                ui.select(
                    AGENT_TYPES, label="Agent type", value=target["agent_type"]
                ).props("dense outlined").classes("w-48").bind_value(
                    target, "agent_type"
                )
                ui.input("Endpoint URL", value=target["endpoint"]).props(
                    "dense outlined"
                ).classes("flex-1 min-w-72").bind_value(target, "endpoint")
                ui.number("Timeout (s)", value=self._builder_canvas["timeout"]).props(
                    "dense outlined"
                ).classes("w-32").bind_value(self._builder_canvas, "timeout")

    def _build_builder_goals_card(self) -> None:
        goals_block = self._builder_canvas["goals"]
        with ui.card().classes("w-full"):
            ui.label("Goals / Dataset").classes("font-semibold text-sm")
            toggle = ui.toggle(
                {"goals": "Goal list", "dataset": "Dataset"},
                value=goals_block["mode"],
            ).props("dense no-caps")
            toggle.bind_value(goals_block, "mode")

            goals_area = ui.column().classes("w-full gap-2")
            goals_area.bind_visibility_from(goals_block, "mode", value="goals")
            with goals_area:
                self._builder_goals_text = (
                    ui.textarea(
                        "Goals (one per line)",
                        value="\n".join(goals_block.get("goals") or []),
                    )
                    .props("dense outlined autogrow")
                    .classes("w-full")
                )

            dataset = goals_block.setdefault("dataset", {})
            dataset_area = ui.row().classes("w-full gap-3 flex-wrap")
            dataset_area.bind_visibility_from(goals_block, "mode", value="dataset")
            with dataset_area:
                for label, key, width in (
                    ("Preset", "preset", "w-44"),
                    ("Provider", "provider", "w-40"),
                    ("Path / URL", "path", "w-64"),
                    ("Goal field", "goal_field", "w-40"),
                    ("Split", "split", "w-32"),
                ):
                    dataset.setdefault(key, "")
                    ui.input(label, value=dataset[key]).props("dense outlined").classes(
                        width
                    ).bind_value(dataset, key)
                dataset.setdefault("limit", None)
                ui.number("Limit", value=dataset["limit"]).props(
                    "dense outlined"
                ).classes("w-28").bind_value(dataset, "limit")

    def _build_builder_chain_card(self) -> None:
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Attack chain").classes("font-semibold text-sm")
                ui.label(
                    "Blocks run as a fallback ladder: a mitigated goal escalates "
                    "to the next block."
                ).classes("text-xs text-grey-6")
            drop_zone = ui.column().classes(
                "w-full gap-2 min-h-24 p-2 rounded border-2 border-dashed"
            )
            drop_zone.on("dragover.prevent", lambda _e: None)
            drop_zone.on("drop.prevent", lambda _e: self._builder_drop())
            self._builder_chain_area = drop_zone

    def _build_builder_guardrails_card(self) -> None:
        guardrails = self._builder_canvas["guardrails"]
        with ui.card().classes("w-full"):
            ui.label("Guardrails (optional)").classes("font-semibold text-sm")
            for slot, title in (("before", "Before"), ("after", "After")):
                block = guardrails.get(slot) or {
                    "identifier": "",
                    "agent_type": "",
                    "endpoint": "",
                }
                guardrails[slot] = block
                with ui.row().classes("w-full gap-3 items-center flex-wrap"):
                    ui.label(title).classes("text-xs text-grey-6 w-14")
                    ui.input("Identifier", value=block["identifier"]).props(
                        "dense outlined"
                    ).classes("w-56").bind_value(block, "identifier")
                    ui.input("Agent type", value=block["agent_type"]).props(
                        "dense outlined"
                    ).classes("w-40").bind_value(block, "agent_type")
                    ui.input("Endpoint", value=block["endpoint"]).props(
                        "dense outlined"
                    ).classes("flex-1 min-w-64").bind_value(block, "endpoint")

    def _build_builder_progress_card(self) -> None:
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.label("Progress").classes("font-semibold text-sm")
                self._builder_status_label = ui.label("Idle").classes(
                    "text-xs text-grey-6"
                )
                self._builder_spinner = ui.spinner(size="sm")
                self._builder_spinner.set_visibility(False)
            self._builder_log = (
                ui.log(max_lines=_MAX_LOG_LINES)
                .classes("w-full h-56 text-xs font-mono")
                .style("white-space: pre-wrap")
            )
            # Bus events arrive on the attack's worker thread; they are queued
            # and flushed here so widgets are only touched from the event loop.
            ui.timer(0.4, self._builder_flush_events)

    def _builder_flush_events(self) -> None:
        """Move queued bus lines into the log widget (runs on the event loop)."""
        if self._builder_log is None:
            return
        while self._builder_event_queue:
            self._builder_log.push(self._builder_event_queue.popleft())

    # ── Canvas mutation ───────────────────────────────────────────────────────

    def _builder_set_drag(self, attack_type: str) -> None:
        self._builder_drag_type = attack_type

    def _builder_drop(self) -> None:
        if self._builder_drag_type:
            self._builder_add_attack(self._builder_drag_type)
            self._builder_drag_type = None

    def _builder_add_attack(self, attack_type: str) -> None:
        self._builder_canvas["attacks"].append(
            {"attack_type": attack_type, "params": ""}
        )
        self._builder_render_chain()

    def _builder_move_attack(self, index: int, delta: int) -> None:
        blocks = self._builder_canvas["attacks"]
        target = index + delta
        if 0 <= target < len(blocks):
            blocks[index], blocks[target] = blocks[target], blocks[index]
            self._builder_render_chain()

    def _builder_remove_attack(self, index: int) -> None:
        blocks = self._builder_canvas["attacks"]
        if 0 <= index < len(blocks):
            blocks.pop(index)
            self._builder_render_chain()

    def _builder_render_chain(self) -> None:
        if self._builder_chain_area is None:
            return
        blocks = self._builder_canvas["attacks"]
        self._builder_chain_area.clear()
        with self._builder_chain_area:
            if not blocks:
                ui.label(
                    "Drag an attack from the palette here to start the chain."
                ).classes("text-sm text-grey-6 p-2")
                return
            for index, block in enumerate(blocks):
                with ui.card().classes("w-full p-2"):
                    with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                        ui.badge(str(index + 1)).props("color=primary")
                        ui.label(attack_label(block["attack_type"])).classes(
                            "text-sm font-medium"
                        )
                        ui.label(block["attack_type"]).classes(
                            "text-xs font-mono text-grey-6"
                        )
                        ui.space()
                        ui.button(
                            icon="arrow_upward",
                            on_click=lambda _e, i=index: self._builder_move_attack(
                                i, -1
                            ),
                        ).props("flat dense round")
                        ui.button(
                            icon="arrow_downward",
                            on_click=lambda _e, i=index: self._builder_move_attack(
                                i, 1
                            ),
                        ).props("flat dense round")
                        ui.button(
                            icon="close",
                            on_click=lambda _e, i=index: self._builder_remove_attack(i),
                        ).props("flat dense round color=grey-7")
                    ui.textarea(
                        "Parameters (JSON, optional)", value=block.get("params") or ""
                    ).props("dense outlined autogrow").classes("w-full").bind_value(
                        block, "params"
                    )
                if index < len(blocks) - 1:
                    ui.icon("south").classes("text-grey-6 self-center")

    def _builder_collect_canvas(self) -> Dict[str, Any]:
        """Return the canvas with widget-only values folded back in."""
        canvas = self._builder_canvas
        if self._builder_name_input is not None:
            canvas["name"] = (
                self._builder_name_input.value or "Untitled attack"
            ).strip()
        if self._builder_goals_text is not None:
            canvas["goals"]["goals"] = [
                line.strip()
                for line in (self._builder_goals_text.value or "").splitlines()
                if line.strip()
            ]
        return canvas

    def _builder_apply_canvas(self, canvas: Dict[str, Any]) -> None:
        """Replace the live canvas and rebuild the whole panel from it."""
        merged = new_canvas()
        merged.update({k: v for k, v in canvas.items() if v is not None})
        self._builder_canvas = merged
        panel = self.all_panels.get("builder")
        if panel is None:
            return
        panel.clear()
        self._build_builder_panel(panel)

    # ── Drafts ────────────────────────────────────────────────────────────────

    def _builder_backend_supports_drafts(self) -> bool:
        return hasattr(self.backend, "save_builder_draft")

    async def _builder_save_draft(self) -> None:
        if not self._builder_backend_supports_drafts():
            ui.notify("This storage backend cannot save drafts.", type="warning")
            return
        canvas = self._builder_collect_canvas()
        try:
            draft = await asyncio.to_thread(
                self.backend.save_builder_draft,
                canvas["name"],
                json.loads(json.dumps(canvas)),  # detach from live widget state
                self._builder_draft_id,
            )
        except Exception as exc:
            logger.error("Failed to save builder draft", exc_info=True)
            ui.notify(f"Could not save draft: {exc}", type="negative")
            return
        self._builder_draft_id = draft["id"]
        await self._builder_refresh_drafts()
        ui.notify(f"Draft '{draft['name']}' saved.", type="positive")

    async def _builder_refresh_drafts(self) -> None:
        if self._builder_drafts_select is None or not (
            self._builder_backend_supports_drafts()
        ):
            return
        try:
            drafts: List[Dict[str, Any]] = await asyncio.to_thread(
                self.backend.list_builder_drafts
            )
        except Exception:
            logger.error("Failed to list builder drafts", exc_info=True)
            return
        self._builder_drafts_select.set_options(
            {
                draft["id"]: f"{draft['name']} — {canvas_summary(draft['canvas'])}"
                for draft in drafts
            },
            value=self._builder_draft_id,
        )

    def _builder_selected_draft_id(self) -> Optional[str]:
        """Selected draft id, or None after notifying why there is none."""
        if not self._builder_backend_supports_drafts():
            ui.notify("This backend cannot store attack drafts.", type="warning")
            return None
        draft_id = self._builder_drafts_select and self._builder_drafts_select.value
        if not draft_id:
            ui.notify("Select a saved draft first.", type="warning")
            return None
        return draft_id

    async def _builder_load_draft(self) -> None:
        draft_id = self._builder_selected_draft_id()
        if not draft_id:
            return
        try:
            draft = await asyncio.to_thread(self.backend.get_builder_draft, draft_id)
        except Exception as exc:
            logger.error("Failed to open builder draft", exc_info=True)
            ui.notify(f"Could not open draft: {exc}", type="negative")
            return
        if not draft:
            ui.notify("That draft no longer exists.", type="warning")
            return
        self._builder_draft_id = draft["id"]
        self._builder_apply_canvas(draft["canvas"])
        await self._builder_refresh_drafts()
        ui.notify(f"Opened draft '{draft['name']}'.", type="positive")

    async def _builder_delete_draft(self) -> None:
        draft_id = self._builder_selected_draft_id()
        if not draft_id:
            return
        try:
            await asyncio.to_thread(self.backend.delete_builder_draft, draft_id)
        except Exception as exc:
            logger.error("Failed to delete builder draft", exc_info=True)
            ui.notify(f"Could not delete draft: {exc}", type="negative")
            return
        if self._builder_draft_id == draft_id:
            self._builder_draft_id = None
        await self._builder_refresh_drafts()
        ui.notify("Draft deleted.", type="positive")

    # ── Submission ────────────────────────────────────────────────────────────

    def _builder_payload(self) -> Optional[Dict[str, Any]]:
        try:
            return build_run_payload(self._builder_collect_canvas())
        except CanvasValidationError as exc:
            ui.notify(str(exc), type="warning")
            return None

    def _builder_preview(self) -> None:
        payload = self._builder_payload()
        if payload is None:
            return
        preview = {
            key: payload[key]
            for key in ("target", "mode", "attack_config", "attacks", "timeout")
            if key in payload
        }
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl"):
            ui.label("Generated attack configuration").classes("font-semibold")
            ui.code(json.dumps(preview, indent=2), language="json").classes("w-full")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    async def _builder_run(self) -> None:
        if self._builder_running:
            ui.notify("An attack is already running.", type="warning")
            return
        payload = self._builder_payload()
        if payload is None:
            return

        self._builder_running = True
        self._builder_run_btn.disable()
        self._builder_spinner.set_visibility(True)
        self._builder_status_label.text = "Running…"
        self._builder_log.clear()
        self._builder_event_queue.clear()
        chain = (
            payload["attack_config"]["attack_type"]
            if payload["mode"] == "single"
            else " → ".join(step["attack_type"] for step in payload["attacks"])
        )
        self._builder_log.push(f"▶ {payload['target']['agent_name']}: {chain}")

        try:
            await asyncio.to_thread(self._builder_execute, payload)
        except Exception as exc:
            logger.error("Attack builder run failed", exc_info=True)
            self._builder_log.push(f"✖ {exc}")
            self._builder_status_label.text = "Failed"
            ui.notify(f"Attack failed: {exc}", type="negative")
        else:
            self._builder_status_label.text = "Completed"
            self._builder_log.push("✔ Attack finished — see History for results.")
            ui.notify("Attack completed. Results are in History.", type="positive")
        finally:
            self._builder_running = False
            self._builder_run_btn.enable()
            self._builder_spinner.set_visibility(False)

        await self.refresh_view()

    def _builder_execute(self, payload: Dict[str, Any]) -> Any:
        """Blocking in-process attack submission — runs on a worker thread."""
        from hackagent import HackAgent
        from hackagent.cli.tui.events import TUIEventBus

        bus = TUIEventBus()
        bus.subscribe(self._builder_on_event)

        target = payload["target"]
        agent = HackAgent(
            name=target["agent_name"],
            endpoint=target["endpoint"],
            agent_type=target["agent_type"],
            before_guardrail=payload.get("before_guardrail"),
            after_guardrail=payload.get("after_guardrail"),
            backend=self.backend,
        )
        run_config_override = {"timeout": payload["timeout"]}
        if payload["mode"] == "single":
            return agent.hack(
                attack_config=payload["attack_config"],
                run_config_override=run_config_override,
                fail_on_run_error=True,
                _tui_event_bus=bus,
            )
        return agent.hack_chain(
            attacks=payload["attacks"],
            goals=payload.get("goals"),
            run_config_override=run_config_override,
            fail_on_run_error=True,
            _tui_event_bus=bus,
        )

    def _builder_on_event(self, event) -> None:
        """Bus subscriber — called on the attack's worker thread.

        Only appends to a queue; :meth:`_builder_flush_events` renders it.
        """
        line = self._builder_format_event(event)
        if line:
            self._builder_event_queue.append(line)

    @staticmethod
    def _builder_format_event(event) -> str:
        payload = event.payload or {}
        detail = (
            payload.get("message")
            or payload.get("goal")
            or payload.get("step")
            or payload.get("status")
            or ""
        )
        detail = str(detail)
        if len(detail) > 160:
            detail = detail[:157] + "…"
        return f"{event.event_type}: {detail}" if detail else str(event.event_type)
