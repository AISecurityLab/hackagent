# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign builder: an outline of the schema on the left, its fields on the right.

Every field starts at its schema default, shown dimmed; typing overrides it and
clearing it (or ``ctrl+t``) goes back to the default. Only overrides are saved.
Rarely changed fields wait under *Advanced*. Problems are shown on the field
they concern and flagged in the outline. *Run* resolves the campaign first —
the goals, models and judges ``hackagent campaign validate`` checks — then
executes that frozen snapshot while editing carries on, showing the run's log
as ``hackagent campaign run`` writes it, coloured.
"""

from __future__ import annotations

import copy
from collections import deque
from queue import Empty, SimpleQueue
import logging
import os
import shlex
import subprocess
import tempfile
from pathlib import Path as FilePath
from threading import Event
from typing import Any, Callable, Optional

import yaml
from rich.markup import escape
from textual import on
from textual.app import ComposeResult, SuspendNotSupported
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.events import DescendantFocus
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    OptionList,
    Static,
    Switch,
    TextArea,
    Tree,
)
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode


from hackagent.interfaces.palette import ACCENT, FAILED, PASSED, paint
from hackagent.interfaces.tui.frame import TitleBar
from hackagent.interfaces.tui.keys import key
from hackagent.core.credentials import CredentialError
from hackagent.core.logging import capture
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.checks import issue_markup, ready_markup, to_fix_markup
from hackagent.interfaces.cli.logging_setup import log_markup, shown_level
from hackagent.orchestrator.campaign import CampaignSpec

from .draft import CampaignDraft, Issue
from .form import FieldRow
from .outline import Group, Node, Outline, build_outline, issue_matches
from .screens import RUN_LINES, ConfirmScreen, PathScreen, RunScreen

#: How often the run view draws what the run logged, in seconds, and at most
#: how many lines each time.
_DRAIN_S = 0.1
_DRAIN_BATCH = 500


class CampaignBuilder(Container):
    """Build a campaign from prefilled fields, then run it."""

    DEFAULT_CSS = """
    CampaignBuilder { layout: vertical; height: 100%; }
    CampaignBuilder #body { height: 1fr; }
    CampaignBuilder #outline-pane {
        width: 30; height: 100%;
        border-right: solid $primary-darken-2; background: $surface;
    }
    CampaignBuilder #run-actions {
        height: auto; align-horizontal: center;
        border-top: solid $primary-darken-2;
    }
    CampaignBuilder #run-actions Button { margin: 0 1; min-width: 10; }
    CampaignBuilder #outline { height: 1fr; padding: 0 1; background: $surface; }
    CampaignBuilder #form { width: 1fr; height: 100%; padding: 0 2; }
    CampaignBuilder .panel-title { text-style: bold; margin-top: 1; }
    CampaignBuilder .panel-doc { color: $text-muted; margin-bottom: 1; }
    CampaignBuilder .panel-issues { color: $error; margin-bottom: 1; }
    CampaignBuilder .toolbar { height: auto; margin-bottom: 1; }
    CampaignBuilder .toolbar Button { margin: 0 2 0 0; }
    CampaignBuilder .box {
        height: auto; border: round $primary-darken-2;
        padding: 0 1; margin-bottom: 1;
    }
    CampaignBuilder .box-title { color: $accent; margin-bottom: 1; }
    CampaignBuilder .enable-row { height: auto; margin-bottom: 1; }
    CampaignBuilder .enable-row Static { width: 24; color: $text-muted; }
    CampaignBuilder Collapsible { border: none; padding: 0; margin-top: 1; }
    CampaignBuilder Collapsible > Contents { padding: 0 0 0 2; }
    CampaignBuilder .attack-list { height: auto; max-height: 20; }
    """

    BINDINGS = [
        key("home", "welcome"),
        key("run"),
        key("stop"),
        key("save"),
        key("open_file", "open"),
        key("edit_yaml"),
        key("reset", "reset_field", show=False),
        key("remove", "remove_node", show=False),
        key("back", "focus_outline", show=False),
    ]

    def __init__(
        self,
        cli_config: CLIConfig,
        initial_data: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__()
        self.cli_config = cli_config
        self.initial_data = initial_data or {}
        self._path: Optional[FilePath] = None
        self._has_comments = False
        self.draft = CampaignDraft()
        self._load_initial()
        self._saved = self.draft.to_yaml() if self._path else ""
        self._spec: Optional[CampaignSpec] = None
        self._issues: tuple[Issue, ...] = ()
        self._node: Optional[Node] = None
        self._tree_nodes: dict[tuple[str, tuple], TreeNode[Node]] = {}
        self._timer: Optional[Timer] = None
        self._campaign_running = False
        self._cancel = Event()
        #: The current run's latest lines, so the run view can be left and
        #: reopened without losing them; the oldest go past RUN_LINES.
        self._run_lines: deque[str] = deque(maxlen=RUN_LINES)
        #: What the run's log handler hands the view, from the run's thread:
        #: drained on the UI's, so logging never waits for a repaint.
        self._incoming: SimpleQueue[str] = SimpleQueue()
        self._snapshot: Optional[CampaignSpec] = None

    def start_from(self, template: Any) -> None:
        """Replace the draft with a starting template, as if freshly opened."""
        text = yaml.safe_dump(template.document)
        self.draft = CampaignDraft.from_yaml(text)
        self._path = getattr(template, "path", None)
        self._has_comments = False
        # The template as given is not a modification of it. Leaving this
        # empty made a freshly opened builder claim to be modified, and
        # made leaving it ask what there was to discard.
        self._saved = self.draft.to_yaml()
        self._validate()
        self._rebuild_outline(("campaign",))
        self.query_one(Tree).focus()
        opened = self._path is not None
        self.notify(
            f"Opened {self._path.name}. Edit any field, then Run."
            if opened
            else f"Started from “{template.title}”. Edit any field, then Run.",
            title="Ready",
            timeout=6,
        )

    def action_remove_node(self) -> None:
        """Remove the attack or judge the outline is sitting on.

        Bound to Delete. A focused text editor claims that key for
        forward-delete, so the removal only happens when the cursor is not in
        one — anywhere else, Delete removes whatever the outline is on.
        """
        node = self._node
        if node is None or isinstance(self.app.focused, (Input, TextArea)):
            return
        if not self._is_removable(node):
            self.notify(
                "Pick an attack or a judge to remove.", severity="warning", timeout=4
            )
            return
        what = self._removable_label(node)
        self._confirm(
            f"Remove {what}?",
            "It is taken out of the campaign; nothing is written to disk.",
            "Remove",
            lambda: self._remove(node),
        )

    @staticmethod
    def _is_removable(node: Node) -> bool:
        return node.kind == "attack" or (
            node.root[:2] == ("evaluation", "judges") and len(node.root) == 3
        )

    def _removable_label(self, node: Node) -> str:
        if node.kind == "attack":
            return f"the attack “{self._attack_name(node)}”"
        return f"judge {int(node.root[-1]) + 1}"

    def _remove(self, node: Node) -> None:
        parent, index = node.root[:-1], int(node.root[-1])
        self.draft.remove(parent, index)
        self._edited()
        self._rebuild_outline(
            ("attacks",) if parent == ("attacks",) else ("evaluation",)
        )
        self.query_one(Tree).focus()

    def action_welcome(self) -> None:
        """Back to the ways in. Asks first if the draft would be lost."""
        if not self._is_dirty():
            self.app.show_welcome()
            return
        self._confirm(
            "Discard your changes?",
            "Going back to the welcome screen replaces the form.",
            "Discard",
            self.app.show_welcome,
        )

    def _load_initial(self) -> None:
        path = self.initial_data.get("campaign_path")
        text = self.initial_data.get("campaign_yaml")
        try:
            if path:
                candidate = FilePath(str(path)).expanduser()
                text = candidate.read_text(encoding="utf-8")
                self._path = candidate
            if text:
                self.draft = CampaignDraft.from_yaml(str(text))
                self._has_comments = "#" in str(text)
        except (OSError, yaml.YAMLError, ValueError):
            self._path = None
            self.draft = CampaignDraft()

    # -- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield TitleBar(id="doc-bar")
        with Horizontal(id="body", classes="frame-body"):
            # The outline and the run controls are one column: picking what to
            # build and starting the run are the two things this pane is for.
            with Vertical(id="outline-pane"):
                tree: Tree[Node] = Tree("campaign", id="outline")
                tree.show_root = False
                tree.auto_expand = False
                yield tree
                with Horizontal(id="run-actions"):
                    yield Button("Run", id="run", variant="success")
                    yield Button("Stop", id="stop", variant="warning", disabled=True)
            yield VerticalScroll(id="form")

    def on_mount(self) -> None:
        self.set_interval(_DRAIN_S, self._drain)
        # Tab from the outline should land on the first field, not the scroller.
        self.query_one("#form").can_focus = False
        # Nor on the run controls, which sit between them in the left pane:
        # Tab is for moving through the campaign. They stay clickable, and
        # ctrl+r and F3 drive them from the keyboard.
        for button in ("#run", "#stop"):
            self.query_one(button, Button).can_focus = False
        self._validate()
        self._rebuild_outline(("campaign",))
        self.query_one(Tree).focus()
        if self.initial_data.get("auto_execute_campaign"):
            self.call_after_refresh(self.action_run)

    # -- outline -----------------------------------------------------------

    def _label(self, node: Node) -> str:
        if node.kind == "add_attack":
            return paint("+ add attack", ACCENT)
        if node.kind == "add_judge":
            return paint("+ add judge", ACCENT)
        title = node.title
        if node.root[:2] == ("evaluation", "judges"):
            _, name = self.draft.get(node.root + ("name",))
            title = str(name or title)
        elif node.kind == "group" and node.root == ("attacks",):
            title = f"{title} ({len(self.draft.items(('attacks',)))})"
        title = escape(title)
        if not node.enabled(self.draft):
            return f"[dim]{title} · off[/dim]"
        if any(issue_matches(node.root, issue.loc) for issue in self._issues):
            return f"{title} {paint('✗', FAILED)}"
        if len(node.root) == 1:
            return f"{title} {paint('✓', PASSED)}"
        return title

    def _rebuild_outline(self, select: Optional[tuple] = None) -> None:
        tree = self.query_one(Tree)
        tree.clear()
        self._tree_nodes = {}

        def add(parent: TreeNode[Node], outline: Outline) -> None:
            node = outline.node
            if outline.children:
                branch = parent.add(self._label(node), data=node, expand=True)
                for child in outline.children:
                    add(branch, child)
            else:
                branch = parent.add_leaf(self._label(node), data=node)
            self._tree_nodes[(node.kind, node.root)] = branch

        for outline in build_outline(self.draft):
            add(tree.root, outline)

        target = next(
            (
                branch
                for (kind, root), branch in self._tree_nodes.items()
                if root == select and kind != "add_judge"
            ),
            None,
        ) or next(iter(self._tree_nodes.values()))
        self._node = None
        self.call_after_refresh(tree.move_cursor, target)
        self.call_later(self._show, target.data)

    def _refresh_labels(self) -> None:
        for branch in self._tree_nodes.values():
            if branch.data is not None:
                branch.set_label(self._label(branch.data))

    async def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.node.data is not None:
            await self._show(event.node.data)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        self._focus_panel()

    # -- panels ------------------------------------------------------------

    @property
    def _run_screen(self) -> Optional[RunScreen]:
        """The run view, when it is the screen on top."""
        screen = self.app.screen if self.app.screen_stack else None
        return screen if isinstance(screen, RunScreen) else None

    def _log(self, markup: str) -> None:
        """Record a line of the run, and show it if anyone is watching."""
        self._run_lines.append(markup)
        screen = self._run_screen
        if screen is not None:
            screen.write(markup)

    def _drain(self, limit: Optional[int] = _DRAIN_BATCH) -> None:
        """Show what the run's log handed over since the last look, at most
        ``limit`` lines (all of them with ``None``), so a burst of lines
        never holds the screen for long."""
        taken = 0
        while limit is None or taken < limit:
            try:
                markup = self._incoming.get_nowait()
            except Empty:
                return
            self._log(markup)
            taken += 1

    def _watch_run(self) -> None:
        """Open the run view on whatever the run has produced so far."""
        if self._run_screen is not None:
            return
        title = self._snapshot.campaign.name if self._snapshot else "Run"
        self.app.push_screen(RunScreen(title, self._run_lines, self.action_stop))

    async def _show(self, node: Optional[Node], *, force: bool = False) -> None:
        if node is None or (node == self._node and not force):
            return
        if node != self._node:
            # What the title bar said about the last part (a field, an attack
            # in the list) is not about this one.
            self.query_one("#doc-bar", TitleBar).show(context="")
        self._node = node
        form = self.query_one("#form", VerticalScroll)
        await form.remove_children()
        await form.mount_all(self._panel(node))
        form.scroll_home(animate=False)
        self._apply_issues()

    def _panel(self, node: Node) -> list[Widget]:
        widgets: list[Widget] = [
            Static(escape(self._panel_title(node)), classes="panel-title")
        ]
        description = node.description or self._attack_description(node)
        if description:
            widgets.append(Static(escape(description), classes="panel-doc"))

        buttons: list[Button] = []
        if node.kind == "model" and node.root != ("target",):
            buttons.append(
                Button(
                    "Copy connection from target", compact=True, classes="copy-target"
                )
            )
        if node.kind == "attack" or node.root[:2] == ("evaluation", "judges"):
            buttons.append(
                Button("Remove", variant="error", compact=True, classes="remove")
            )
        if buttons:
            widgets.append(Horizontal(*buttons, classes="toolbar"))

        if node.optional:
            widgets.append(
                Horizontal(
                    Static("enabled"),
                    Switch(value=node.enabled(self.draft), classes="enable"),
                    classes="enable-row",
                )
            )
            if not node.enabled(self.draft):
                return widgets

        if node.kind == "add_attack":
            return widgets + [self._attack_list()]
        if node.kind == "add_judge":
            return widgets + [
                Static(
                    "A judge reads each reply and votes on whether the attack "
                    "succeeded. It starts with the target's connection.",
                    classes="panel-doc",
                ),
                Button(
                    "Add judge", variant="success", compact=True, classes="add-judge"
                ),
            ]
        if node.kind == "group":
            return widgets + [Static(self._group_summary(node), classes="panel-doc")]

        widgets.append(Static("", classes="panel-issues"))
        groups = node.groups(self.draft)
        for group in groups:
            widgets.extend(self._group_widgets(node, group))
        if not groups and node.kind == "attack":
            widgets.append(
                Static("This attack has no parameters.", classes="panel-doc")
            )
        return widgets

    def _group_widgets(self, node: Node, group: Group) -> list[Widget]:
        """A box of rows: the nested model it comes from, titled and bordered.

        The panel's own fields have no box; everything else is grouped the way
        the schema groups it, so related settings stay together.
        """
        rows = [
            FieldRow(field, node.root, self.draft, group.path) for field in group.fields
        ]
        if not group.path:
            return list(rows)

        on = self.draft.get(node.root + group.path)[0]
        body: list[Widget] = [
            Static(f"[b]{escape(group.title)}[/b]", classes="box-title")
        ]
        if group.description:
            body.append(Static(escape(group.description), classes="panel-doc"))
        if group.optional:
            body.append(
                Horizontal(
                    Static("enabled"),
                    Switch(
                        value=on,
                        classes="enable-group",
                        name=".".join(str(part) for part in group.path),
                    ),
                    classes="enable-row",
                )
            )
            if not on:
                return [Vertical(*body, classes="box")]
        body.extend(rows)
        for inner in group.boxes:
            body.extend(self._group_widgets(node, inner))
        return [Vertical(*body, classes="box")]

    def _panel_title(self, node: Node) -> str:
        if node.kind == "attack":
            return f"Attacks › {node.title}"
        if node.kind == "add_attack":
            return "Add an attack"
        if node.kind == "add_judge":
            return "Add a judge"
        parent = {
            "roles": f"Attacks › {self._attack_name(node)} › ",
            "judges": "Evaluation › ",
            "guardrails": "Guardrails › ",
            "dataset": "Dataset › ",
        }
        if len(node.root) > 1:
            key = node.root[-2] if node.root[-2] in parent else node.root[0]
            return parent.get(str(key), "") + self._label_text(node)
        return node.title

    def _label_text(self, node: Node) -> str:
        if node.root[:2] == ("evaluation", "judges"):
            _, name = self.draft.get(node.root + ("name",))
            return str(name or node.title)
        return node.title

    def _attack_name(self, node: Node) -> str:
        _, name = self.draft.get(node.root[:2] + ("name",))
        return str(name or "")

    def _attack_description(self, node: Node) -> str:
        if node.kind != "attack" or not node.attack:
            return ""
        from hackagent.client import catalog_by_id

        entry = catalog_by_id().get(node.attack, {})
        return str(entry.get("description") or "")

    def _attack_list(self) -> OptionList:
        from hackagent.client import catalog_entries

        options = [
            Option(
                f"{escape(str(entry['attack_type']))}  "
                f"[dim]{escape(str(entry.get('category_label') or ''))}[/dim]",
                id=str(entry["attack_type"]),
            )
            for entry in catalog_entries()
        ]
        return OptionList(*options, classes="attack-list")

    def _group_summary(self, node: Node) -> str:
        if node.root == ("attacks",):
            names = [
                str(item.get("name", "?"))
                for item in self.draft.items(("attacks",))
                if isinstance(item, dict)
            ]
            return "\n".join(f"• {escape(name)}" for name in names) or "No attacks yet."
        sides = []
        for side in ("before", "after"):
            state = "on" if self.draft.get(("guardrails", side))[0] else "off"
            sides.append(f"{side}: {state}")
        return " · ".join(sides)

    def _focus_panel(self) -> None:
        for widget in self.query_one("#form").query("*"):
            if widget.focusable and widget.display:
                widget.focus()
                return

    # -- validation ----------------------------------------------------------

    def _edited(self) -> None:
        self._update_doc_bar()
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(0.25, self._validate)

    def _validate(self) -> None:
        self._spec, self._issues = self.draft.validate()
        self._refresh_labels()
        self._apply_issues()
        self._update_doc_bar()
        self._sync_run_controls()

    def _sync_run_controls(self) -> None:
        """Run and Stop, as buttons and as keys, follow the campaign: Run
        needs a valid campaign and no run going, Stop a run going."""
        self.query_one("#run", Button).disabled = (
            self._campaign_running or self._spec is None
        )
        self.query_one("#stop", Button).disabled = not self._campaign_running
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Run is greyed out until the campaign is valid (while a run goes,
        it shows the run); Stop is offered only while a run goes."""
        if action == "run":
            return True if self._campaign_running or self._spec is not None else None
        if action == "stop":
            return self._campaign_running
        return True

    def _apply_issues(self) -> None:
        node = self._node
        if node is None:
            return
        rows = list(self.query(FieldRow))
        claimed: set[int] = set()
        for row in rows:
            row.issue = None
            for position, issue in enumerate(self._issues):
                if issue_matches(row.path, issue.loc):
                    row.issue = issue.message
                    claimed.add(position)
                    break
            row.refresh_state()

        deeper = [
            root
            for (kind, root) in self._tree_nodes
            if kind not in ("add_judge", "add_attack")
            and len(root) > len(node.root)
            and issue_matches(node.root, root)
        ]
        lines = []
        for position, issue in enumerate(self._issues):
            if position in claimed or not issue_matches(node.root, issue.loc):
                continue
            if any(issue_matches(root, issue.loc) for root in deeper):
                continue
            lines.append(issue_markup(issue, relative_to=node.root))
        for widget in self.query(".panel-issues"):
            assert isinstance(widget, Static)
            widget.update("\n".join(lines))
            widget.display = bool(lines)

    def _update_doc_bar(self) -> None:
        name = self._path.name if self._path else "untitled campaign"
        dirty = " [$warning]●[/] [dim]modified[/dim]" if self._is_dirty() else ""
        count = len(self._issues)
        state = to_fix_markup(count) if count else ready_markup()
        running = (
            "  [$accent]▶ running[/] [dim]· ctrl+r to watch[/dim]"
            if self._campaign_running
            else ""
        )
        self.query_one("#doc-bar", TitleBar).show(
            title=f"{escape(name)}{dirty}  ·  {state}{running}"
        )

    def _is_dirty(self) -> bool:
        try:
            return self.draft.to_yaml() != self._saved
        except CredentialError:
            return True

    # -- events from the form -----------------------------------------------

    def _switch_variant(self, row: FieldRow) -> None:
        """A tagged union changed shape: drop the old variant's fields.

        The fields of the variant left behind mean nothing to the new one, and
        leaving them would make the document invalid, so the tag is kept and
        everything beside it goes.
        """
        parent = row.path[:-1]
        tag = row.path[-1]
        found, current = self.draft.get(parent)
        if found and isinstance(current, dict):
            for key in [key for key in current if key != tag]:
                self.draft.delete(parent + (key,), keep=len(parent))
        node = self._node
        if node is not None:
            self.call_after_refresh(
                lambda: self.run_worker(self._show(node, force=True))
            )

    def on_field_row_edited(self, event: FieldRow.Edited) -> None:
        self._edited()
        if event.row.field.discriminator:
            self._switch_variant(event.row)

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        widget = self.app.focused
        row = next(
            (
                node
                for node in (widget.ancestors if widget else [])
                if isinstance(node, FieldRow)
            ),
            None,
        )
        # What the focused field is for; the keys are the footer's.
        about = ""
        if row is not None:
            text = row.field.description or row.field.label
            about = f"{escape(row.field.label)}: {escape(text)}"
        self.query_one("#doc-bar", TitleBar).show(context=about)

    @on(Switch.Changed, ".enable-group")
    async def _toggle_group(self, event: Switch.Changed) -> None:
        """Turn an optional box (a classifier, say) on or off in place."""
        event.stop()
        node = self._node
        if node is None or not event.switch.name:
            return
        path = node.root + tuple(event.switch.name.split("."))
        if event.value:
            self.draft.set(path, {})
        else:
            self.draft.delete(path, keep=len(node.root))
        self._edited()
        self._refresh_labels()
        await self._show(node, force=True)

    @on(Switch.Changed, ".enable")
    async def _toggle_optional(self, event: Switch.Changed) -> None:
        node = self._node
        if node is None or not node.optional:
            return
        if event.value:
            self.draft.set(node.root, {})
        else:
            self.draft.delete(node.root, keep=len(node.root) - 2)
        self._edited()
        self._refresh_labels()
        await self._show(node, force=True)

    @on(OptionList.OptionHighlighted, ".attack-list")
    def _describe_attack(self, event: OptionList.OptionHighlighted) -> None:
        from hackagent.client import catalog_by_id

        entry = catalog_by_id().get(str(event.option.id), {})
        self.query_one("#doc-bar", TitleBar).show(
            context=escape(str(entry.get("description") or event.option.id))
        )

    @on(OptionList.OptionSelected, ".attack-list")
    def _add_attack(self, event: OptionList.OptionSelected) -> None:
        index = self.draft.append(("attacks",), {"name": str(event.option.id)})
        self._edited()
        self._rebuild_outline(("attacks", index))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        node = self._node
        if button.id == "run":
            self.action_run()
        elif button.id == "stop":
            self._stop()
        elif node is None:
            return
        elif button.has_class("remove"):
            self._remove(node)
        elif button.has_class("copy-target"):
            found, connection = self.draft.get(("target", "connection"))
            if not found:
                self.notify("The target has no connection yet.", severity="warning")
                return
            self.draft.set(node.root + ("connection",), copy.deepcopy(connection))
            self._edited()
            self.call_later(self._show, node, force=True)
        elif button.has_class("add-judge"):
            found, connection = self.draft.get(("target", "connection"))
            judge = {"connection": copy.deepcopy(connection)} if found else {}
            index = self.draft.append(("evaluation", "judges"), judge)
            self._edited()
            self._rebuild_outline(("evaluation", "judges", index))

    # -- actions -------------------------------------------------------------

    def action_focus_outline(self) -> None:
        self.query_one(Tree).focus()

    def action_reset_field(self) -> None:
        focused = self.app.focused
        row = next(
            (
                node
                for node in (focused.ancestors if focused else [])
                if isinstance(node, FieldRow)
            ),
            None,
        )
        if row is None:
            self.notify("Move to a field to reset it.", severity="warning")
            return
        row.reset()

    def _confirm(
        self, question: str, detail: str, action: str, then: Callable[[], None]
    ) -> None:
        def _after(confirmed: Optional[bool]) -> None:
            if confirmed:
                then()

        self.app.push_screen(ConfirmScreen(question, detail, action), _after)

    def action_save(self) -> None:
        if self._path is None:
            self._save_as()
        else:
            self._write(self._path)

    def _save_as(self) -> None:
        def _after(value: Optional[str]) -> None:
            if value:
                self._write(FilePath(value).expanduser())

        self.app.push_screen(
            PathScreen("Save campaign as", "campaign.yaml", "Save"), _after
        )

    def _write(self, path: FilePath, *, confirmed: bool = False) -> None:
        if self._has_comments and path == self._path and not confirmed:
            self._confirm(
                f"Overwrite {path.name}?",
                "The file is rewritten from the form, so its comments are lost.",
                "Save",
                lambda: self._write(path, confirmed=True),
            )
            return
        try:
            text = self.draft.to_yaml()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except (OSError, CredentialError) as exc:
            self.notify(str(exc), title="Save failed", severity="error")
            return
        self._path, self._saved, self._has_comments = path, text, False
        self._update_doc_bar()
        self.notify(f"Saved {path}", title="Campaign")

    def action_open(self) -> None:
        def _ask() -> None:
            def _after(value: Optional[str]) -> None:
                if value:
                    self._read(FilePath(value).expanduser())

            self.app.push_screen(
                PathScreen("Open campaign", "campaign.yaml", "Open"), _after
            )

        if self._is_dirty():
            self._confirm(
                "Discard your changes?",
                "Opening a file replaces the form.",
                "Discard",
                _ask,
            )
        else:
            _ask()

    def open_path(self, path: FilePath) -> None:
        """Open a campaign file, keeping the comments that explain it."""
        self._read(path)

    def _read(self, path: FilePath) -> None:
        try:
            text = path.read_text(encoding="utf-8")
            draft = CampaignDraft.from_yaml(text)
        except (OSError, yaml.YAMLError, ValueError) as exc:
            self.notify(str(exc), title="Open failed", severity="error")
            return
        self.draft, self._path, self._has_comments = draft, path, "#" in text
        self._saved = draft.to_yaml()
        self._validate()
        self._rebuild_outline(("campaign",))
        self.notify(f"Opened {path}", title="Campaign")

    def action_edit_yaml(self) -> None:
        """Edit the whole campaign in ``$EDITOR``; the form reloads from it."""
        try:
            draft_text = self.draft.to_yaml()
        except CredentialError as exc:
            self.notify(str(exc), title="Editor failed", severity="error")
            return
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
        # An unmodified file is edited in place, so its comments survive.
        in_place = self._path is not None and not self._is_dirty()
        if in_place:
            target = self._path
        else:
            handle = tempfile.NamedTemporaryFile(
                "w", suffix=".yaml", delete=False, encoding="utf-8"
            )
            with handle:
                handle.write(draft_text)
            target = FilePath(handle.name)
        try:
            with self.app.suspend():
                subprocess.run([*shlex.split(editor), str(target)], check=False)
            text = target.read_text(encoding="utf-8")
        except (OSError, ValueError, SuspendNotSupported) as exc:
            self.notify(str(exc), title="Editor failed", severity="error")
            return
        finally:
            if not in_place:
                target.unlink(missing_ok=True)
        try:
            draft = CampaignDraft.from_yaml(text)
        except (yaml.YAMLError, ValueError) as exc:
            self.notify(f"Kept the form: {exc}", title="Invalid YAML", severity="error")
            return
        self.draft = draft
        if in_place:
            self._saved, self._has_comments = draft.to_yaml(), "#" in text
        root = self._node.root if self._node else ("campaign",)
        self._validate()
        self._rebuild_outline(root)

    # -- running ---------------------------------------------------------------

    def action_run(self) -> None:
        if self._campaign_running:
            # Already going: show it rather than refusing to do anything.
            self._watch_run()
            return
        self._validate()
        if self._spec is None:
            self._rebuild_outline(())
            self.notify(
                f"{len(self._issues)} problem(s) to fix first.",
                title="Run blocked",
                severity="error",
            )
            return
        self._snapshot = self._spec
        self._campaign_running = True
        self._cancel.clear()
        self._sync_run_controls()
        self._run_lines.clear()
        self._note(
            logging.INFO,
            "campaign · running a snapshot: edits from now on apply to the next run",
        )
        self._watch_run()
        self._update_doc_bar()
        self.run_worker(self._execute, thread=True, exclusive=True, name="campaign-run")

    def _execute(self) -> None:
        from hackagent.orchestrator.campaign import resolve_campaign, run_campaign

        spec = self._snapshot
        if spec is None:
            return

        # The checks ``hackagent campaign validate`` runs, before anything is
        # attacked: the form only knows the file is well formed, while this
        # loads the goals and builds every model. What it resolved is what the
        # run then uses. The view shows the log of both, down to the run's
        # closing summary: from INFO, or DEBUG when the CLI's log shows it.
        self.app.call_from_thread(
            self._note, logging.INFO, "campaign · checking goals, models and judges"
        )
        with capture(_RunLog(self._incoming), min(shown_level(), logging.INFO)):
            try:
                resolved = resolve_campaign(spec, settings=self.cli_config.settings)
            except Exception as exc:
                self.app.call_from_thread(
                    self._finish, logging.ERROR, f"campaign rejected: {exc}"
                )
                return
            if self._cancel.is_set():
                self.app.call_from_thread(
                    self._finish, logging.WARNING, "campaign stopped"
                )
                return
            try:
                run_campaign(
                    spec,
                    cancel=self._cancel,
                    settings=getattr(self.cli_config, "settings", None),
                    resolved=resolved,
                )
            except Exception as exc:
                if self._cancel.is_set():
                    self.app.call_from_thread(
                        self._finish, logging.WARNING, "campaign stopped"
                    )
                else:
                    self.app.call_from_thread(
                        self._finish, logging.ERROR, f"campaign failed: {exc}"
                    )
                return
        self.app.call_from_thread(self._finish)

    def _note(self, level: int, message: str) -> None:
        """A line of the view's own, written as a line of the run's log."""
        self._log(
            log_markup(
                logging.makeLogRecord(
                    {
                        "name": __name__,
                        "levelno": level,
                        "levelname": logging.getLevelName(level),
                        "msg": message,
                    }
                )
            )
        )

    def _finish(self, level: Optional[int] = None, message: str = "") -> None:
        """End the run; ``message`` says why it ended early, if it did."""
        # The run's last lines come before how it ended.
        self._drain(limit=None)
        self._campaign_running = False
        if level is not None:
            self._note(level, message)
        self._sync_run_controls()
        self._update_doc_bar()

    def action_stop(self) -> None:
        """Stop the running campaign. Bound to F3 and the Stop button."""
        self._stop()

    def _stop(self) -> None:
        if self._campaign_running:
            self._cancel.set()
            self.query_one("#stop", Button).disabled = True
            self._note(logging.WARNING, "campaign · stopping after the current step")

    def refresh_data(self) -> None:
        self._validate()


class _RunLog(logging.Handler):
    """The run view's handler of the run's log: each line, written as the CLI
    writes it to a file and coloured as a log viewer colours it.

    It only queues them for the view, which draws them on its own thread:
    the run never waits for the screen.
    """

    def __init__(self, queue: SimpleQueue[str]) -> None:
        super().__init__()
        self.queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put(log_markup(record))
        except Exception:
            self.handleError(record)


__all__ = ["CampaignBuilder"]
