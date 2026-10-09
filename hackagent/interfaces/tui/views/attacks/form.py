# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Form prefill for the Attacks tab."""

from textual.widgets import Input, Select, TextArea


from hackagent.interfaces.tui.views.attacks.helpers import _AGENT_TYPE_CHOICES


class AttacksFormMixin:
    """Prefill the static target/goals/timeout fields from ``initial_data``.

    Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.
    The attack and judge rows carry their own state and are not prefilled here.
    """

    def _prefill_form(self) -> None:
        """Pre-fill the static form fields with initial data."""
        if "agent_name" in self.initial_data:
            self.query_one("#agent-name", Input).value = self.initial_data["agent_name"]
        if "agent_type" in self.initial_data:
            agent_type_value = self.initial_data["agent_type"]
            # Only set known choices — an unrecognised value would raise
            # InvalidSelectValueError and crash the tab on mount.
            valid_types = {value for _, value in _AGENT_TYPE_CHOICES}
            if agent_type_value in valid_types:
                self.query_one("#agent-type", Select).value = agent_type_value
        if "endpoint" in self.initial_data:
            self.query_one("#endpoint-url", Input).value = self.initial_data["endpoint"]
        if "goals" in self.initial_data:
            self.query_one("#attack-goals", TextArea).text = self.initial_data["goals"]
        if "timeout" in self.initial_data:
            self.query_one("#timeout", Input).value = str(self.initial_data["timeout"])
