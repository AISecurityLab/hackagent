# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dynamic attack and judge rows for the Attacks tab.

Each :class:`AttackRow` is one attack in the campaign: its technique, its own
attacker model (which fills every LLM role the technique declares), and its
algorithm parameters. Each :class:`JudgeRow` is one judge in the evaluation
panel. Rows are added and removed from the form, so a campaign can run several
attacks and be scored by several judges.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Collapsible,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TextArea,
)
from textual.widgets._select import NoSelection

from hackagent.attacks.techniques.registry import get_attack_class
from hackagent.core.defaults import DEFAULT_ATTACKER_IDENTIFIER
from hackagent.evaluation.judges import EVALUATOR_MAP
from hackagent.interfaces.tui.forms import (
    ConfigField,
    FieldType,
    get_attack_config_spec,
)

from hackagent.interfaces.tui.views.attacks.helpers import (
    _AGENT_TYPE_CHOICES,
    _escape,
    _strategy_focus_choices,
    model_config_from_fields,
)


def _cast(cfg_field: ConfigField, raw: Any) -> Any:
    """Cast a raw widget value to the field's Python type, best-effort."""
    if raw is None or raw == "":
        return None
    if cfg_field.field_type == FieldType.INTEGER:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if cfg_field.field_type == FieldType.FLOAT:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return raw
    if cfg_field.field_type == FieldType.BOOLEAN:
        if isinstance(raw, bool):
            return raw
        lowered = str(raw).strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return raw


def _param_widget(cfg_field: ConfigField):
    """The typed widget for one attack parameter field."""
    if cfg_field.field_type == FieldType.CHOICE:
        return Select(cfg_field.choices or [], classes="row-param")
    if cfg_field.field_type == FieldType.BOOLEAN:
        return Switch(value=bool(cfg_field.default), classes="row-param")
    if cfg_field.field_type == FieldType.TEXT:
        area = TextArea(
            "" if cfg_field.default is None else str(cfg_field.default),
            classes="row-param",
        )
        area.styles.height = 4
        return area
    placeholder = ""
    if cfg_field.field_type == FieldType.INTEGER:
        placeholder = "integer"
    elif cfg_field.field_type == FieldType.FLOAT:
        placeholder = "number"
    return Input(
        value="" if cfg_field.default is None else str(cfg_field.default),
        placeholder=placeholder,
        classes="row-param",
    )


class AttackRow(Vertical):
    """One attack: technique + its own attacker model + parameters."""

    DEFAULT_CLASSES = "attack-row"

    def __init__(self, attack_type: Optional[str] = None) -> None:
        super().__init__()
        choices = _strategy_focus_choices()
        self._initial_type = attack_type or (choices[0][1] if choices else None)
        # field key -> (field, widget), rebuilt whenever the technique changes.
        self._param_widgets: Dict[str, Tuple[ConfigField, Any]] = {}

    def compose(self) -> ComposeResult:
        choices = _strategy_focus_choices()
        with Horizontal(classes="row-head"):
            yield Select(
                choices,
                value=self._initial_type if self._initial_type else Select.BLANK,
                classes="row-attack-type",
            )
            yield Button("✕", classes="remove-row", variant="error")
        yield Static("", classes="row-attack-desc")
        yield Label("Attacker model:")
        yield Input(
            value=DEFAULT_ATTACKER_IDENTIFIER,
            placeholder="e.g., ollama/llama3",
            classes="row-attacker-id",
        )
        yield Label("Attacker type:")
        yield Select(_AGENT_TYPE_CHOICES, value="ollama", classes="row-attacker-type")
        yield Label("Attacker endpoint (optional):")
        yield Input(
            placeholder="blank for the local default", classes="row-attacker-endpoint"
        )
        with Collapsible(title="Parameters", collapsed=True):
            yield Vertical(classes="row-params")

    def on_mount(self) -> None:
        self._render_params()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Re-render the parameter fields when the technique changes."""
        if event.select.has_class("row-attack-type"):
            self._render_params()

    # -- technique + params ------------------------------------------------

    def attack_type(self) -> Optional[str]:
        value = self.query_one(".row-attack-type", Select).value
        if isinstance(value, NoSelection) or not value:
            return None
        return str(value)

    def _render_params(self) -> None:
        container = self.query_one(".row-params", Vertical)
        container.remove_children()
        self._param_widgets = {}
        attack_type = self.attack_type()

        desc = self.query_one(".row-attack-desc", Static)
        spec = get_attack_config_spec(attack_type) if attack_type else None
        if spec is None:
            desc.update("")
            return
        desc.update(f"[dim]{_escape(spec.description)}[/dim]")

        widgets: List[Any] = []
        for cfg_field in spec.fields:
            label = cfg_field.label + (" *" if cfg_field.required else "")
            widgets.append(Label(label))
            widget = _param_widget(cfg_field)
            self._param_widgets[cfg_field.key] = (cfg_field, widget)
            widgets.append(widget)
        if widgets:
            container.mount(*widgets)
            self._apply_param_defaults()

    def _apply_param_defaults(self) -> None:
        """Select widgets take their default after mount (a blank Select is
        otherwise left on the ``NoSelection`` sentinel)."""

        def _apply() -> None:
            for cfg_field, widget in self._param_widgets.values():
                if isinstance(widget, Select) and cfg_field.default is not None:
                    try:
                        widget.value = cfg_field.default
                    except Exception:
                        pass

        self.call_after_refresh(_apply)

    def _collect_params(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Return ``(parameters, raw_flat)`` read from the parameter widgets.

        ``parameters`` drops unset values (what the spec receives); ``raw_flat``
        keeps every field for the spec's own validation.
        """
        raw_flat: Dict[str, Any] = {}
        for key, (cfg_field, widget) in self._param_widgets.items():
            if isinstance(widget, Select):
                value = widget.value
                if isinstance(value, NoSelection):
                    value = cfg_field.default
            elif isinstance(widget, Switch):
                value = widget.value
            elif isinstance(widget, TextArea):
                value = widget.text
            else:
                value = widget.value
            raw_flat[key] = _cast(cfg_field, value)
        parameters = {k: v for k, v in raw_flat.items() if v is not None}
        return parameters, raw_flat

    def _attacker(self) -> Optional[Dict[str, Any]]:
        return model_config_from_fields(
            self.query_one(".row-attacker-id", Input).value,
            self.query_one(".row-attacker-type", Select).value,
            self.query_one(".row-attacker-endpoint", Input).value,
        )

    def to_block(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """A campaign ``attacks[]`` block, or ``(None, error)`` if invalid."""
        attack_type = self.attack_type()
        if not attack_type:
            return None, "Select an attack type for every attack row."

        parameters, raw_flat = self._collect_params()
        spec = get_attack_config_spec(attack_type)
        errors = spec.validate(raw_flat) if spec else []
        if errors:
            return None, f"{attack_type}: " + "; ".join(errors)

        roles = sorted(get_attack_class(attack_type).params_type.completion_roles())
        attacker = self._attacker()
        if roles and attacker is None:
            return None, (
                f"'{attack_type}' needs an attacker model — fill in its "
                "Attacker fields."
            )

        block: Dict[str, Any] = {"name": attack_type, "parameters": parameters}
        if roles:
            block["roles"] = {role: attacker for role in roles}
        return block, None


class JudgeRow(Vertical):
    """One judge in the evaluation panel: a model and how it scores."""

    DEFAULT_CLASSES = "judge-row"

    def compose(self) -> ComposeResult:
        with Horizontal(classes="row-head"):
            yield Input(
                value=DEFAULT_ATTACKER_IDENTIFIER,
                placeholder="e.g., ollama/llama3",
                classes="row-judge-id",
            )
            yield Button("✕", classes="remove-row", variant="error")
        yield Label("Judge type:")
        yield Select(_AGENT_TYPE_CHOICES, value="ollama", classes="row-judge-type")
        yield Label("Judge endpoint (optional):")
        yield Input(
            placeholder="blank for the local default", classes="row-judge-endpoint"
        )
        yield Label("Scoring:")
        yield Select(
            [(name, name) for name in sorted(EVALUATOR_MAP)],
            value="harmbench",
            classes="row-judge-scoring",
        )

    def to_config(self) -> Optional[Dict[str, Any]]:
        """A campaign judge config, or ``None`` when no judge name is entered."""
        scoring = self.query_one(".row-judge-scoring", Select).value
        scoring_type = "harmbench" if isinstance(scoring, NoSelection) else str(scoring)
        return model_config_from_fields(
            self.query_one(".row-judge-id", Input).value,
            self.query_one(".row-judge-type", Select).value,
            self.query_one(".row-judge-endpoint", Input).value,
            extra={"scoring": {"type": scoring_type}},
        )


__all__ = ["AttackRow", "JudgeRow"]
