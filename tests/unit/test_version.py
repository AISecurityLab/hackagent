# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the frozen-binary friendly version lookup."""

from importlib.metadata import PackageNotFoundError

from hackagent import _version


def test_get_version_uses_distribution_metadata():
    assert _version.get_version() == _version._distribution_version("hackagent")


def test_get_version_falls_back_to_build_version(monkeypatch):
    def _raise(_name):
        raise PackageNotFoundError("hackagent")

    monkeypatch.setattr(_version, "_distribution_version", _raise)
    monkeypatch.setenv("HACKAGENT_BUILD_VERSION", "1.2.3")

    assert _version.get_version() == "1.2.3"


def test_get_version_falls_back_to_unknown(monkeypatch):
    def _raise(_name):
        raise PackageNotFoundError("hackagent")

    monkeypatch.setattr(_version, "_distribution_version", _raise)
    monkeypatch.delenv("HACKAGENT_BUILD_VERSION", raising=False)

    assert _version.get_version() == _version.UNKNOWN_VERSION


def test_cli_version_flag_reports_version():
    from click.testing import CliRunner

    from hackagent.cli.main import cli

    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert _version.get_version() in result.output
