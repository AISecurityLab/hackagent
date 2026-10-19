# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The OmniSafeBench taxonomy vocabulary."""

from __future__ import annotations

import pytest

from hackagent.datasets import taxonomy

EXPLOIT = {
    "category": "E. Cybersecurity Threats",
    "subcategory": "E2. Exploit Development",
}


@pytest.mark.parametrize(
    "value",
    [
        "E2",
        "e2",
        "**E2. Exploit Development**",
        "E2 - Exploit Development",
        "exploit development",
    ],
)
def test_a_subcategory_resolves_from_its_code_label_or_display_form(value):
    assert taxonomy.resolve_subcategory(value) == "E2"


@pytest.mark.parametrize(
    "value", ["E", "E. Cybersecurity Threats", "cybersecurity threats"]
)
def test_a_category_resolves_from_its_code_label_or_display_form(value):
    assert taxonomy.resolve_category(value) == "E"


@pytest.mark.parametrize("value", ["Q9", "E. Cybersecurity Threats", ""])
def test_anything_else_is_not_a_subcategory(value):
    with pytest.raises(ValueError):
        taxonomy.resolve_subcategory(value)


def test_labels_take_the_category_from_the_subcategory():
    assert taxonomy.labels("E2") == EXPLOIT
    assert taxonomy.category_of("E2") == "E"


def test_every_subcategory_appears_in_the_description():
    described = taxonomy.describe()
    for code, label in taxonomy.subcategories().items():
        assert f"- {code}. {label}" in described
    assert list(taxonomy.subcategories("C")) == [f"C{n}" for n in range(1, 8)]


def test_omnisafebench_files_intents_under_every_subcategory_with_its_label():
    from hackagent.datasets.intents import _omnisafebench, intents_of

    filed = {
        code: sub["label"]
        for category in _omnisafebench().values()
        for code, sub in category["subcategories"].items()
    }
    assert filed == taxonomy.subcategories()
    assert all(intents_of(code) for code in filed)
