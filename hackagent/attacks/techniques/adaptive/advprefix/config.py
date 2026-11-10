# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for AdvPrefix."""

from typing import ClassVar, Optional

from pydantic import Field, field_validator, model_validator

from ...contract import AttackParams, Completion
from .prompts import META_PREFIXES


class AdvPrefixParams(AttackParams):
    """How many prefixes to write, how many times to try each, and who writes them.

    ``attacker`` is a role: the uncensored model that writes the candidate
    prefixes, so AdvPrefix cannot run without it.

    The selection rule and its weights follow the paper; the sample counts
    are scaled down from the reference, as each field says. The one knob
    worth reading before a big run is :attr:`samples_per_candidate`, which
    multiplies the target calls: a goal costs roughly
    ``candidates_per_goal * samples_per_candidate`` target calls on top of
    one writer call per requested candidate.
    """

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker"})

    meta_prefixes: tuple[str, ...] = Field(
        default=META_PREFIXES,
        description=(
            "Openings the writer continues, as the literal first words of the "
            "prefix; an empty string lets it open freely."
        ),
    )
    samples_per_prefix: int | tuple[int, ...] = Field(
        default=4,
        description=(
            "Candidates asked for per opening. One count for all of them, or one "
            "per opening. The reference uses ``(50, 50, 50, 150)``; the default "
            "here is far smaller because every candidate costs a writer call."
        ),
    )
    min_char_length: int = Field(
        default=10,
        ge=0,
        description=(
            "Shortest candidate worth keeping. The reference counts tokens "
            "(``min_token_length``); counting characters needs no tokenizer."
        ),
    )
    max_prefix_chars: int = Field(
        default=300,
        ge=1,
        description=(
            "Maximum prefix length sent to the target. Longer attacker-generated "
            "prefixes are truncated to this character limit."
        ),
    )
    require_linebreak: bool = Field(
        default=True,
        description=(
            "Keep only candidates with a line break, which is what makes a prefix "
            "look mid-document."
        ),
    )
    candidates_per_goal: int = Field(
        default=5,
        ge=1,
        description=(
            "Candidates carried into the attack, after filtering. The reference "
            "uses 100; each one costs ``samples_per_candidate`` target calls."
        ),
    )
    samples_per_candidate: int = Field(
        default=4,
        ge=1,
        description=(
            "Completions drawn per candidate. The prefilling attack success rate is"
            " the share of these the panel passes, so one sample makes it a coin "
            "flip rather than a rate. The reference draws 25; the default here is "
            "smaller because it runs against an endpoint rather than a local batch,"
            " and every sample is another target call per candidate."
        ),
    )
    prefixes_per_goal: int = Field(
        default=1,
        ge=1,
        description=(
            "Prefixes marked selected as this goal's result, as the reference does."
            " Every attempt is still judged and reported."
        ),
    )
    pasr_weight: float = Field(
        default=10.0,
        gt=0.0,
        description=(
            "How much a better attack success rate is worth against a higher "
            "negative log-likelihood, in the reference's selection score "
            "``-pasr_weight * log(pasr) + nll``."
        ),
    )
    pasr_tol: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "How far below the best attack success rate a prefix may still be "
            "selected. ``0`` keeps only prefixes that match the best."
        ),
    )
    nll_tol: float = Field(
        default=999.0,
        ge=0.0,
        description=(
            "How far above the best prefix's negative log-likelihood another may "
            "be. Inactive unless the target reports token logprobs, which the model"
            " contract does not yet carry."
        ),
    )
    prefill: bool = Field(
        default=True,
        description=(
            "Put the prefix in the assistant turn, which is the paper's attack. "
            "Turn it off for an endpoint that rejects a trailing assistant message;"
            " the goal then asks for the prefix instead of supplying it."
        ),
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Writes the candidate prefixes by continuing a short opening such as "
            "'Sure' or 'Here'. Best served by an uncensored model, which does not "
            "refuse to write them."
        ),
    )

    @field_validator("samples_per_prefix")
    @classmethod
    def check_samples(cls, value: int | tuple[int, ...]) -> int | tuple[int, ...]:
        """Reject a single count below 1 or a negative per-opening count."""
        if isinstance(value, int):
            if value < 1:
                raise ValueError("samples_per_prefix must be at least 1")
            return value
        if any(count < 0 for count in value):
            raise ValueError("per-opening sample counts cannot be negative")
        return value

    @model_validator(mode="after")
    def check_samples_match_prefixes(self) -> "AdvPrefixParams":
        """Reject per-opening counts that do not match ``meta_prefixes`` one to one."""
        counts = self.samples_per_prefix
        if isinstance(counts, tuple) and len(counts) != len(self.meta_prefixes):
            raise ValueError(
                f"samples_per_prefix has {len(counts)} counts for "
                f"{len(self.meta_prefixes)} meta prefixes."
            )
        return self


__all__ = ["AdvPrefixParams"]
