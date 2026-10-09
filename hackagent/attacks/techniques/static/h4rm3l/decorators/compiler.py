# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Public facade and compiler for the h4rm3l decorator engine."""

from __future__ import annotations

import ast
from collections.abc import Callable
from functools import partial

from ...base import Completion
from .base import DecorationResult, PromptDecorator
from .llm import (
    PAPDecorator,
    PersonaDecorator,
    PersuasiveDecorator,
    ResearcherDecorator,
    SynonymDecorator,
    TransformFxDecorator,
    TranslateDecorator,
    VillainDecorator,
    VisualObfuscationDecorator,
)
from .static import (
    AIMDecorator,
    AffirmativePrefixInjectionDecorator,
    AnswerStyleDecorator,
    Base64Decorator,
    ChainofThoughtDecorator,
    CharCorrupt,
    CharDropout,
    CipherDecorator,
    ColorMixInDecorator,
    DANDecorator,
    DialogStyleDecorator,
    DistractorDecorator,
    FewShotDecorator,
    HexStringMixInDecorator,
    IdentityDecorator,
    JekyllHydeDialogStyleDecorator,
    LIVEGPTDecorator,
    MilitaryWordsMixInDecorator,
    PayloadSplittingDecorator,
    QuestionIdentificationDecorator,
    RefusalSuppressionDecorator,
    ReverseDecorator,
    RoleplayingDecorator,
    STANDecorator,
    StyleInjectionJSONDecorator,
    StyleInjectionShortDecorator,
    TemplateDecorator,
    TranslateBackDecorator,
    UTADecorator,
    WikipediaDecorator,
    WordMixInDecorator,
)

LLM_ASSISTED_DECORATOR_NAMES = {
    "TranslateDecorator",
    "TranslateBackDecorator",
    "PAPDecorator",
    "PersonaDecorator",
    "PersuasiveDecorator",
    "SynonymDecorator",
    "ResearcherDecorator",
    "VillainDecorator",
    "VisualObfuscationDecorator",
    "TransformFxDecorator",
}


def is_llm_assisted_decorator_name(name: str) -> bool:
    """Return True if the decorator class name is LLM-assisted."""
    return name in LLM_ASSISTED_DECORATOR_NAMES


# Decorator classes available to the restricted program compiler.
_DECORATOR_NAMESPACE = {
    # Utility
    "IdentityDecorator": IdentityDecorator,
    "ReverseDecorator": ReverseDecorator,
    # Text-level
    "Base64Decorator": Base64Decorator,
    "CharCorrupt": CharCorrupt,
    "CharDropout": CharDropout,
    "PayloadSplittingDecorator": PayloadSplittingDecorator,
    # Word-level
    "WordMixInDecorator": WordMixInDecorator,
    "ColorMixInDecorator": ColorMixInDecorator,
    "HexStringMixInDecorator": HexStringMixInDecorator,
    "MilitaryWordsMixInDecorator": MilitaryWordsMixInDecorator,
    # Style / suffix
    "QuestionIdentificationDecorator": QuestionIdentificationDecorator,
    "AnswerStyleDecorator": AnswerStyleDecorator,
    "DialogStyleDecorator": DialogStyleDecorator,
    "JekyllHydeDialogStyleDecorator": JekyllHydeDialogStyleDecorator,
    "RefusalSuppressionDecorator": RefusalSuppressionDecorator,
    "AffirmativePrefixInjectionDecorator": AffirmativePrefixInjectionDecorator,
    "StyleInjectionShortDecorator": StyleInjectionShortDecorator,
    "StyleInjectionJSONDecorator": StyleInjectionJSONDecorator,
    # LLM-assisted
    "TranslateDecorator": TranslateDecorator,
    "TranslateBackDecorator": TranslateBackDecorator,
    "PersuasiveDecorator": PersuasiveDecorator,
    "SynonymDecorator": SynonymDecorator,
    "ResearcherDecorator": ResearcherDecorator,
    "VillainDecorator": VillainDecorator,
    "PersonaDecorator": PersonaDecorator,
    "PAPDecorator": PAPDecorator,
    "CipherDecorator": CipherDecorator,
    "ChainofThoughtDecorator": ChainofThoughtDecorator,
    "VisualObfuscationDecorator": VisualObfuscationDecorator,
    # Templates
    "FewShotDecorator": FewShotDecorator,
    "WikipediaDecorator": WikipediaDecorator,
    "DistractorDecorator": DistractorDecorator,
    "AIMDecorator": AIMDecorator,
    "DANDecorator": DANDecorator,
    "STANDecorator": STANDecorator,
    "LIVEGPTDecorator": LIVEGPTDecorator,
    "UTADecorator": UTADecorator,
    "TemplateDecorator": TemplateDecorator,
    # Generic
    "RoleplayingDecorator": RoleplayingDecorator,
    "TransformFxDecorator": TransformFxDecorator,
}


def _missing_completion(name: str) -> Callable[..., PromptDecorator]:
    def constructor(*_args: object, **_kwargs: object) -> PromptDecorator:
        raise ValueError(
            f"{name} rewrites the prompt with a model; configure the 'decorator' role"
        )

    return constructor


def _compiler_namespace(completion: Completion | None) -> dict[str, object]:
    namespace = dict(_DECORATOR_NAMESPACE)
    for name in LLM_ASSISTED_DECORATOR_NAMES - {"TranslateBackDecorator"}:
        namespace[name] = (
            _missing_completion(name)
            if completion is None
            else partial(namespace[name], completion)
        )
    return namespace


def _literal_argument(node: ast.expr) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError) as error:
        raise ValueError("decorator arguments must be literals") from error


def _instantiate_decorator(
    node: ast.expr,
    namespace: dict[str, object],
) -> PromptDecorator:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        raise ValueError("expected a registered decorator constructor")

    name = node.func.id
    try:
        constructor = namespace[name]
    except KeyError as error:
        raise ValueError(f"unknown decorator: {name}") from error
    if not callable(constructor):
        raise ValueError(f"decorator is not callable: {name}")

    args = [_literal_argument(argument) for argument in node.args]
    kwargs = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            raise ValueError("expanded decorator keyword arguments are not allowed")
        kwargs[keyword.arg] = _literal_argument(keyword.value)

    decorator = constructor(*args, **kwargs)
    if not isinstance(decorator, PromptDecorator):
        raise TypeError(f"{name} did not create a PromptDecorator")
    return decorator


def _parse_v2_node(
    node: ast.expr,
    namespace: dict[str, object],
) -> PromptDecorator:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "then"
    ):
        if node.keywords or len(node.args) != 1:
            raise ValueError("then() requires exactly one decorator")
        left = _parse_v2_node(node.func.value, namespace)
        right = _parse_v2_node(node.args[0], namespace)
        return left.then(right)
    return _instantiate_decorator(node, namespace)


def _compile_v1(program: str, namespace: dict[str, object]) -> PromptDecorator:
    """v1: one decorator constructor per statement, applied in order."""
    chain = []
    for statement in ast.parse(program, mode="exec").body:
        if not isinstance(statement, ast.Expr):
            raise ValueError("v1 programs may only contain decorator constructors")
        chain.append(_instantiate_decorator(statement.value, namespace))
    if not chain:
        return IdentityDecorator()
    decorator = chain[0]
    for composing_decorator in chain[1:]:
        decorator = decorator.then(composing_decorator)
    return decorator


def _compile_v2(expression: str, namespace: dict[str, object]) -> PromptDecorator:
    """v2: a single expression chaining decorators with ``.then()``."""
    return _parse_v2_node(ast.parse(expression, mode="eval").body, namespace)


def compile_program(
    program: str,
    syntax_version: int = 2,
    *,
    completion: Completion | None = None,
) -> Callable[[str], DecorationResult]:
    """Compile a decorator program string into a callable.

    Args:
        program: The program string (either v1 or v2 syntax).
        syntax_version: ``1`` for semicolon-separated, ``2`` for ``.then()``.
        completion: The model LLM-assisted decorators rewrite prompts with.

    Returns:
        A function ``(prompt) -> str | Awaitable[str]`` applying the chain.

    Raises:
        ValueError: If ``syntax_version`` is not 1 or 2, the program is not a
            valid decorator chain, or it uses an LLM-assisted decorator
            without a ``completion``.
        SyntaxError: If the program string cannot be parsed.
    """
    namespace = _compiler_namespace(completion)
    if syntax_version == 1:
        return _compile_v1(program, namespace).decorate
    if syntax_version == 2:
        return _compile_v2(program, namespace).decorate
    raise ValueError(f"Unknown syntax_version={syntax_version}; expected 1 or 2")


def program_uses_llm_assisted_decorators(
    program: str,
    syntax_version: int = 2,
) -> bool:
    """Return whether a program names at least one LLM-assisted decorator."""
    mode = "exec" if syntax_version == 1 else "eval"
    try:
        tree = ast.parse(program, mode=mode)
    except SyntaxError:
        return any(name in program for name in LLM_ASSISTED_DECORATOR_NAMES)
    return any(
        isinstance(node, ast.Name) and is_llm_assisted_decorator_name(node.id)
        for node in ast.walk(tree)
    )
