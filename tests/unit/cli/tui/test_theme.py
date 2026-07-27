# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the shared TUI theme and terminology module."""

from hackagent.cli.tui import theme


class TestOutcomeVocabulary:
    """Evaluation outcomes use a single, defender-polarity vocabulary."""

    def test_successful_jailbreak_is_vulnerable(self) -> None:
        assert theme.classify_evaluation_status("SUCCESSFUL_JAILBREAK") is (
            theme.VULNERABLE
        )

    def test_failed_jailbreak_is_mitigated(self) -> None:
        assert theme.classify_evaluation_status("FAILED_JAILBREAK") is theme.MITIGATED

    def test_error_is_errored(self) -> None:
        assert theme.classify_evaluation_status("ERROR") is theme.ERRORED

    def test_unknown_and_none_are_not_evaluated(self) -> None:
        assert theme.classify_evaluation_status(None) is theme.NOT_EVALUATED
        assert theme.classify_evaluation_status("NOT_EVALUATED") is (
            theme.NOT_EVALUATED
        )
        assert theme.classify_evaluation_status("something else") is (
            theme.NOT_EVALUATED
        )

    def test_enum_like_status_is_unwrapped(self) -> None:
        class _Status:
            value = "SUCCESSFUL_JAILBREAK"

        assert theme.classify_evaluation_status(_Status()) is theme.VULNERABLE

    def test_vulnerable_is_red_and_mitigated_is_green(self) -> None:
        """A vulnerability must never be painted green, and vice versa."""
        assert theme.VULNERABLE.color == "red"
        assert theme.MITIGATED.color == "green"

    def test_render_wraps_label_in_its_own_colour(self) -> None:
        rendered = theme.VULNERABLE.render()
        assert rendered.startswith("[red]")
        assert rendered.endswith("[/red]")
        assert "Vulnerable" in rendered

    def test_css_classes_are_unique(self) -> None:
        classes = [outcome.css_class for outcome in theme.OUTCOMES]
        assert len(set(classes)) == len(classes)
        assert all(css.startswith("-") for css in classes)


class TestRunStateVocabulary:
    """Run lifecycle states map onto a single set of icons and colours."""

    def test_known_states(self) -> None:
        assert theme.classify_run_status("COMPLETED") is theme.RUN_COMPLETED
        assert theme.classify_run_status("running") is theme.RUN_RUNNING
        assert theme.classify_run_status("FAILED") is theme.RUN_FAILED
        assert theme.classify_run_status("PENDING") is theme.RUN_PENDING

    def test_unknown_and_none(self) -> None:
        assert theme.classify_run_status(None) is theme.RUN_UNKNOWN
        assert theme.classify_run_status("whatever") is theme.RUN_UNKNOWN

    def test_render_icon_is_colour_wrapped(self) -> None:
        assert theme.RUN_RUNNING.render_icon() == (
            f"[{theme.RUN_RUNNING.color}]{theme.RUN_RUNNING.icon}"
            f"[/{theme.RUN_RUNNING.color}]"
        )


class TestCssVariables:
    """The brand palette is exposed once, as Textual CSS variables."""

    def test_variables_cover_the_palette(self) -> None:
        variables = theme.css_variables()
        assert variables["brand"] == theme.BRAND_RED
        assert variables["brand-dark"] == theme.BRAND_RED_DARK
        assert variables["brand-darker"] == theme.BRAND_RED_DARKER
        assert variables["brand-hover"] == theme.BRAND_RED_HOVER
        assert variables["brand-text"] == theme.TEXT_ON_BRAND
        assert variables["brand-text-muted"] == theme.TEXT_MUTED

    def test_app_exposes_brand_variables_and_uses_no_raw_hex(self) -> None:
        import re

        from hackagent.cli.config import CLIConfig
        from hackagent.cli.tui.app import HackAgentTUI

        app = HackAgentTUI(CLIConfig())
        variables = app.get_css_variables()
        assert variables["brand"] == theme.BRAND_RED
        assert variables["brand-dark"] == theme.BRAND_RED_DARK
        # Brand colours are referenced through the palette, not re-declared.
        assert not re.search(r"#[0-9a-fA-F]{6}", HackAgentTUI.CSS)
