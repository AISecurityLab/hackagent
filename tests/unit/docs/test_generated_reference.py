# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The generated reference pages must match the code they are generated from.

The docs site's reference section is written by
``docs/scripts/generate_reference.py``. If someone changes a field, an attack
parameter or a CLI option without regenerating, these tests fail and say so,
which is the whole point: generated docs cannot drift.

They also check the YAML examples in those pages, so a snippet a reader copies
is one the campaign format actually accepts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "docs" / "scripts"
REFERENCE = ROOT / "docs" / "docs" / "reference"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _generated() -> dict[Path, str]:
    import generate_reference

    return generate_reference.generate()


@pytest.fixture(scope="module")
def generated() -> dict[Path, str]:
    return _generated()


def test_the_committed_pages_match_the_code(generated):
    stale = sorted(
        str(path.relative_to(ROOT))
        for path, content in generated.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    )
    assert stale == [], (
        "These files no longer match the code. Run:\n"
        "  uv run python docs/scripts/generate_reference.py\n"
        + "\n".join(f"  - {name}" for name in stale)
    )


def test_no_stale_pages_are_left_behind(generated):
    on_disk = {path for path in REFERENCE.rglob("*.md")}
    assert on_disk - set(generated) == set()


def test_every_section_of_the_campaign_format_has_a_page(generated):
    from hackagent.orchestrator.campaign.spec import CampaignSpec

    # A section is documented either as `<name>.md` or as `<name>/index.md`.
    pages = {path.stem for path in generated if path.suffix == ".md"}
    pages |= {
        path.parent.name for path in generated if path.name == "index.md"
    }
    missing = [
        name
        for name in CampaignSpec.model_fields
        if name not in pages and name != "version"
    ]
    assert missing == [], f"no reference page documents: {missing}"


def test_every_attack_has_a_page(generated):
    from hackagent.attacks.techniques.registry import ATTACKS

    pages = {path.stem for path in generated if path.parent.name == "attacks"}
    assert set(ATTACKS) - pages == set()


def _yaml_blocks(text: str) -> list[str]:
    return re.findall(r"```yaml\n(.*?)```", text, flags=re.S)


def _example_pages() -> list[tuple[str, str]]:
    return [
        (str(path.relative_to(REFERENCE)), path.read_text(encoding="utf-8"))
        for path in sorted(REFERENCE.rglob("*.md"))
    ]


@pytest.mark.parametrize(("name", "text"), _example_pages())
def test_yaml_examples_parse_and_fit_the_format(name, text):
    """Every snippet is valid YAML and uses only fields the format defines."""
    from hackagent.orchestrator.campaign.spec import CampaignSpec

    for block in _yaml_blocks(text):
        if block.lstrip().startswith("#"):  # an editor directive, not a campaign
            continue
        data = yaml.safe_load(block)
        assert isinstance(data, dict), f"{name}: snippet is not a mapping"
        unknown = set(data) - set(CampaignSpec.model_fields)
        assert unknown == set(), f"{name}: unknown section(s) {sorted(unknown)}"


def test_the_complete_example_is_a_valid_campaign():
    """The campaign on the landing page must resolve, not merely parse."""
    from hackagent.orchestrator.campaign.spec import CampaignSpec

    blocks = _yaml_blocks((REFERENCE / "index.md").read_text(encoding="utf-8"))
    full = [block for block in blocks if "version:" in block and "attacks:" in block]
    assert full, "the landing page should show one complete campaign"
    for block in full:
        CampaignSpec.model_validate(yaml.safe_load(block))


def test_the_published_schema_matches_the_spec(generated):
    import json

    from hackagent.orchestrator.campaign.spec import campaign_json_schema

    path = ROOT / "docs" / "static" / "schema" / "campaign.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == campaign_json_schema()
