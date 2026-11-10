# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every registered attack has a hand-written page, and only those do.

The attack pages under ``docs/docs/attacks/<type>/`` are written by hand,
around a generated partial that carries the facts from the code. The
registry is the source of truth: the type folder comes from the attack's
module path (``multi_turn`` -> ``multi-turn``), so an attack that is added,
renamed, removed or moved to another type fails here until its page follows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hackagent.attacks.techniques.registry import ATTACKS, attack_family

ATTACKS_DIR = Path(__file__).resolve().parents[3] / "docs" / "docs" / "attacks"

#: The ``##`` sections of an attack page, in order. ``docs/README.md`` says
#: what goes in each.
SECTIONS = [
    "At a glance",
    "Research",
    "How it works",
    "When to use it",
    "Cost",
    "Configuration",
    "Reading the results",
    "Limitations",
    "Related",
]


def _folder(name: str) -> str:
    return attack_family(name).replace("_", "-")


def _page(name: str) -> Path:
    return ATTACKS_DIR / _folder(name) / f"{name}.mdx"


def _type_folders() -> set[str]:
    return {_folder(name) for name in ATTACKS}


def _renders(text: str, partial: str) -> bool:
    """Whether ``text`` imports ``partial`` and renders it as a component."""
    match = re.search(
        rf"^import (\w+) from '\./{re.escape(partial)}';$", text, flags=re.M
    )
    return bool(match) and re.search(rf"<{match.group(1)}\s*/>", text) is not None


def _headings(text: str) -> list[str]:
    """The ``##`` headings of a page, outside code blocks."""
    text = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    return re.findall(r"^## (.+?)\s*$", text, flags=re.M)


def test_every_attack_has_a_page():
    missing = sorted(
        str(_page(name).relative_to(ATTACKS_DIR))
        for name in ATTACKS
        if not _page(name).is_file()
    )
    assert missing == [], f"registered attacks with no page: {missing}"


def test_no_page_outlives_its_attack():
    expected = {_page(name) for name in ATTACKS}
    found = {
        path
        for path in ATTACKS_DIR.glob("*/*.mdx")
        if path.name != "index.mdx" and not path.name.startswith("_")
    }
    extra = sorted(str(path.relative_to(ATTACKS_DIR)) for path in found - expected)
    assert extra == [], (
        f"pages with no registered attack, or in the wrong type folder: {extra}"
    )


@pytest.mark.parametrize("folder", sorted(_type_folders()))
def test_every_type_folder_has_an_index_and_a_category(folder):
    assert (ATTACKS_DIR / folder / "index.mdx").is_file()
    assert (ATTACKS_DIR / folder / "_category_.json").is_file()


def test_no_type_folder_outlives_its_type():
    folders = {path.name for path in ATTACKS_DIR.iterdir() if path.is_dir()}
    assert folders - _type_folders() == set()


@pytest.mark.parametrize("folder", sorted(_type_folders()))
def test_every_type_index_renders_its_list(folder):
    text = (ATTACKS_DIR / folder / "index.mdx").read_text(encoding="utf-8")
    assert _renders(text, "_list.generated.mdx")


def test_the_overview_renders_the_catalog():
    text = (ATTACKS_DIR / "index.mdx").read_text(encoding="utf-8")
    assert _renders(text, "_catalog.generated.mdx")


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_every_page_renders_its_generated_partial(name):
    page = _page(name)
    if not page.is_file():
        pytest.skip("no page; test_every_attack_has_a_page reports it")
    assert _renders(page.read_text(encoding="utf-8"), f"_{name}.generated.mdx"), (
        f"{page.name} must `import X from './_{name}.generated.mdx';` and "
        "render `<X />` under `## Configuration`"
    )


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_every_page_follows_the_template(name):
    page = _page(name)
    if not page.is_file():
        pytest.skip("no page; test_every_attack_has_a_page reports it")
    text = page.read_text(encoding="utf-8")
    assert _headings(text) == SECTIONS, (
        f"{page.name}: the ## sections must be exactly {SECTIONS}"
    )
    configuration = text.split("## Configuration", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"<\w+\s*/>", configuration), (
        f"{page.name}: render the generated partial under ## Configuration"
    )
