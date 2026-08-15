# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Strategy config form rendering, collection and prefill."""

from typing import Any, Dict, List, Optional

from textual.containers import Vertical
from textual.widgets import (
    Checkbox,
    Collapsible,
    Input,
    Label,
    RadioButton,
    Select,
    SelectionList,
    Static,
    Switch,
    TextArea,
)
from textual.widgets._select import NoSelection


from hackagent.cli.tui.attack_specs import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
    get_all_attack_specs,
    get_attack_config_spec,
)


from hackagent.cli.tui.views.attacks.helpers import (
    _AGENT_TYPE_CHOICES,
    _escape,
    _field_widget_id,
)


class AttacksFormMixin:
    """Strategy config form rendering, collection and prefill.

    Mixed into :class:`~hackagent.cli.tui.views.attacks.tab.AttacksTab`.
    """

    def _sync_configuring_options(self, selected: List[str]) -> None:
        """Restrict the 'Configuring' dropdown to only the checked attacks,
        in check order, so the config form can't be opened for a strategy
        that isn't actually part of the current run.

        A no-op if *selected* is unchanged since the last call — a single
        bulk selection change (e.g. selecting the N default campaign
        attacks in a loop) posts one ``SelectedChanged`` message *per*
        ``.select()`` call rather than one combined message, so this method
        can be invoked several times in a row for what is conceptually one
        update; skipping true no-ops avoids redundantly rebuilding the
        dropdown's options each time.
        """
        if selected == self._configuring_options_keys:
            return
        self._configuring_options_keys = list(selected)

        all_specs = get_all_attack_specs()
        focus_choices = [
            (all_specs[key].display_name, key) for key in selected if key in all_specs
        ]
        focus_select = self.query_one("#attack-strategy-focus", Select)

        if not focus_choices:
            # Nothing checked — leave the dropdown empty; execute-time
            # validation already rejects an empty selection.
            focus_select.set_options([])
            return

        focus_select.set_options(focus_choices)
        new_focus = (
            self._focused_strategy
            if self._focused_strategy in selected
            else selected[0]
        )
        focus_select.value = new_focus
        if new_focus != self._focused_strategy:
            self._switch_focused_strategy(new_focus)

    def _sync_chain_mode_visibility(self, selected: Optional[List[str]] = None) -> None:
        """Show the hack_chain escalation toggle only when 2+ attacks are checked."""
        if selected is None:
            try:
                selected = list(
                    self.query_one("#attack-strategies", SelectionList).selected
                )
            except Exception:
                selected = []
        is_chain = len(selected) > 1
        try:
            self.query_one("#escalate-only-mitigated", Checkbox).display = is_chain
            self.query_one("#escalate-only-mitigated-help", Static).display = is_chain
        except Exception:
            pass

    def _switch_focused_strategy(self, technique_key: str) -> None:
        """Switch which strategy's config form is displayed.

        Caches the currently-displayed strategy's field values first (so
        switching back to it later, e.g. after adding it to the chain
        selection, restores prior edits instead of resetting to defaults),
        then renders *technique_key*'s form, prefilling it from the cache if
        it was previously configured in this session.

        A no-op if *technique_key* is already focused and rendered — avoids
        redundantly rebuilding the same config form (e.g. when the
        "Configuring" Select's own internal blank-reset-then-restore cycle
        during ``set_options()`` briefly reports the previous value again).
        """
        if technique_key == self._focused_strategy and self._current_spec is not None:
            return
        if self._focused_strategy and self._focused_strategy != technique_key:
            self._strategy_value_cache[self._focused_strategy] = (
                self._collect_strategy_config()
            )
        self._focused_strategy = technique_key
        self._render_strategy_config(technique_key)
        cached = self._strategy_value_cache.get(technique_key)
        if cached and self._current_spec:
            # Delay widget value assignment until after refresh to ensure widgets are fully initialized
            self.call_after_refresh(
                lambda: self._apply_values_to_spec_widgets(self._current_spec, cached)
            )

    def _apply_values_to_spec_widgets(
        self, spec: AttackConfigSpec, flat_values: Dict[str, Any]
    ) -> None:
        """Write *flat_values* (dotted-key -> value) into the mounted widgets
        for *spec*'s fields, skipping any field without a mounted widget
        (e.g. an advanced field while advanced mode is off)."""
        for cfg_field in spec.fields:
            if cfg_field.key not in flat_values:
                continue
            widget_id = _field_widget_id(cfg_field)
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                continue
            value = flat_values[cfg_field.key]
            if isinstance(widget, Select):
                # None isn't a legal Select value (only the NoSelection sentinel is) — skip and keep its constructed default.
                if value is not None:
                    try:
                        widget.value = value
                    except Exception:
                        # Textual Select widget may not be fully initialized yet; skip this value.
                        pass
            elif isinstance(widget, Switch):
                widget.value = bool(value)
            elif isinstance(widget, TextArea):
                widget.text = "" if value is None else str(value)
            elif isinstance(widget, Input):
                widget.value = "" if value is None else str(value)

    def _resolve_config_for_strategy(self, technique_key: str) -> Dict[str, Any]:
        """Return the flat (dotted-key) config values for *technique_key*.

        If it is the strategy currently displayed in the form, values are
        read live from the widgets (picking up not-yet-cached edits).
        Otherwise, the cached values from the last time it was configured
        are used, falling back to the spec's defaults if it was never
        opened in this session.
        """
        spec = get_attack_config_spec(technique_key)
        if spec is None:
            return {}
        if technique_key == self._focused_strategy and self._current_spec is spec:
            return self._collect_strategy_config()
        cached = self._strategy_value_cache.get(technique_key)
        if cached is not None:
            return cached
        return spec.defaults_dict()

    def _render_strategy_config(self, technique_key: str) -> None:
        """Clear and re-render the strategy-specific config fields.

        Args:
            technique_key: Technique identifier (e.g. ``"advprefix"``).
        """
        spec = get_attack_config_spec(technique_key)
        if spec is None:
            return

        # Keep internal state aligned with the current checkbox value.
        try:
            pinned = bool(self.query_one("#advanced-toggle", Checkbox).value)
            self._show_advanced = (
                pinned or self._advanced_hover_preview or self._advanced_focus_preview
            )
        except Exception:
            pass

        self._current_spec = spec

        # Update description
        desc_widget = self.query_one("#strategy-description", Static)
        desc_widget.update(f"[dim]{_escape(spec.description)}[/dim]")

        # Remove old config widgets
        container = self.query_one("#strategy-config-container", Vertical)
        container.remove_children()

        # Group fields by section
        for section in spec.sections():
            fields = spec.fields_for_section(
                section, include_advanced=self._show_advanced
            )
            if not fields:
                continue

            section_widgets: List[Any] = []

            for cfg_field in fields:
                widget_id = _field_widget_id(cfg_field)
                # Label with optional tooltip
                label_text = cfg_field.label
                if cfg_field.required:
                    label_text += " *"
                section_widgets.append(Label(label_text))

                if cfg_field.description:
                    section_widgets.append(
                        Static(
                            f"[dim]{_escape(cfg_field.description)}[/dim]",
                            classes="field-description",
                        )
                    )

                # Render the appropriate widget
                widget = self._create_field_widget(cfg_field, widget_id)
                section_widgets.append(widget)

            # Build collapsible with children upfront to avoid mount-order issues.
            collapsible = Collapsible(*section_widgets, title=section, collapsed=False)
            container.mount(collapsible)

        # Apply default values to Select widgets after mount
        def _apply_defaults() -> None:
            for cfg_field in spec.fields:
                if (
                    cfg_field.field_type == FieldType.CHOICE
                    and cfg_field.default is not None
                ):
                    widget_id = _field_widget_id(cfg_field)
                    try:
                        widget = self.query_one(f"#{widget_id}")
                        if isinstance(widget, Select):
                            widget.value = cfg_field.default
                    except Exception:
                        pass

        self.call_after_refresh(_apply_defaults)

        # Clear validation errors
        self.query_one("#validation-errors", Static).update("")

    def _create_field_widget(self, cfg_field: ConfigField, widget_id: str) -> Any:
        """Create the appropriate Textual widget for a :class:`ConfigField`."""
        if self._show_advanced:
            # Advanced mode intentionally uses plain text boxes for all fields.
            default_str = ""
            if cfg_field.default is not None:
                if isinstance(cfg_field.default, bool):
                    default_str = "true" if cfg_field.default else "false"
                else:
                    default_str = str(cfg_field.default)

            placeholder = ""
            if cfg_field.field_type == FieldType.BOOLEAN:
                placeholder = "true / false"
            elif cfg_field.field_type == FieldType.CHOICE and cfg_field.choices:
                placeholder = ", ".join(str(choice[1]) for choice in cfg_field.choices)
            elif cfg_field.min_value is not None and cfg_field.max_value is not None:
                placeholder = f"{cfg_field.min_value} – {cfg_field.max_value}"
            elif cfg_field.field_type == FieldType.INTEGER:
                placeholder = "integer"
            elif cfg_field.field_type == FieldType.FLOAT:
                placeholder = "number"

            return Input(value=default_str, placeholder=placeholder, id=widget_id)

        if cfg_field.field_type == FieldType.CHOICE:
            return Select(
                cfg_field.choices or [],
                id=widget_id,
            )

        if cfg_field.field_type == FieldType.BOOLEAN:
            return Switch(
                value=bool(cfg_field.default)
                if cfg_field.default is not None
                else False,
                id=widget_id,
            )

        if cfg_field.field_type == FieldType.TEXT:
            ta = TextArea(
                str(cfg_field.default) if cfg_field.default is not None else "",
                id=widget_id,
            )
            ta.styles.height = 4
            return ta

        # STRING / INTEGER / FLOAT → Input
        placeholder = ""
        if cfg_field.min_value is not None and cfg_field.max_value is not None:
            placeholder = f"{cfg_field.min_value} – {cfg_field.max_value}"
        elif cfg_field.field_type == FieldType.INTEGER:
            placeholder = "integer"
        elif cfg_field.field_type == FieldType.FLOAT:
            placeholder = "number"

        return Input(
            value=str(cfg_field.default) if cfg_field.default is not None else "",
            placeholder=placeholder,
            id=widget_id,
        )

    # ------------------------------------------------------------------
    # Collect values from dynamic config
    # ------------------------------------------------------------------

    def _collect_strategy_config(self) -> Dict[str, Any]:
        """Read all strategy-specific config field values from the UI.

        Returns:
            A flat ``{key: value}`` dict with parsed values.
        """
        if self._current_spec is None:
            return {}

        values: Dict[str, Any] = {}
        for cfg_field in self._current_spec.fields:
            if cfg_field.advanced and not self._show_advanced:
                # Use default for hidden advanced fields
                if cfg_field.default is not None:
                    values[cfg_field.key] = cfg_field.default
                continue

            widget_id = _field_widget_id(cfg_field)
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                # Widget not mounted (e.g. section collapsed)
                if cfg_field.default is not None:
                    values[cfg_field.key] = cfg_field.default
                continue

            raw: Any = None
            if isinstance(widget, Select):
                raw = widget.value
                if isinstance(raw, NoSelection):
                    # Fall back to the field's default rather than caching a bare None.
                    raw = cfg_field.default
            elif isinstance(widget, Switch):
                raw = widget.value
            elif isinstance(widget, TextArea):
                raw = widget.text
            elif isinstance(widget, Input):
                raw = widget.value
            else:
                raw = getattr(widget, "value", None)

            # Cast to correct Python type
            if raw is not None and raw != "":
                if cfg_field.field_type == FieldType.INTEGER:
                    try:
                        raw = int(raw)
                    except (TypeError, ValueError):
                        pass
                elif cfg_field.field_type == FieldType.FLOAT:
                    try:
                        raw = float(raw)
                    except (TypeError, ValueError):
                        pass
                elif cfg_field.field_type == FieldType.BOOLEAN:
                    if isinstance(raw, str):
                        lowered = raw.strip().lower()
                        if lowered in {"true", "1", "yes", "y", "on"}:
                            raw = True
                        elif lowered in {"false", "0", "no", "n", "off"}:
                            raw = False

            values[cfg_field.key] = raw

        return values

    def _expand_dotted_keys(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        """Expand dotted keys like ``"attacker.model"`` into nested dicts.

        Example::

            {"attacker.model": "gpt-4", "n_iterations": 5}
            → {"attacker": {"model": "gpt-4"}, "n_iterations": 5}
        """
        result: Dict[str, Any] = {}
        for key, value in flat.items():
            parts = key.split(".")
            target = result
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        return result

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    def _prefill_form(self) -> None:
        """Pre-fill form fields with initial data."""
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

        strategy_value = self.initial_data.get(
            "attack_type"
        ) or self._attack_config_overrides.get("attack_type")
        if strategy_value:
            strategy_value = str(strategy_value)
            strategies = self.query_one("#attack-strategies", SelectionList)
            strategies.deselect_all()
            strategies.select(strategy_value)

            def _finish_strategy_prefill(key: str = strategy_value) -> None:
                # Deferred for the same reason as
                # `_select_default_campaign_attacks`: let the queued
                # `SelectedChanged` messages from the calls above drain
                # before touching the "Configuring" dropdown. Field-value
                # prefill runs in the same deferred step, after it, so
                # `_current_spec` reflects `key` by the time it runs.
                self._sync_configuring_options([key])
                self._sync_chain_mode_visibility([key])
                if self._attack_config_overrides:
                    self._prefill_strategy_fields(self._attack_config_overrides)

            self.call_after_refresh(_finish_strategy_prefill)
        elif self._attack_config_overrides:
            self._prefill_strategy_fields(self._attack_config_overrides)

        goals_from_overrides = self._attack_config_overrides.get("goals")
        if isinstance(goals_from_overrides, list) and goals_from_overrides:
            self.query_one("#attack-goals", TextArea).text = str(
                goals_from_overrides[0]
            )

        # ── Prefill dataset vs goals toggle ──
        dataset_cfg = self._attack_config_overrides.get("dataset")
        if isinstance(dataset_cfg, dict) and dataset_cfg.get("preset"):
            self.query_one("#radio-dataset", RadioButton).value = True
            self.query_one("#goals-container").display = False
            self.query_one("#dataset-container").display = True
            self.query_one("#dataset-preset", Select).value = dataset_cfg["preset"]
            if "limit" in dataset_cfg:
                self.query_one("#dataset-limit", Input).value = str(
                    dataset_cfg["limit"]
                )
            if "shuffle" in dataset_cfg:
                self.query_one("#dataset-shuffle", Switch).value = bool(
                    dataset_cfg["shuffle"]
                )
            if "seed" in dataset_cfg:
                self.query_one("#dataset-seed", Input).value = str(dataset_cfg["seed"])

    @staticmethod
    def _flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dict keys using dot notation."""
        flat: Dict[str, Any] = {}
        for key, value in data.items():
            dotted_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.update(AttacksFormMixin._flatten_dict(value, dotted_key))
            else:
                flat[dotted_key] = value
        return flat

    def _prefill_strategy_fields(self, attack_config: Dict[str, Any]) -> None:
        """Pre-fill strategy-specific form fields from attack config overrides."""
        if not self._current_spec:
            return

        flat_overrides = self._flatten_dict(attack_config)
        advanced_keys = {
            field.key for field in self._current_spec.fields if field.advanced
        }

        if advanced_keys.intersection(flat_overrides.keys()):
            advanced_toggle = self.query_one("#advanced-toggle", Checkbox)
            advanced_toggle.value = True
            self._show_advanced = True
            self._render_strategy_config(self._current_spec.technique_key)

        for cfg_field in self._current_spec.fields:
            if cfg_field.key not in flat_overrides:
                continue

            widget_id = _field_widget_id(cfg_field)
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                continue

            value = flat_overrides[cfg_field.key]

            if isinstance(widget, Select):
                widget.value = value
            elif isinstance(widget, Switch):
                widget.value = bool(value)
            elif isinstance(widget, TextArea):
                widget.text = "" if value is None else str(value)
            elif isinstance(widget, Input):
                widget.value = "" if value is None else str(value)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
