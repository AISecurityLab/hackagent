# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every key the TUI answers to, said once.

A screen binds a key by its name here (:func:`key`), so the same key does
the same thing and is called the same in every footer, and the help screen
(F1) is written from the same table: the keys of the screen it is opened
on (:func:`known`), with what each one does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from textual.binding import Binding


@dataclass(frozen=True)
class Key:
    """A key: what is pressed, its word in the footer, what it does."""

    keys: str
    word: str
    does: str
    display: Optional[str] = None


#: The keys, by name.
KEYS: dict[str, Key] = {
    "back": Key("escape", "Back", "go back where you came from", "esc"),
    "open": Key("enter", "Open", "open what is highlighted"),
    "choose": Key("down", "Choose", "move to the next or previous one", "↑↓"),
    "help": Key("f1", "Help", "show these keys"),
    "home": Key("f2", "Home", "go back to the welcome screen"),
    "run": Key("ctrl+r", "Run", "run the campaign"),
    "stop": Key("f3", "Stop", "stop the run after the current step"),
    "save": Key("ctrl+s", "Save", "save the campaign to a file"),
    "open_file": Key("ctrl+o", "Open file", "open a campaign file"),
    "edit_yaml": Key("f4", "Edit YAML", "edit the whole campaign in $EDITOR"),
    "reset": Key("ctrl+t", "Reset field", "put the field back to its default"),
    "remove": Key("delete", "Remove", "remove the selected attack or judge"),
    "refresh": Key("f5", "Refresh", "read the runs again"),
    "switch_store": Key("s", "Switch store", "read runs from the other store"),
    "export_csv": Key("ctrl+e", "Export CSV", "export the results as CSV"),
    "export_json": Key("ctrl+j", "Export JSON", "export the results as JSON"),
    "copy": Key("ctrl+y", "Copy", "copy the run's log, or the selection"),
    "quit": Key("q", "Quit", "leave HackAgent"),
}


def key(
    name: str,
    action: Optional[str] = None,
    *,
    show: bool = True,
    priority: bool = False,
    keys: Optional[str] = None,
) -> Binding:
    """The binding of the key called ``name``, running ``action`` (``name``
    by default). ``keys`` adds keys that do the same, as ``up`` does for
    ``choose``."""
    item = KEYS[name]
    return Binding(
        keys or item.keys,
        action or name,
        item.word,
        show=show,
        priority=priority,
        key_display=item.display,
    )


def known(binding: Binding) -> Optional[Key]:
    """The key of this table a binding is, or ``None`` for one of Textual's
    own (moving inside a tree, focus, the command palette)."""
    for item in KEYS.values():
        if item.word == binding.description and binding.key in item.keys.split(","):
            return item
    return None


__all__ = ["KEYS", "Key", "key", "known"]
