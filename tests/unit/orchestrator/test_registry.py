# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Registry ids are the catalog AttackIds, resolved lazily."""

from pathlib import Path

import pytest

import hackagent.attacks.techniques as techniques
from hackagent.catalog.attacks import ATTACK_CATALOG
from hackagent.catalog.taxonomy import ATTACK_IDS, AttackTag, get_attack_taxonomy
from hackagent.orchestrator.setup.registry import (
    ATTACK_REGISTRY,
    CONFIG_REGISTRY,
    load_attack,
    load_config_model,
)

_CATEGORY_FOLDERS = {"static", "adaptive", "multi_turn", "indirect"}


def _folder(attack_id: str) -> str:
    """The folder a technique belongs in: the docs grouping.

    The ``indirect`` tag wins; otherwise the primary category decides.
    """
    taxonomy = get_attack_taxonomy(attack_id)
    if AttackTag.INDIRECT in taxonomy.tags:
        return "indirect"
    return taxonomy.category.value


def test_registry_ids_equal_catalog_ids():
    """Registry keys are the catalog AttackIds.

    ``ATTACK_CATALOG`` is the CLI label table and is a subset (it still
    omits ``rag``). The id set the registry must match is ``ATTACK_IDS``.
    """
    assert set(ATTACK_REGISTRY) == set(ATTACK_IDS)
    assert set(ATTACK_CATALOG) <= set(ATTACK_REGISTRY)


def test_load_attack_imports_the_registered_class():
    cls = load_attack("baseline")
    assert cls.__name__ == "BaselineAttack"
    assert f"{cls.__module__}:{cls.__name__}" == ATTACK_REGISTRY["baseline"]


def test_unknown_attack_id_is_rejected():
    with pytest.raises(ValueError, match="Unsupported attack_type: missing"):
        load_attack("missing")


def test_config_model_is_optional_and_loaded_from_the_registry():
    assert load_config_model("baseline") is None
    assert load_config_model("advprefix") is None
    model = load_config_model("pair")
    assert model is not None
    assert model.__name__ == "PairConfig"


@pytest.mark.parametrize(
    "attack_id, spec",
    [*ATTACK_REGISTRY.items(), *CONFIG_REGISTRY.items()],
)
def test_technique_lives_in_its_category_folder(attack_id, spec):
    module = spec.partition(":")[0]
    folder = module.split(".")[3]
    assert module.startswith("hackagent.attacks.techniques.")
    assert folder == _folder(attack_id), (
        f"{attack_id} is in techniques/{folder}/, but its taxonomy puts it in "
        f"techniques/{_folder(attack_id)}/"
    )


def test_every_technique_package_is_in_a_category_folder():
    root = Path(techniques.__file__).parent
    top_level = {
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "__init__.py").exists()
    }
    assert top_level == _CATEGORY_FOLDERS
