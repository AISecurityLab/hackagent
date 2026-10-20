# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""One form row per schema field: label, value, and where the value comes from."""

from __future__ import annotations

from typing import Any, Optional

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Select, Static, Switch, TextArea

from .draft import CampaignDraft
from .schema import FieldDef, Path


class FieldRow(Horizontal):
    """Edits the value at ``root + field.path``; empty means the default."""

    DEFAULT_CSS = """
    FieldRow { height: auto; margin-bottom: 1; }
    FieldRow > .label {
        width: 26; color: $text-muted; padding-right: 2; text-align: right;
    }
    /* A compact Input draws no border, so without a background of its own the
       editable area had no visible edge and ran into the label. */
    FieldRow > .value { width: 34; background: $boost; }
    FieldRow > Switch.value { background: transparent; }
    FieldRow > TextArea.value { height: 5; }
    FieldRow > .state {
        width: 1fr; padding-left: 2; color: $text-muted;
        text-wrap: nowrap; text-overflow: ellipsis;
    }
    FieldRow:focus-within > .label { color: $accent; text-style: bold; }
    FieldRow:focus-within > .value { background: $boost-lighten-1; }
    FieldRow.-set > .label { color: $text; }
    FieldRow.-error > .label { color: $error; }
    FieldRow.-error > .value { background: $error 20%; }
    """

    class Edited(Message):
        """The row wrote to (or reset) the draft."""

        def __init__(self, row: "FieldRow") -> None:
            super().__init__()
            self.row = row

    def __init__(
        self,
        field: FieldDef,
        root: Path,
        draft: CampaignDraft,
        box: Path = (),
    ) -> None:
        super().__init__()
        self.field = field
        self.root = root
        self.draft = draft
        self.box = box
        self.issue: Optional[str] = None
        # Kept rather than queried: Textual can remove the row's children
        # before a pending mount refreshes it, as when the app closes at once.
        self._state = Static("", classes="state")

    @property
    def path(self) -> Path:
        return self.root + self.field.path

    def compose(self) -> ComposeResult:
        yield Static(_label_markup(self.field.label_in(self.box)), classes="label")
        yield self._editor()
        yield self._state

    def on_mount(self) -> None:
        self.refresh_state()

    def _editor(self) -> Widget:
        field = self.field
        found, value = self.draft.get(self.path)
        if field.kind == "bool":
            current = value if found else field.default
            return Switch(value=bool(current), classes="value")
        if field.kind in ("choice", "tristate"):
            options = [(choice, choice) for choice in field.choices]
            selected: Any = Select.NULL
            if found:
                text = _text(value)
                selected = text if text in field.choices else Select.NULL
            prompt = field.default_text or (
                "required" if field.required else "not sent"
            )
            return Select(
                options,
                prompt=prompt,
                value=selected,
                allow_blank=True,
                compact=True,
                classes="value",
            )
        if field.kind == "list":
            items = value if found and isinstance(value, list) else []
            return TextArea(
                "\n".join(str(item) for item in items),
                placeholder=field.default_text or "one per line",
                compact=True,
                classes="value",
            )
        return Input(
            value=_text(value) if found else "",
            placeholder=field.default_text
            or ("required" if field.required else "not sent"),
            type={"int": "integer", "float": "number"}.get(field.kind, "text"),
            compact=True,
            classes="value",
        )

    # -- editing ---------------------------------------------------------

    def _commit(self, value: Any) -> None:
        found, current = self.draft.get(self.path)
        if found and current == value:
            return
        if self.field.discriminator and value is not None:
            # The tag is structural, not an override: without it the document
            # cannot say which variant it is, even when it matches the default.
            if self.draft.set(self.path, value):
                self.refresh_state()
                self.post_message(self.Edited(self))
            return
        if value is None or self.field.is_default(value):
            changed = self.draft.delete(self.path, keep=len(self.root))
        else:
            changed = self.draft.set(self.path, value)
        if changed:
            self.refresh_state()
            self.post_message(self.Edited(self))

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        text = event.value.strip()
        if not text:
            self._commit(None)
            return
        try:
            value: Any = {"int": int, "float": float}.get(self.field.kind, str)(text)
        except ValueError:
            return
        self._commit(value)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        event.stop()
        self._commit(event.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        if event.value is Select.NULL:
            self._commit(None)
        elif self.field.kind == "tristate":
            self._commit(event.value == "true")
        else:
            # The widget holds text; the campaign needs the schema's type.
            self._commit(self.field.choice_value(str(event.value)))

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        event.stop()
        items = [line.strip() for line in event.text_area.text.splitlines()]
        self._commit([item for item in items if item] or None)

    def reset(self) -> None:
        """Drop the user's value so the default applies again."""
        if self.field.discriminator:
            return  # removing the tag would leave the document unreadable
        editor = self.query_one(".value")
        if isinstance(editor, Switch):
            editor.value = bool(self.field.default)
        elif isinstance(editor, Select):
            editor.value = Select.NULL
        elif isinstance(editor, TextArea):
            editor.text = ""
        elif isinstance(editor, Input):
            editor.value = ""
        self._commit(None)

    # -- state -------------------------------------------------------------

    def refresh_state(self) -> None:
        found, value = self.draft.get(self.path)
        edited = found and not self.field.is_default(value)
        self.set_class(edited, "-set")
        self.set_class(self.issue is not None, "-error")
        if self.issue is not None:
            text = f"[$error]✗ {escape(self.issue)}[/]"
        elif edited:
            default = self.field.default_text
            text = "[$accent]●[/] edited" + (
                f" [dim]· default {escape(default)}[/dim]" if default else ""
            )
        elif self.field.required:
            text = "[$warning]required[/]"
        elif self.field.default_text:
            text = "[dim]default[/dim]"
        else:
            # No default and not required: leaving it out sends nothing, and
            # whatever is on the other end picks.
            text = "[dim]not sent[/dim]"
        self._state.update(text)


def _label_markup(label: str) -> str:
    """The field's key, with any parent path dimmed so the key stands out.

    The label is the YAML key you are editing, so it is shown verbatim rather
    than prettified; only the emphasis changes.
    """
    parent, _, leaf = label.rpartition(".")
    if not parent:
        return escape(label)
    return f"[dim]{escape(parent)}.[/dim]{escape(leaf)}"


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return "" if value is None else str(value)


__all__ = ["FieldRow"]
