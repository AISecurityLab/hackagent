# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Smoke tests for package import and optional extras.

Layering (depth-0 independence, private ``storage._http``, UI frameworks, and
logging-handler setup) is enforced by import-linter. The unit suite runs that
check in ``test_import_contracts``. This module checks that the package, its
entrypoints, and its declared extras still import.
"""

import importlib
import pkgutil
import subprocess
import sys

import pytest

# Fresh interpreter: the CLI and web entrypoints may load click and flask.
# Textual stays lazy until a TUI command runs. Packages outside interfaces
# must not bind those names. The import graph itself is test_import_contracts.
_ENTRYPOINT_PROBE = """
import importlib
import sys

cli_main = importlib.import_module("hackagent.interfaces.cli.main")
web = importlib.import_module("hackagent.interfaces.web")
assert callable(cli_main.main)
assert callable(cli_main.cli)
assert callable(web.create_app)

assert "click" in sys.modules, "CLI entrypoint did not import click"
assert "flask" in sys.modules, "web entrypoint did not import flask"
assert "textual" not in sys.modules, "entrypoint import loaded textual"

forbidden = ("textual", "flask", "click")
leaks = []
for name, module in sys.modules.items():
    if module is None:
        continue
    if name != "hackagent" and not name.startswith("hackagent."):
        continue
    if name == "hackagent.interfaces" or name.startswith("hackagent.interfaces."):
        continue
    bound = [lib for lib in forbidden if lib in module.__dict__]
    if bound:
        leaks.append(f"{name} binds {bound}")
if leaks:
    raise SystemExit("interface toolkits bound outside interfaces:\\n" + "\\n".join(leaks))
"""

# Fresh interpreter with the technique extras removed from the import path.
# A dev install has faiss, numpy, Pillow, and datasets; this probe must still
# pass, because a bare ``pip install hackagent`` does not.
_BARE_CLI_PROBE = r"""
import importlib.abc
import sys

_BLOCKED = {"faiss", "numpy", "PIL", "datasets", "textual"}


class _BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        root = fullname.split(".", 1)[0]
        if root in _BLOCKED:
            raise ModuleNotFoundError(f"No module named {fullname!r}")
        return None


sys.meta_path.insert(0, _BlockOptional())

from click.testing import CliRunner

from hackagent._version import get_version
from hackagent.interfaces.cli.main import cli, main

assert callable(main)
loaded = sorted(name for name in _BLOCKED if name in sys.modules)
if loaded:
    raise SystemExit("CLI import loaded optional modules: " + ", ".join(loaded))

runner = CliRunner()
version = runner.invoke(cli, ["--version"])
if version.exit_code != 0:
    raise SystemExit(f"--version failed ({version.exit_code}): {version.output}")
expected = get_version()
if expected not in version.output:
    raise SystemExit(f"version {expected!r} not in {version.output!r}")

help_result = runner.invoke(cli, ["--help"])
if help_result.exit_code != 0:
    raise SystemExit(f"--help failed ({help_result.exit_code}): {help_result.output}")

eval_help = runner.invoke(cli, ["eval", "--help"])
if eval_help.exit_code != 0:
    raise SystemExit(
        f"eval --help failed ({eval_help.exit_code}): {eval_help.output}"
    )
for name in ("rag", "mml", "h4rm3l", "autodan_turbo"):
    if name not in eval_help.output:
        raise SystemExit(f"{name} missing from eval help:\n{eval_help.output}")

from hackagent.orchestrator.setup.registry import load_attack

for attack_id, extra in (("rag", "rag"), ("mml", "vision"), ("autodan_turbo", "rag")):
    try:
        load_attack(attack_id)
    except ImportError as exc:
        hint = f"hackagent[{extra}]"
        if hint not in str(exc):
            raise SystemExit(f"{attack_id} hint missing ({hint}): {exc}") from exc
    else:
        raise SystemExit(f"{attack_id} imported without its extra")

from hackagent.attacks.techniques.static.h4rm3l.decorators import IdentityDecorator

try:
    IdentityDecorator()
except ImportError as exc:
    if "hackagent[rag]" not in str(exc):
        raise SystemExit(f"h4rm3l hint missing: {exc}") from exc
else:
    raise SystemExit("h4rm3l decorator constructed without numpy")
"""


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
        from hackagent.interfaces.cli.main import cli

        assert cli is not None

    def test_interface_entrypoints_import(self):
        """CLI and web entrypoints import without leaking UI toolkits.

        ``hackagent.interfaces.cli.main:main`` is the console script. The
        dashboard is ``hackagent.interfaces.web.create_app``. Click and flask
        load with those modules; textual does not. Modules outside
        ``interfaces`` must not bind those names.
        """
        result = subprocess.run(
            [sys.executable, "-c", _ENTRYPOINT_PROBE],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_cli_runs_without_technique_extras(self):
        """``hackagent --version`` and ``--help`` do not need rag, vision, or hf.

        The console script imports the eval catalog, which loads every
        technique config. That import must not pull FAISS, NumPy, Pillow,
        or Hugging Face ``datasets``. Commands that need those libraries
        still fail with an install hint when the technique is loaded.
        """
        result = subprocess.run(
            [sys.executable, "-c", _BARE_CLI_PROBE],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_lazy_technique_packages_still_export_classes(self):
        """Package imports keep working once the extras are installed."""
        pytest.importorskip("faiss")
        pytest.importorskip("numpy")
        pytest.importorskip("PIL")
        from hackagent.attacks.techniques.adaptive.autodan_turbo import (
            AutoDANTurboAttack,
        )
        from hackagent.attacks.techniques.indirect.rag import RagAttack
        from hackagent.attacks.techniques.static.h4rm3l import H4rm3lAttack
        from hackagent.attacks.techniques.static.mml import MMLAttack

        assert RagAttack.__name__ == "RagAttack"
        assert MMLAttack.__name__ == "MMLAttack"
        assert H4rm3lAttack.__name__ == "H4rm3lAttack"
        assert AutoDANTurboAttack.__name__ == "AutoDANTurboAttack"

    def test_agent_import(self):
        """Test that the HackAgent class can be imported."""
        from hackagent import HackAgent

        assert HackAgent is not None

    def test_public_exports(self):
        """The package root exports the facade and public types only."""
        from hackagent import AgentType, ApiError, HackAgent, Settings

        assert AgentType and ApiError and HackAgent and Settings

    def test_root_import_does_not_load_interface_toolkits(self):
        """Importing the facade must not pull in textual, flask, or click."""
        code = (
            "import sys, hackagent; "
            "bad = [n for n in ('textual', 'flask', 'click') if n in sys.modules]; "
            "raise SystemExit(0 if not bad else 1)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_optional_extras_are_declared(self):
        """The packaging metadata names the optional extras and their packages."""
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        section = text.split("[project.optional-dependencies]", 1)[1].split("\n[", 1)[0]
        for extra, package in {
            "tui": "textual",
            "web": "flask",
            "browser": "playwright",
            "rag": "faiss-cpu",
            "vision": "Pillow",
            "hf": "datasets",
        }.items():
            assert f"{extra} =" in section or f"{extra}=" in section
            assert package in section
        assert "numpy" in section

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
