# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The campaign format documents itself, and its role contract is honest.

The reference documentation is generated from the code: every field's
description is its attribute docstring. These tests keep that true — a new
field without a docstring, or a ``REQUIRED_ROLES`` declaration that no longer
matches what an attack's constructor enforces, fails here instead of quietly
producing wrong docs.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from hackagent.attacks.techniques.registry import ATTACKS, get_attack_class
from hackagent.orchestrator.campaign.spec import CampaignSpec


def _models(root: type[BaseModel]) -> set[type[BaseModel]]:
    """``root`` and every model nested anywhere in its fields."""
    seen: set[type[BaseModel]] = set()
    stack = [root]
    while stack:
        model = stack.pop()
        if model in seen:
            continue
        seen.add(model)
        for field in model.model_fields.values():
            stack.extend(_nested(field.annotation))
    return seen


def _nested(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [
        found
        for arg in getattr(annotation, "__args__", ()) or ()
        for found in _nested(arg)
    ]


def test_every_campaign_field_is_documented():
    undocumented = sorted(
        f"{model.__name__}.{name}"
        for model in _models(CampaignSpec)
        for name, field in model.model_fields.items()
        if not field.description
    )
    assert undocumented == [], "add an attribute docstring to: " + ", ".join(
        undocumented
    )


def test_every_campaign_model_has_a_docstring():
    missing = sorted(
        model.__name__ for model in _models(CampaignSpec) if not model.__doc__
    )
    assert missing == []


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_every_attack_parameter_and_role_is_documented(name):
    attack = get_attack_class(name)
    params = attack.params_type
    undocumented = sorted(
        field for field, info in params.model_fields.items() if not info.description
    )
    assert undocumented == [], f"{name}: document {', '.join(undocumented)}"
    assert attack.__doc__, f"{name}: the attack class needs a docstring"


async def _complete(_messages: Any) -> str:
    return "ok"


async def _embed(texts: Any) -> list[list[float]]:
    return [[0.0] for _ in texts]


def _roles(params_type: Any, names: set[str]) -> dict[str, Any]:
    embedders = params_type.embedder_roles()
    return {role: (_embed if role in embedders else _complete) for role in names}


#: Parameters an attack cannot run without (beyond its roles). Their
#: descriptions say "Required."; these are the smallest values that satisfy them.
_REQUIRED_PARAMETERS: dict[str, dict[str, Any]] = {
    "rag": {"documents": ("A document the attack can poison.",)},
}


def _params(name: str, roles: set[str]) -> Any:
    params_type = get_attack_class(name).params_type
    return params_type(
        **_REQUIRED_PARAMETERS.get(name, {}), **_roles(params_type, roles)
    )


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_required_roles_are_enough_to_build_the_attack(name):
    attack = get_attack_class(name)
    params_type = attack.params_type
    assert params_type.REQUIRED_ROLES <= params_type.role_names()
    attack(_params(name, set(params_type.REQUIRED_ROLES)))


@pytest.mark.parametrize(
    ("name", "role"),
    [
        (name, role)
        for name in sorted(ATTACKS)
        for role in sorted(get_attack_class(name).params_type.REQUIRED_ROLES)
    ],
)
def test_each_required_role_is_really_required(name, role):
    attack = get_attack_class(name)
    others = set(attack.params_type.REQUIRED_ROLES) - {role}
    # The error must be about this role, not some other unmet requirement.
    with pytest.raises(ValueError, match=role):
        attack(_params(name, others))
