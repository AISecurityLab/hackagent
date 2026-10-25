# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The shared credential resolver: one precedence, no silent fallbacks."""

from __future__ import annotations

import pytest

from hackagent.core.contracts.specs import ModelSpec
from hackagent.core.credentials import CredentialError, resolve_api_key


def test_an_explicit_value_wins_over_the_default_variable():
    env = {"HACKAGENT_API_KEY": "platform"}
    assert resolve_api_key("runtime", default_env="HACKAGENT_API_KEY", env=env) == (
        "runtime"
    )


def test_a_value_is_never_treated_as_a_variable_name():
    env = {"MY_KEY": "secret"}
    assert resolve_api_key("MY_KEY", env=env) == "MY_KEY"
    assert resolve_api_key("${MY_KEY}", env=env) == "${MY_KEY}"


def test_an_explicit_reference_reads_the_named_variable():
    env = {"MY_KEY": " secret ", "HACKAGENT_API_KEY": "platform"}
    assert (
        resolve_api_key(None, "MY_KEY", default_env="HACKAGENT_API_KEY", env=env)
        == "secret"
    )


def test_the_default_variable_is_used_when_nothing_is_explicit():
    env = {"HACKAGENT_API_KEY": "platform"}
    assert resolve_api_key(default_env="HACKAGENT_API_KEY", env=env) == "platform"


def test_both_inputs_conflict():
    with pytest.raises(CredentialError, match="not both"):
        resolve_api_key("value", "NAME", env={"NAME": "x"})


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_explicit_value_is_an_error(value):
    with pytest.raises(CredentialError, match="api_key is empty"):
        resolve_api_key(value, default_env="D", env={"D": "fallback"})


def test_an_empty_reference_name_is_an_error():
    with pytest.raises(CredentialError, match="api_key_env is empty"):
        resolve_api_key(None, " ", env={})


@pytest.mark.parametrize(
    ("env", "message"),
    [({}, "is not set"), ({"MY_KEY": "  "}, "is empty")],
)
def test_an_explicit_reference_never_falls_back(env, message):
    env = {**env, "HACKAGENT_API_KEY": "platform"}
    with pytest.raises(CredentialError, match=message):
        resolve_api_key(None, "MY_KEY", default_env="HACKAGENT_API_KEY", env=env)


def test_an_optional_default_may_be_missing():
    assert resolve_api_key(default_env="HACKAGENT_API_KEY", env={}) is None
    assert resolve_api_key(env={}) is None


def test_a_required_default_must_be_set():
    with pytest.raises(CredentialError, match="HACKAGENT_API_KEY"):
        resolve_api_key(default_env="HACKAGENT_API_KEY", required=True, env={})
    with pytest.raises(CredentialError, match="is required"):
        resolve_api_key(required=True, env={})


def test_errors_never_contain_the_secret():
    with pytest.raises(CredentialError) as excinfo:
        resolve_api_key("sk-very-secret", "NAME", env={})
    assert "sk-very-secret" not in str(excinfo.value)


def test_model_spec_never_exports_or_shows_a_literal_key():
    spec = ModelSpec(identifier="m", api_key="sk-very-secret")
    assert "api_key" not in spec.model_dump()
    assert "sk-very-secret" not in spec.model_dump_json()
    assert "sk-very-secret" not in repr(spec)
    assert spec.api_key == "sk-very-secret"


def test_model_spec_keeps_the_reference_name():
    spec = ModelSpec(identifier="m", api_key_env="PROVIDER_KEY")
    assert spec.model_dump()["api_key_env"] == "PROVIDER_KEY"


def test_model_spec_rejects_both_inputs():
    with pytest.raises(ValueError, match="not both"):
        ModelSpec(identifier="m", api_key="k", api_key_env="K")
