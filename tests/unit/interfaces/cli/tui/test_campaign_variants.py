# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The dataset source is a tagged union, and the form follows the tag.

`source.type` decides which other fields exist. The form must show the tag and
only that variant's fields, and changing the tag must take the old variant's
fields with it — otherwise the document keeps values that no longer mean
anything and stops validating.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yaml
from textual.widgets import Select

from hackagent.datasets.config import DatasetSpec, InlineSource, PresetSource
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.app import HackAgentTUI
from hackagent.interfaces.tui.views.campaign import CampaignBuilder
from hackagent.interfaces.tui.views.campaign.draft import CampaignDraft
from hackagent.interfaces.tui.views.campaign.form import FieldRow
from hackagent.interfaces.tui.views.campaign.outline import build_outline

WIDE = (140, 45)


@pytest.fixture
def cli_config():
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-key"
    config.base_url = "https://api.test.hackagent.dev"
    return config


def _campaign(source: dict) -> dict:
    return {
        "version": 1,
        "campaign": {"name": "x"},
        "dataset": {"source": source},
        "target": {
            "name": "m",
            "connection": {"provider": "ollama", "type": "OLLAMA"},
        },
        "attacks": [{"name": "baseline"}],
    }


def _source_fields(source: dict) -> list[str]:
    """The rows of the Source box, inside the Dataset panel."""
    draft = CampaignDraft.from_yaml(yaml.safe_dump(_campaign(source)))
    found = []

    def walk(items):
        for outline in items:
            if outline.node.root == ("dataset",):
                found.append(outline.node)
            walk(outline.children)

    walk(build_outline(draft))
    assert found, "the dataset should have a panel"
    box = next(group for group in found[0].groups(draft) if group.title == "Source")
    return [field.label for field in box.fields]


class TestTheFormFollowsTheTag:
    def test_a_preset_source_offers_only_a_preset(self):
        assert _source_fields({"type": "preset", "name": "harmbench"}) == [
            "source.type",
            "source.name",
        ]

    def test_an_inline_source_offers_only_goals(self):
        assert _source_fields({"type": "inline", "goals": ["g"]}) == [
            "source.type",
            "source.goals",
        ]

    def test_a_provider_source_offers_the_provider_fields(self):
        fields = _source_fields({"type": "provider", "provider": "huggingface"})
        assert "source.provider" in fields
        assert "source.path" in fields
        assert "source.goals" not in fields
        # A provider source has a `name` of its own (the dataset configuration),
        # which is a different thing from a preset's name.
        assert "source.split" in fields


class TestTheModelRejectsMixtures:
    def test_a_preset_on_an_inline_source_is_rejected(self):
        with pytest.raises(ValueError, match="preset"):
            DatasetSpec.model_validate(
                {"source": {"type": "inline", "goals": ["g"], "preset": "harmbench"}}
            )

    def test_each_variant_requires_its_own_field(self):
        with pytest.raises(ValueError, match="goals"):
            DatasetSpec.model_validate({"source": {"type": "inline"}})
        with pytest.raises(ValueError, match="preset"):
            DatasetSpec.model_validate({"source": {"type": "preset"}})

    def test_the_older_top_level_preset_still_loads(self):
        """Campaign files written before the split keep working."""
        spec = DatasetSpec.model_validate({"preset": "harmbench"})
        assert isinstance(spec.source, PresetSource)
        assert spec.preset == "harmbench"

    def test_an_inline_source_reports_no_preset(self):
        spec = DatasetSpec.model_validate(
            {"source": {"type": "inline", "goals": ["g"]}}
        )
        assert isinstance(spec.source, InlineSource)
        assert spec.preset is None


class TestChangingTheTagInTheForm:
    async def _source_panel(self, app, pilot) -> CampaignBuilder:
        await pilot.pause()
        builder = app.query_one(CampaignBuilder)
        for _ in range(20):
            if builder._node is not None and builder._node.root == ("dataset",):
                return builder
            await pilot.press("down")
            await pilot.pause()
        raise AssertionError("never reached the dataset panel")

    @staticmethod
    def _source_rows(app) -> list[str]:
        return [
            row.field.label
            for row in app.query(FieldRow)
            if row.field.label.startswith("source")
        ]

    @pytest.mark.asyncio
    async def test_switching_swaps_the_fields_and_drops_the_old_ones(self, cli_config):
        document = _campaign({"type": "preset", "name": "harmbench"})
        app = HackAgentTUI(
            cli_config, initial_data={"campaign_yaml": yaml.safe_dump(document)}
        )
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._source_panel(app, pilot)
            assert self._source_rows(app) == ["source.type", "source.name"]

            tag = next(
                row for row in app.query(FieldRow) if row.field.label == "source.type"
            )
            tag.query_one(".value", Select).value = "inline"
            for _ in range(4):
                await pilot.pause()

            assert self._source_rows(app) == ["source.type", "source.goals"]
            # The preset meant nothing to an inline source, so it is gone.
            assert builder.draft.data["dataset"]["source"] == {"type": "inline"}

    @pytest.mark.asyncio
    async def test_the_tag_is_marked_so_the_panel_knows_to_rebuild(self, cli_config):
        document = _campaign({"type": "preset", "name": "harmbench"})
        app = HackAgentTUI(
            cli_config, initial_data={"campaign_yaml": yaml.safe_dump(document)}
        )
        async with app.run_test(size=WIDE) as pilot:
            await self._source_panel(app, pilot)
            rows = {row.field.label: row.field for row in app.query(FieldRow)}
            assert rows["source.type"].discriminator is True
            assert rows["source.name"].discriminator is False


class TestTheTagSurvivesEditing:
    """The tag is structural: without it the document cannot be read at all.

    It used to be pruned like any other value that matched its default, which
    left a source with no `type` — and validation could then only say it was
    "unable to extract tag using discriminator 'type'".
    """

    async def _dataset_panel(self, app, pilot) -> CampaignBuilder:
        await pilot.pause()
        await pilot.press("enter")  # leave the welcome screen
        await pilot.pause()
        builder = app.query_one(CampaignBuilder)
        for _ in range(20):
            if builder._node is not None and builder._node.root == ("dataset",):
                return builder
            await pilot.press("down")
            await pilot.pause()
        raise AssertionError("never reached the dataset panel")

    @staticmethod
    def _tag(builder) -> FieldRow:
        return next(row for row in builder.query(FieldRow) if row.field.discriminator)

    @pytest.mark.asyncio
    async def test_choosing_the_default_variant_keeps_the_tag(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._dataset_panel(app, pilot)

            for wanted in ("inline", "preset", "provider", "preset"):
                self._tag(builder).query_one(".value", Select).value = wanted
                for _ in range(4):
                    await pilot.pause()
                source = builder.draft.data["dataset"]["source"]
                assert source["type"] == wanted, f"tag lost switching to {wanted}"

    @pytest.mark.asyncio
    async def test_a_preset_can_be_chosen_after_switching_back(self, cli_config):
        app = HackAgentTUI(cli_config)
        async with app.run_test(size=WIDE) as pilot:
            builder = await self._dataset_panel(app, pilot)
            for wanted in ("inline", "preset"):
                self._tag(builder).query_one(".value", Select).value = wanted
                for _ in range(4):
                    await pilot.pause()

            row = next(
                r for r in builder.query(FieldRow) if r.field.label_in(r.box) == "name"
            )
            row.query_one(".value", Select).value = "advbench"
            for _ in range(3):
                await pilot.pause()

            assert builder.draft.data["dataset"]["source"] == {
                "type": "preset",
                "name": "advbench",
            }
            # Validation is debounced in the UI; ask for it now.
            builder._validate()
            assert builder._issues == ()
