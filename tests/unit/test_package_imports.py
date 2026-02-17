# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Test that all package modules can be imported correctly.
This test ensures that all dependencies are properly declared in pyproject.toml
and the package can be installed and used without import errors.
"""

import importlib
import pkgutil
import pytest


class TestPackageImports:
    """Test suite to verify all hackagent modules can be imported."""

    def test_main_package_import(self):
        """Test that the main hackagent package can be imported."""
        import hackagent

        assert hackagent is not None

    def test_cli_main_import(self):
        """Test that the CLI entry point can be imported.

        This is the entry point for the hackagent CLI command.
        If this fails, users won't be able to run 'hackagent' commands.
        """
        from hackagent.cli.main import cli

        assert cli is not None

    def test_agent_import(self):
        """Test that the HackAgent class can be imported."""
        from hackagent import HackAgent

        assert HackAgent is not None

    def test_client_import(self):
        """Test that the Client class can be imported."""
        from hackagent import Client

        assert Client is not None

    def test_router_import(self):
        """Test that the AgentRouter can be imported."""
        from hackagent.router import AgentRouter

        assert AgentRouter is not None

    def test_models_import(self):
        """Test that models can be imported.

        This specifically tests for the python-dateutil dependency
        which is used in model serialization.
        """
        from hackagent.models import Agent

        assert Agent is not None

    def test_api_modules_import(self):
        """Test that API modules can be imported."""
        from hackagent import api

        assert api is not None

    def test_attacks_import(self):
        """Test that attacks module can be imported."""
        from hackagent import attacks

        assert attacks is not None

    def test_utils_import(self):
        """Test that utils module can be imported."""
        from hackagent import utils

        assert utils is not None

    def test_dateutil_dependency(self):
        """Test that python-dateutil is available.

        This dependency is required for ISO date parsing in models.
        """
        from dateutil.parser import isoparse

        assert isoparse is not None

    def test_attrs_dependency(self):
        """Test that attrs is available.

        This dependency is required for model definitions.
        """
        from attrs import define, field

        assert define is not None
        assert field is not None


class TestAllSubmodulesImportable:
    """Test that all submodules in hackagent are importable."""

    @pytest.fixture
    def hackagent_submodules(self):
        """Get list of all hackagent submodules."""
        import hackagent

        submodules = []
        package_path = hackagent.__path__
        prefix = hackagent.__name__ + "."

        for importer, modname, ispkg in pkgutil.walk_packages(
            package_path, prefix=prefix
        ):
            submodules.append(modname)

        return submodules

    def test_all_submodules_importable(self, hackagent_submodules):
        """Test that all discovered submodules can be imported.

        This is a comprehensive test that walks through all modules
        in the hackagent package and attempts to import them.
        This helps catch missing dependencies early.
        """
        failed_imports = []

        for modname in hackagent_submodules:
            try:
                importlib.import_module(modname)
            except ImportError as e:
                failed_imports.append((modname, str(e)))

        if failed_imports:
            error_msg = "Failed to import the following modules:\n"
            for modname, error in failed_imports:
                error_msg += f"  - {modname}: {error}\n"
            pytest.fail(error_msg)


class TestDependenciesAvailable:
    """Test that all required dependencies are installed."""

    @pytest.mark.parametrize(
        "package_name",
        [
            "requests",
            "pydantic",
            "litellm",
            "openai",
            "rich",
            "click",
            "yaml",  # pyyaml
            "textual",
            "dateutil",  # python-dateutil
            "attrs",
        ],
    )
    def test_dependency_importable(self, package_name):
        """Test that each required dependency can be imported."""
        try:
            importlib.import_module(package_name)
        except ImportError:
            pytest.fail(
                f"Required dependency '{package_name}' is not installed. "
                f"Please add it to pyproject.toml dependencies."
            )
