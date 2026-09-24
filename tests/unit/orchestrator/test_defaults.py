# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Role defaults are a pure function of config and Settings."""

from hackagent.core.defaults import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_REMOTE_ATTACKER_IDENTIFIER,
)
from hackagent.core.settings import Settings
from hackagent.orchestrator.setup.defaults import apply_role_defaults

_NO_FILE = "/nonexistent/hackagent/config.json"


def _settings(*, api_key=None) -> Settings:
    return Settings.resolve(api_key=api_key, env={}, config_path=_NO_FILE)


def test_local_defaults_fill_missing_roles_and_keep_explicit_fields():
    resolved = apply_role_defaults(
        {
            "attack_type": "pair",
            "attacker": {"identifier": "kept-model"},
        },
        _settings(),
    )
    assert resolved["attacker"]["identifier"] == "kept-model"
    assert resolved["attacker"]["endpoint"]
    assert resolved["judge"]["identifier"] == DEFAULT_LOCAL_MODEL
    assert "api_key" not in resolved["judge"] or resolved["judge"]["api_key"] is None


def test_remote_defaults_use_the_hosted_attacker():
    resolved = apply_role_defaults(
        {"attack_type": "pair"},
        _settings(api_key="sk-test"),
    )
    assert resolved["attacker"]["identifier"] == DEFAULT_REMOTE_ATTACKER_IDENTIFIER
    assert resolved["attacker"]["api_key"] == "sk-test"
    assert resolved["judge"]["api_key"] == "sk-test"
