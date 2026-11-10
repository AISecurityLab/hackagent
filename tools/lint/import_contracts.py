# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Import-linter contract: logging handlers belong to interfaces."""

from __future__ import annotations

import ast
from pathlib import Path

from importlinter.application import output
from importlinter.domain.contract import Contract, ContractCheck

_HANDLER_CALLS = frozenset({"addHandler", "basicConfig", "dictConfig", "fileConfig"})
_HANDLER_MODULES = frozenset({"logging.handlers", "rich.logging"})


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _imports_handler_module(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name in _HANDLER_MODULES for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return module in _HANDLER_MODULES or any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in _HANDLER_MODULES
        )
    return False


class LoggingHandlersContract(Contract):
    """Fail when library code installs a logging handler.

    Interfaces own handler setup (the CLI installs a Rich handler). Every
    other module may obtain loggers and set levels, but must not call
    ``addHandler`` / ``basicConfig`` / ``dictConfig`` / ``fileConfig`` or
    import ``logging.handlers`` or ``rich.logging``.
    """

    type_name = "logging_handlers"

    def check(self, graph, verbose: bool) -> ContractCheck:
        del graph, verbose
        violations: list[str] = []
        root = Path("hackagent")
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or "interfaces" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                violations.append(f"{path}:{exc.lineno}: {exc.msg}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node) in _HANDLER_CALLS:
                    violations.append(
                        f"{path}:{node.lineno}: {_call_name(node)}() "
                        "installs a logging handler"
                    )
                elif _imports_handler_module(node) and isinstance(
                    node, (ast.Import, ast.ImportFrom)
                ):
                    violations.append(
                        f"{path}:{node.lineno}: imports a logging-handler module"
                    )
        return ContractCheck(
            kept=not violations,
            metadata={"violations": violations},
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        output.print_error(
            "Logging handlers are installed outside hackagent.interfaces:",
            bold=True,
        )
        for violation in check.metadata["violations"]:
            output.print_error(f"    {violation}")
