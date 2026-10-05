# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every example parses, and none still calls the removed HackAgent constructor."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_EXAMPLES = _ROOT / "hackagent" / "examples"

# These scripts do their work at import time (network, a missing index, or a
# required API key plus a document). They still have to parse.
_IMPORT_SKIP = {
    "openai_sdk/rag/ingest.py",
    "langchain/rag/ingest.py",
    "langchain/rag/read_db.py",
    "langchain/rag/agent_client.py",
}

_SESSION_KWARGS = {"backend", "timeout", "raise_on_unexpected_status"}


def _example_paths() -> list[Path]:
    return sorted(_EXAMPLES.rglob("*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(_EXAMPLES).as_posix()


def _module_name(path: Path) -> str:
    relative = path.relative_to(_EXAMPLES).with_suffix("")
    return "hackagent.examples." + ".".join(relative.parts)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _importable() -> list[Path]:
    return [path for path in _example_paths() if _rel(path) not in _IMPORT_SKIP]


@pytest.mark.parametrize("path", _example_paths(), ids=_rel)
def test_example_parses_and_uses_the_current_client(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    compile(source, str(path), "exec")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "HackAgent":
            continue
        keywords = {keyword.arg for keyword in node.keywords}
        assert None not in keywords, path
        assert keywords <= _SESSION_KWARGS, path
        assert node.args, path
        assert isinstance(node.args[0], ast.Call)
        assert _call_name(node.args[0].func) == "resolve", path

    if "HackAgent" in source and ".hack(" in source:
        assert ".target(" in source, path


def _load_as_script(path: Path):
    """Execute ``path`` the way ``python path`` does, without package ``__init__``."""
    name = "example_script_" + "_".join(
        path.relative_to(_EXAMPLES).with_suffix("").parts
    )
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


@pytest.mark.parametrize("path", _importable(), ids=_rel)
def test_example_imports(path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("HACKAGENT_DB_PATH", ":memory:")
    try:
        importlib.import_module(_module_name(path))
        return
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing.startswith("hackagent"):
            raise
    # A package __init__ may import an optional SDK the script itself does not.
    try:
        _load_as_script(path)
    except ImportError:
        pytest.skip(f"optional dependency {missing} is not installed")
