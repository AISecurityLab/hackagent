# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Form field keys must target config keys the techniques actually read."""

import pytest

from hackagent.interfaces.tui.forms import get_all_attack_specs

ALL_FIELDS = [
    (technique, field.key)
    for technique, spec in get_all_attack_specs().items()
    for field in spec.fields
]


@pytest.mark.parametrize("technique,key", ALL_FIELDS)
def test_model_fields_use_identifier(technique, key):
    # Role routers are built from ``<role>.identifier``; a ``<role>.model``
    # field is silently ignored.
    assert not key.endswith(".model"), f"{technique}: use '.identifier' in {key!r}"


def test_pair_form_uses_schema_scalars_not_a_model_alias():
    """Role dicts have no nested JSON schema, so they are not expanded.

    Scalar technique fields still come from the pydantic model, and no
    field is spelled ``.model`` (routers read ``identifier``).
    """
    keys = {field.key for field in get_all_attack_specs()["pair"].fields}

    assert "attacker_feedback_max_chars" in keys
    assert not any(key.endswith(".model") for key in keys)
