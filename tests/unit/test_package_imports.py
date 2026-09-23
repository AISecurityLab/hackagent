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

    def test_storage_exports(self):
        """Test that the storage types are exported from the package root."""
        from hackagent import LocalBackend, RemoteBackend, Store

        assert Store is not None and LocalBackend and RemoteBackend

    def test_models_connect_import(self):
        """Test that model access can be imported."""
        from hackagent.models import Guarded, ModelFactory, connect

        assert connect and Guarded and ModelFactory

    def test_models_import(self):
        """Test that models can be imported.

        This specifically tests for the python-dateutil dependency
        which is used in model serialization.
        """
        from hackagent.storage._http.api.models import Agent

        assert Agent is not None

    def test_api_modules_import(self):
        """Test that API modules can be imported."""
        from hackagent.storage._http import api

        assert api is not None

    def test_attacks_import(self):
        """Test that attacks module can be imported."""
        from hackagent import attacks

        assert attacks is not None

    def test_core_import(self):
        """Test that the core package can be imported."""
        from hackagent.core import contracts, settings

        assert contracts is not None and settings is not None

    def test_dateutil_dependency(self):
        """Test that python-dateutil is available.

        This dependency is required for ISO date parsing in models.
        """
        from dateutil.parser import isoparse

        assert isoparse is not None

    def test_pydantic_dependency(self):
        """Test that pydantic v2 is available with email extras.

        This dependency is required for model definitions, client classes,
        and storage records throughout the SDK.
        """
        from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator

        assert BaseModel is not None
        assert ConfigDict is not None
        assert PrivateAttr is not None
        assert field_validator is not None


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
