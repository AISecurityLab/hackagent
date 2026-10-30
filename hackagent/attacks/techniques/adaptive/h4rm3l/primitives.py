# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The catalogue of primitives the synthesizer is allowed to write with.

A name on its own does not say how to call the thing. Shown only
``CharCorrupt``, a model writes ``CharCorrupt(corruption_rate=0.1)``, which
is a reasonable guess and not the signature, and the program is thrown away
by the compiler having cost a round. So the catalogue carries each
constructor's parameters, read off the classes the compiler itself accepts.

It also carries only what can be built right now. Ten primitives rewrite the
prompt with a model and take a ``completion``, which comes from the optional
``decorator`` role; with no such role the compiler rejects every program that
names one. Offering them anyway asks the synthesizer to spend proposals on
programs that cannot run.
"""

from __future__ import annotations

import inspect

from .decorators import decorator_namespace

#: Supplied by the compiler, never written by a program.
_SUPPLIED = frozenset({"self", "completion"})


def _render(name: str, cls: type) -> str:
    """``name`` with its parameters, as a program would write the call."""
    try:
        signature = inspect.signature(cls.__init__)
    except (TypeError, ValueError):  # pragma: no cover - builtins have none
        return f"{name}()"

    parts = []
    for parameter in signature.parameters.values():
        if parameter.name in _SUPPLIED:
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        annotation = parameter.annotation
        kind = (
            annotation
            if isinstance(annotation, str)
            else getattr(annotation, "__name__", "")
        )
        rendered = f"{parameter.name}: {kind}" if kind else parameter.name
        if parameter.default is not parameter.empty:
            rendered += f" = {parameter.default!r}"
        parts.append(rendered)
    return f"{name}({', '.join(parts)})"


def needs_decorator_model(cls: type) -> bool:
    """Whether building ``cls`` requires the optional ``decorator`` role."""
    try:
        return "completion" in inspect.signature(cls.__init__).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins have none
        return False


def primitive_signatures(*, with_decorator_model: bool) -> list[str]:
    """Every primitive that can be built, rendered as a call signature.

    With no ``decorator`` role the model-backed primitives are left out
    rather than advertised and then rejected.
    """
    return [
        _render(name, cls)
        for name, cls in decorator_namespace().items()
        if with_decorator_model or not needs_decorator_model(cls)
    ]


__all__ = ["needs_decorator_model", "primitive_signatures"]
