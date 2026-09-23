# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Registry ids are the catalog AttackIds, resolved lazily."""

import pytest

from hackagent.catalog.attacks import ATTACK_CATALOG
from hackagent.catalog.taxonomy import ATTACK_IDS
from hackagent.orchestrator.registry import (
    ATTACK_REGISTRY,
    load_attack,
    load_config_model,
)


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
