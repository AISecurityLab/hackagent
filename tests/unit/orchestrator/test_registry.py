# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Registry ids are the catalog AttackIds, resolved lazily."""

from pathlib import Path


import hackagent.attacks.techniques as techniques
from hackagent.catalog.attacks import ATTACK_CATALOG
from hackagent.catalog.taxonomy import ATTACK_IDS, AttackTag, get_attack_taxonomy

_CATEGORY_FOLDERS = {"static", "adaptive", "multi_turn", "indirect"}


def _folder(attack_id: str) -> str:
    """The folder a technique belongs in: the docs grouping.

    The ``indirect`` tag wins; otherwise the primary category decides.
    """
    taxonomy = get_attack_taxonomy(attack_id)
    if AttackTag.INDIRECT in taxonomy.tags:
        return "indirect"
    return taxonomy.category.value


def test_campaign_registry_ids_equal_catalog_ids():
    """Every attack is a campaign attack now, so the campaign registry is the
    one that must cover the catalog. The legacy ATTACK_REGISTRY is empty."""
    from hackagent.attacks.techniques.registry import ATTACKS

    assert set(ATTACKS) == set(ATTACK_IDS)
    assert set(ATTACK_CATALOG) <= set(ATTACKS)


def test_the_campaign_registry_imports_a_technique_class():
    from hackagent.attacks.techniques.registry import get_attack_class

    cls = get_attack_class("baseline")
    assert cls.__name__ == "BaselineAttack"


def test_every_technique_package_is_in_a_category_folder():
    root = Path(techniques.__file__).parent
    top_level = {
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "__init__.py").exists()
    }
    assert top_level == _CATEGORY_FOLDERS
