# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The app is one screen: start from something, then build and run it.

These cover the shell rather than the form: that the welcome screen offers a
campaign worth starting from, that choosing one lands in the builder ready to
run, and that handing the app a campaign skips the welcome entirely.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml
from textual.widgets import Button, Input, Static, Tree

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.app import HackAgentTUI
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.campaign.draft import CampaignDraft
from hackagent.orchestrator.campaign import CampaignResult
from hackagent.interfaces.tui.views.campaign.screens import (
    ConfirmScreen,
    ExampleScreen,
    HelpScreen,
    PathScreen,
    ResultsScreen,
    RunScreen,
)
from hackagent.interfaces.cli.banner import HACKAGENT_BANNER
from hackagent.interfaces.tui.views.campaign.welcome import (
    TAGLINE,
    WelcomeScreen,
    starting_point,
)

WIDE = (120, 40)


def _resolution(spec):
    """What ``resolve_campaign`` hands back, with nothing actually built."""
    return SimpleNamespace(spec=spec, goals=(), attacks=(), panel=None, classifier=None)


@pytest.fixture
def cli_config():
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-key"
    config.base_url = "https://api.test.hackagent.dev"
    config.settings = MagicMock(name="resolved-settings")
    return config


def test_the_starting_point_is_a_campaign_that_runs():
    """The builder must open on something valid, not a form full of errors."""
    draft = CampaignDraft.from_yaml(yaml.safe_dump(starting_point().document))
    spec, issues = draft.validate()
    assert issues == (), [(issue.loc, issue.message) for issue in issues]
    assert spec is not None


def test_the_starting_point_can_be_judged():
    """Without a judge a run records replies but scores nothing."""
    assert starting_point().document["evaluation"]["judges"]


def test_the_starting_point_keeps_its_results_on_this_machine():
    """Nothing the welcome screen offers should need an account to record."""
    draft = CampaignDraft.from_yaml(yaml.safe_dump(starting_point().document))
    spec, issues = draft.validate()

    assert issues == ()
    assert spec is not None
    assert spec.execution.storage.backend == "local"


LOGO_LINES = tuple(HACKAGENT_BANNER.strip("\n").splitlines())


def _rendered(app) -> list[str]:
    """What the terminal actually shows, one string per row."""
    return [
        "".join(segment.text for segment in strip)
        for strip in app.screen._compositor.render_strips()
    ]


def _logo_rows(app) -> list[str]:
    """The rows holding the logo, located by its own first line.

    Matching on content rather than on a glyph: the bottom row of the logo is
    drawn entirely in box characters, so looking for a block character would
    quietly miss it.
    """
    rows = _rendered(app)
    first = LOGO_LINES[0].strip()
    start = next(i for i, row in enumerate(rows) if row.strip() == first)
    found = rows[start : start + len(LOGO_LINES)]
    assert [row.strip() for row in found] == [line.strip() for line in LOGO_LINES]
    return found


class TestShell:
    @pytest.mark.asyncio
    async def test_the_view_starts_at_the_top_of_the_screen(self, cli_config):
        """No title strip above it: the builder already says what it is."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rows = _rendered(app)

        assert "ready to run" in rows[0]

    @pytest.mark.asyncio
    async def test_campaign_execution_receives_the_tui_account_settings(
        self, cli_config
    ):
        captured = {}

        def fake_run(_spec, **kwargs):
            captured["settings"] = kwargs["settings"]
            return CampaignResult(campaign_name="test", run_id="run-1", dry_run=True)

        app = HackAgentTUI(
            cli_config,
            initial_data={"campaign_yaml": yaml.safe_dump(starting_point().document)},
        )
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            builder._snapshot = builder.draft.validate()[0]
            with (
                # The run resolves the campaign first; that is covered on its
                # own, and doing it here would load a dataset for nothing.
                patch(
                    "hackagent.orchestrator.campaign.resolve_campaign",
                    return_value=_resolution(builder._snapshot),
                ),
                patch(
                    "hackagent.orchestrator.campaign.run_campaign",
                    side_effect=fake_run,
                ),
                patch.object(app, "call_from_thread"),
            ):
                builder._execute()

        assert captured["settings"] is cli_config.settings

    @pytest.mark.asyncio
    async def test_config_view_says_runs_are_recorded_here(self, cli_config):
        """A configured account is for reading, and must not look like more."""
        app = HackAgentTUI(cli_config, initial_tab="config")
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            rendered = str(app.query_one("#mode-indicator", Static).render())

        assert "Local" in rendered and "SQLite" in rendered
        assert cli_config.base_url in rendered
        assert "storage.backend: remote" in rendered


class TestWelcome:
    @pytest.mark.asyncio
    async def test_opens_on_the_welcome_screen_with_the_logo(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            # Every line of it, and nothing cut: _logo_rows checks the content.
            assert len(_logo_rows(app)) == len(LOGO_LINES)

    @pytest.mark.asyncio
    async def test_the_logo_is_centred_without_shearing_its_letters(self, cli_config):
        """Centring each line on its own would slide the letters out of line."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            rows = _logo_rows(app)

        indents = {len(row) - len(row.lstrip()) for row in rows}
        assert len(indents) == 1, f"logo rows start at different columns: {indents}"
        # Centred as a block: the margin on the left matches the one on the right.
        left = indents.pop()
        right = WIDE[0] - max(len(row.rstrip()) for row in rows)
        assert abs(left - right) <= 1

    # Narrower than the banner, and narrower than the card wants to be.
    @pytest.mark.parametrize("width", [70, 50])
    @pytest.mark.asyncio
    async def test_a_narrow_terminal_still_gets_the_banner(self, cli_config, width):
        """There is one banner, so a small window gets less of it, not a word."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=(width, 24)) as pilot:
            await pilot.pause()
            rows = _rendered(app)

        # As many rows as the banner has, each one the start of its own line.
        drawn = [
            row
            for row in rows
            if any(row.strip() and line.startswith(row.strip()) for line in LOGO_LINES)
        ]
        assert len(drawn) == len(LOGO_LINES)
        assert max(len(row.rstrip()) for row in rows) <= width
        # The card shrinks with the terminal, so the tagline wraps whole
        # rather than being cut off at the edge.
        assert TAGLINE.split()[-1] in " ".join(rows)

    @pytest.mark.asyncio
    async def test_every_choice_lands_somewhere_different(self, cli_config):
        """The screen once had four buttons into the same editor. Not again."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            buttons = list(app.screen.query(Button))
            destinations = {button.id for button in buttons}

            # One button per destination: no two land in the same place.
            assert len(destinations) == len(buttons)
            assert destinations == {"build", "example", "open", "results"}

    @pytest.mark.asyncio
    async def test_starting_lands_in_a_runnable_builder(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert not isinstance(app.screen, WelcomeScreen)
            builder = app.query_one(CampaignBuilder)
            assert builder.query_one("#run", Button).disabled is False

    @pytest.mark.asyncio
    async def test_a_campaign_handed_to_the_app_skips_the_welcome(self, cli_config):
        given = yaml.safe_dump(
            {
                "version": 1,
                "campaign": {"name": "given"},
                "dataset": {"source": {"type": "inline", "goals": ["g"]}},
                "target": {
                    "name": "m",
                    "connection": {"provider": "ollama", "type": "OLLAMA"},
                },
                "attacks": [{"name": "baseline"}],
            }
        )
        app = HackAgentTUI(cli_config, initial_data={"campaign_yaml": given})
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, WelcomeScreen)
            assert app.query_one(CampaignBuilder).draft.data["campaign"]["name"] == (
                "given"
            )


class TestOneScreen:
    @pytest.mark.asyncio
    async def test_help_opens_and_closes(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            await pilot.press("escape")  # take the default starting point
            await pilot.pause()
            await pilot.press("f1")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.parametrize("view", ["results", "agents", "config"])
    @pytest.mark.asyncio
    async def test_the_other_views_still_open_on_their_own(self, cli_config, view):
        """`hackagent results` and `hackagent agent` open these directly."""
        app = HackAgentTUI(cli_config, initial_tab=view)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, WelcomeScreen)
            assert len(app.query(CampaignBuilder)) == 0


class TestRemovingAttacks:
    """Taking an attack out needed the mouse; Delete now does it."""

    CAMPAIGN = {
        "version": 1,
        "campaign": {"name": "two attacks"},
        "dataset": {"source": {"type": "inline", "goals": ["g"]}},
        "target": {
            "name": "m",
            "connection": {"provider": "ollama", "type": "OLLAMA"},
        },
        "attacks": [{"name": "baseline"}, {"name": "flipattack"}],
    }

    async def _builder(self, app, pilot) -> CampaignBuilder:
        await pilot.pause()
        return app.query_one(CampaignBuilder)

    async def _walk_to(self, builder, pilot, root) -> bool:
        for _ in range(40):
            if builder._node is not None and builder._node.root == root:
                return True
            await pilot.press("down")
            await pilot.pause()
        return False

    @pytest.mark.asyncio
    async def test_delete_removes_the_selected_attack(self, cli_config):
        app = HackAgentTUI(
            cli_config, initial_data={"campaign_yaml": yaml.safe_dump(self.CAMPAIGN)}
        )
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._builder(app, pilot)
            assert await self._walk_to(builder, pilot, ("attacks", 1))

            await pilot.press("delete")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)

            await pilot.press("tab")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

            names = [attack["name"] for attack in builder.draft.data["attacks"]]
            assert names == ["baseline"]

    @pytest.mark.asyncio
    async def test_cancelling_keeps_the_attack(self, cli_config):
        app = HackAgentTUI(
            cli_config, initial_data={"campaign_yaml": yaml.safe_dump(self.CAMPAIGN)}
        )
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._builder(app, pilot)
            assert await self._walk_to(builder, pilot, ("attacks", 1))

            await pilot.press("delete")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            names = [attack["name"] for attack in builder.draft.data["attacks"]]
            assert names == ["baseline", "flipattack"]

    @pytest.mark.asyncio
    async def test_delete_does_nothing_on_a_part_that_is_not_removable(
        self, cli_config
    ):
        app = HackAgentTUI(
            cli_config, initial_data={"campaign_yaml": yaml.safe_dump(self.CAMPAIGN)}
        )
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._builder(app, pilot)
            assert builder._node.root == ("campaign",)  # not an attack

            await pilot.press("delete")
            await pilot.pause()
            assert not isinstance(app.screen, ConfirmScreen)
            assert len(builder.draft.data["attacks"]) == 2


class TestWelcomeDestinations:
    """Each button lands somewhere the others do not."""

    async def _choose(self, app, pilot, destination):
        await pilot.pause()
        assert isinstance(app.screen, WelcomeScreen)
        app.screen.dismiss(destination)
        await pilot.pause()

    @pytest.mark.asyncio
    async def test_it_offers_four_ways_in(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            labels = {str(button.label) for button in app.screen.query(Button)}

        assert labels == {
            "Build your own campaign",
            "Start from an example",
            "Open a campaign file",
            "Show results",
        }

    @pytest.mark.asyncio
    async def test_build_lands_in_a_runnable_builder(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await self._choose(app, pilot, "build")

            assert not isinstance(app.screen, WelcomeScreen)
            assert app.query_one(CampaignBuilder).draft.validate()[0] is not None

    @pytest.mark.asyncio
    async def test_an_example_opens_in_the_builder_rather_than_running(
        self, cli_config
    ):
        """You read it and can change the model before anything is attacked."""
        from hackagent import examples as examples_catalog

        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await self._choose(app, pilot, "example")
            assert isinstance(app.screen, ExampleScreen)

            chosen = examples_catalog.campaign_files()["ollama/h4rm3l-demo"]
            app.screen.dismiss(chosen)
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            spec = builder.draft.validate()[0]

        assert spec is not None and spec.campaign.name == "Ollama h4rm3l demo"
        # Opened as a file, so its explanatory comments survive.
        assert builder._has_comments

    @pytest.mark.asyncio
    async def test_looking_at_an_attack_does_not_change_it(self, cli_config):
        """h4rm3l's ``syntax_version`` is ``Literal[1, 2]``: an int, not "2".

        Showing the attack's form used to write the choice back as text, so
        the example stopped validating and could not be run.
        """
        from hackagent import examples as examples_catalog

        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await self._choose(app, pilot, "example")
            app.screen.dismiss(examples_catalog.campaign_files()["ollama/h4rm3l-demo"])
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            for _ in range(15):
                if builder._node is not None and builder._node.root == ("attacks", 0):
                    break
                await pilot.press("down")
                await pilot.pause()
            assert builder._node.root == ("attacks", 0)
            await pilot.pause()

            spec, issues = builder.draft.validate()

        assert issues == ()
        assert spec is not None and spec.attacks[0].parameters["syntax_version"] == 2

    @pytest.mark.asyncio
    async def test_open_asks_for_a_path_without_offering_to_discard(self, cli_config):
        """Arriving from the welcome there is no draft to lose."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await self._choose(app, pilot, "open")

            assert isinstance(app.screen, PathScreen)

    @pytest.mark.asyncio
    async def test_results_opens_and_comes_back_to_the_welcome(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await self._choose(app, pilot, "results")
            assert isinstance(app.screen, ResultsScreen)

            app.screen.dismiss(None)
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)


class TestGoingBack:
    @pytest.mark.asyncio
    async def test_a_fresh_template_is_not_a_modification_of_itself(self, cli_config):
        """The status bar claimed "modified" the moment the builder opened."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            app.screen.dismiss("build")
            await pilot.pause()

            assert not app.query_one(CampaignBuilder)._is_dirty()

    @pytest.mark.asyncio
    async def test_f2_goes_back_to_the_welcome(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            app.screen.dismiss("build")
            await pilot.pause()
            await pilot.press("f2")
            await pilot.pause()

            assert isinstance(app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_f2_asks_first_when_there_is_work_to_lose(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            app.screen.dismiss("build")
            await pilot.pause()
            builder = app.query_one(CampaignBuilder)
            builder.draft.set(("campaign", "name"), "edited")
            builder._validate()
            await pilot.press("f2")
            await pilot.pause()

            assert isinstance(app.screen, ConfirmScreen)


class TestResultsReadAsSentences:
    """The list answers "did anything get through", in words."""

    def test_time_is_said_the_way_people_say_it(self):
        from datetime import datetime, timedelta, timezone

        from hackagent.interfaces.tui.views.results.tab import _ago

        now = datetime.now(timezone.utc)
        assert _ago(now - timedelta(seconds=10)) == "just now"
        assert _ago(now - timedelta(minutes=9)) == "9m ago"
        assert _ago(now - timedelta(hours=3)) == "3h ago"
        assert _ago(now - timedelta(days=2)) == "2d ago"
        assert _ago(None) == "—"

    def test_an_outcome_is_a_sentence_not_a_ratio(self):
        from hackagent.interfaces.tui.views.results.tab import _outcome

        assert "5 of 5 goals jailbroken" in _outcome(5, 5, "COMPLETED", 5)
        assert "0 of 10 goals jailbroken" in _outcome(0, 10, "COMPLETED", 10)

    def test_a_campaign_that_never_ran_says_so(self):
        """It used to show 0/0, which reads as a clean result."""
        from hackagent.interfaces.tui.views.results.tab import _outcome

        assert "did not finish" in _outcome(0, 0, "FAILED", 0)
        assert "nothing recorded" in _outcome(0, 0, "COMPLETED", 0)


class TestRunView:
    """Running opens a screen of its own; the outline is only the campaign."""

    async def _builder(self, app, pilot):
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        return app.query_one(CampaignBuilder)

    @pytest.mark.asyncio
    async def test_the_outline_lists_only_campaign_sections(self, cli_config):
        """No "Run" or "Logs" entry: running is not a part of the campaign."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._builder(app, pilot)
            titles = {
                node.data.title
                for node in builder.query_one(Tree).root.children
                if node.data is not None
            }

        assert "Logs" not in titles and "Run" not in titles
        assert "Dataset" in titles and "Execution" in titles

    @pytest.mark.asyncio
    async def test_watching_a_run_takes_the_whole_screen(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._builder(app, pilot)
            builder._log("[cyan]baseline[/]")
            builder._watch_run()
            await pilot.pause()

            assert isinstance(app.screen, RunScreen)
            # The log is as wide as the terminal, not as wide as a pane.
            assert app.screen.query_one("#run-log").size.width > WIDE[0] * 0.8

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, RunScreen)
            assert app.query_one(CampaignBuilder) is builder

    @pytest.mark.asyncio
    async def test_lines_written_while_away_are_there_on_return(self, cli_config):
        """Leaving the run view does not stop the run, so nothing may be lost."""
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._builder(app, pilot)
            builder._log("before watching")
            builder._watch_run()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            builder._log("while away")
            builder._set_progress(60)
            builder._watch_run()
            await pilot.pause()
            rows = _rendered(app)

        assert any("before watching" in row for row in rows)
        assert any("while away" in row for row in rows)


class TestKeysThatMustNotBeShadowed:
    """A key an editor already owns can never reach the builder."""

    @pytest.mark.asyncio
    async def test_edit_yaml_uses_a_key_no_text_field_claims(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            await pilot.pause()
            await pilot.press("enter")  # into the builder
            await pilot.pause()
            # Focus a text field directly: this is about what a focused
            # editor swallows, not about where Tab happens to land. On a slow
            # runner the builder can still be rendering its form, replacing
            # the fields, so look the field up afresh until focusing it holds.
            for _ in range(20):
                fields = [field for field in app.query(Input) if field.focusable]
                if fields:
                    fields[0].focus()
                await pilot.pause(0.05)
                if isinstance(app.focused, Input):
                    break

            assert isinstance(app.focused, Input), app.focused
            claimed = set(app.focused._bindings.key_to_bindings)
            builder = app.query_one(CampaignBuilder)
            advertised = {
                binding.key
                for binding in builder.BINDINGS
                if getattr(binding, "show", True)
            }
            # Whatever the footer promises must survive a focused text field.
            assert advertised & claimed == set(), (
                f"shadowed while editing: {sorted(advertised & claimed)}"
            )


class TestPanelsAreBoxed:
    """Nested models are boxes inside one panel, not entries in the outline."""

    async def _panel(self, app, pilot, root) -> CampaignBuilder:
        await pilot.pause()
        await pilot.press("enter")  # leave the welcome screen
        await pilot.pause()
        builder = app.query_one(CampaignBuilder)
        for _ in range(15):
            if builder._node is not None and builder._node.root == root:
                return builder
            await pilot.press("down")
            await pilot.pause()
        raise AssertionError(f"never reached {root}")

    @staticmethod
    def _boxes(builder) -> dict[str, list[str]]:
        """Each box and the rows it owns directly, nested boxes included."""
        from hackagent.interfaces.tui.views.campaign.form import FieldRow

        return {
            str(box.query(".box-title").first().render()): [
                row.field.label_in(row.box)
                for row in box.query(FieldRow)
                if row.parent is box
            ]
            for box in builder.query(".box")
        }

    @pytest.mark.asyncio
    async def test_the_dataset_panel_boxes_source_selection_and_classifier(
        self, cli_config
    ):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=(140, 45)) as pilot:
            builder = await self._panel(app, pilot, ("dataset",))
            boxes = self._boxes(builder)

            # Filters is a box inside Selection, as the schema nests it.
            assert list(boxes) == ["Source", "Selection", "Filters", "Classifier"]
            assert boxes["Source"] == ["type", "name"]
            assert "limit" in boxes["Selection"]
            assert boxes["Filters"] == ["categories"]

    @pytest.mark.asyncio
    async def test_a_model_panel_boxes_connection_and_generation(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=(140, 45)) as pilot:
            builder = await self._panel(app, pilot, ("target",))
            boxes = self._boxes(builder)

            assert list(boxes) == ["Connection", "Generation"]
            assert "endpoint" in boxes["Connection"]
            assert "temperature" in boxes["Generation"]

    @pytest.mark.asyncio
    async def test_an_optional_box_switches_on_in_place(self, cli_config):
        """Turning on a classifier must not send you to another screen."""
        from textual.widgets import Switch

        app = HackAgentTUI(cli_config)
        async with app.run_test(size=(140, 45)) as pilot:
            builder = await self._panel(app, pilot, ("dataset",))
            assert builder.draft.data["dataset"].get("classifier") is None

            builder.query(".enable-group").first(Switch).value = True
            for _ in range(4):
                await pilot.pause()

            assert builder.draft.data["dataset"]["classifier"] == {}
            assert builder._node.root == ("dataset",)  # still the same panel
            assert self._boxes(builder)["Classifier"]


@pytest.mark.asyncio
async def test_a_field_row_being_torn_down_can_still_refresh(cli_config):
    """A row's pending mount can run after its children are gone.

    When the app closes right after opening the builder, Textual can remove
    a row's children before the row handles its own mount, which refreshes
    the state line. Looking that line up then failed with NoMatches.
    """
    from hackagent.interfaces.tui.views.campaign.form import FieldRow

    app = HackAgentTUI(cli_config)
    async with app.run_test(size=WIDE) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        row = app.screen.query(FieldRow).first()
        await row.remove_children()
        row.refresh_state()  # no raise
