# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What every campaign attack depends on, and how it is configured.

An attack never builds, configures, or calls a model on its own. Whatever
it needs is a callable supplied from outside:

- a *role* is an auxiliary model. Most are annotated :data:`Completion`
  (chat messages in, reply text out), such as an attacker or a decorator;
  one, :data:`Embedder` (texts in, vectors out), is how a retrieval attack
  reaches an embedding model;
- the *target* is passed to iterative attacks at run time as a
  :data:`Target`;
- the *judge* is passed with it as a :data:`Judge`. It is the campaign's
  evaluation panel: an iterative attack consults it while it searches, and
  its verdict on each exchange is what the run reports.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar, get_args

from pydantic import BaseModel, ConfigDict

from hackagent.core.contracts import Sample, Verdict
from hackagent.core.contracts.protocols import CompletionResult

Message = dict[str, Any]
Messages = list[Message]

#: An auxiliary model: chat messages in, reply text out. It raises when the
#: model gives no usable reply.
Completion = Callable[[Messages], Awaitable[str]]

#: The model under test. Called with the chat history, and optionally with
#: keyword overrides the model layer understands (``tools`` schemas,
#: ``tool_choice``, sampling). It never raises: a provider error or a
#: guardrail block comes back as a reply that is not ``ok``.
Target = Callable[..., Awaitable[CompletionResult]]


#: An embedding model: a batch of texts in, one vector each out. A
#: retrieval attack embeds its poisoned documents and its queries through
#: this, and never builds an embeddings client itself. It raises when the
#: model cannot be reached.
Embedder = Callable[[Sequence[str]], Awaitable[list[list[float]]]]


#: The evaluation panel, as an attack sees it while it searches. It raises
#: when the panel cannot be reached; a panel that abstains returns a
#: :class:`~hackagent.core.contracts.Verdict` carrying ``error``.
Judge = Callable[[Sample], Awaitable[Verdict]]


class AttackParams(BaseModel):
    """Validated, immutable attack configuration.

    Fields annotated with :data:`Completion` or :data:`Embedder`
    (optionally ``| None``) are roles. Every other field is a plain
    algorithm parameter.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Roles the attack cannot run without. Every other role is optional.
    #: Read by campaign resolution (to report a missing role clearly) and by the
    #: documentation generator.
    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def _fields_of(cls, kind: Any) -> frozenset[str]:
        return frozenset(
            name
            for name, field in cls.model_fields.items()
            if field.annotation == kind or kind in get_args(field.annotation)
        )

    @classmethod
    def completion_roles(cls) -> frozenset[str]:
        """Role fields that take a chat model."""
        return cls._fields_of(Completion)

    @classmethod
    def embedder_roles(cls) -> frozenset[str]:
        """Role fields that take an embedding model."""
        return cls._fields_of(Embedder)

    @classmethod
    def role_names(cls) -> frozenset[str]:
        """Names of every field that takes an auxiliary model."""
        return cls.completion_roles() | cls.embedder_roles()


__all__ = [
    "AttackParams",
    "Completion",
    "Embedder",
    "Judge",
    "Message",
    "Messages",
    "Target",
]
