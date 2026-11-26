# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What is wrong with a campaign document, each problem where it is.

One check for every interface: the TUI's builder shows its issues on the
fields they concern, ``hackagent campaign validate`` and ``campaign run``
print them, and :func:`~hackagent.orchestrator.campaign.load_campaign`
raises them as :class:`CampaignInvalid`. Each :class:`Issue` names the
document path it is about (``attacks.0``) and says what is wrong in a
sentence, rather than a validation library's report.

Three kinds of problem are found, in this order: an API key written into
the file instead of referenced; an attack's parameters or roles that
resolving the campaign would reject; and anything else the campaign format
does not allow.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError

from hackagent.core.credentials import CredentialError, validate_file_credentials
from hackagent.orchestrator.campaign.spec import CampaignSpec

Path = tuple[Any, ...]


@dataclass(frozen=True)
class Issue:
    """A problem at a document path: ``attacks.0``, ``Unknown attack…``."""

    loc: Path
    message: str

    @property
    def where(self) -> str:
        """The path as written in the document: ``attacks.0.parameters``."""
        return ".".join(str(part) for part in self.loc)

    def __str__(self) -> str:
        return f"{self.where}: {self.message}" if self.loc else self.message


class CampaignInvalid(ValueError):
    """A campaign document with :attr:`issues`; its message lists them, one
    per line."""

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


def campaign_issues(
    values: Mapping[str, Any],
) -> tuple[Optional[CampaignSpec], tuple[Issue, ...]]:
    """Check a campaign document: its spec when there is nothing to fix,
    else ``None`` and what to fix."""
    credentials = _credential_issues(values)
    if credentials:
        return None, tuple(credentials)
    issues = _attack_issues(values)
    try:
        spec: Optional[CampaignSpec] = CampaignSpec.model_validate(dict(values))
    except ValidationError as exc:
        spec = None
        issues.extend(issues_from(exc))
    return (spec if not issues else None), tuple(_most_specific(issues))


def _most_specific(issues: Sequence[Issue]) -> list[Issue]:
    """Drop an issue another one explains from inside it: an attack list
    "too short" because its only attack has an unknown name says nothing
    the attack's own issue does not."""
    return [
        issue
        for issue in issues
        if not any(
            other.loc[: len(issue.loc)] == issue.loc and len(other.loc) > len(issue.loc)
            for other in issues
        )
    ]


def issues_from(error: ValidationError) -> list[Issue]:
    """A validation error's problems, each at its path, in a sentence."""
    return _most_specific(_issues_from(error))


def _issues_from(error: ValidationError) -> list[Issue]:
    issues = []
    for found in error.errors(include_url=False):
        message = str(found.get("msg") or "Invalid value")
        if message == "Field required":
            message = "required"
        issues.append(
            Issue(tuple(found.get("loc") or ()), message.removeprefix("Value error, "))
        )
    return issues


def _credential_issues(value: Any, path: Path = ()) -> list[Issue]:
    """An API key written in the document, where a reference belongs."""
    issues = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"api_key", "api_key_env"}:
                try:
                    validate_file_credentials({key: child})
                except CredentialError as exc:
                    issues.append(Issue((*path, key), str(exc)))
            else:
                issues.extend(_credential_issues(child, (*path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_credential_issues(child, (*path, index)))
    return issues


def _attack_issues(values: Mapping[str, Any]) -> list[Issue]:
    """What resolving the campaign would reject: bad parameters, missing roles."""
    from hackagent.attacks.techniques.registry import ATTACKS, get_attack_class

    issues = []
    attacks = values.get("attacks")
    for index, attack in enumerate(attacks if isinstance(attacks, list) else ()):
        name = attack.get("name") if isinstance(attack, Mapping) else None
        if name not in ATTACKS:
            continue
        params = get_attack_class(name).params_type
        root = ("attacks", index)
        try:
            params.model_validate(attack.get("parameters") or {})
        except ValidationError as exc:
            for found in exc.errors(include_url=False):
                issues.append(
                    Issue(
                        root + ("parameters", *tuple(found.get("loc") or ())),
                        str(found.get("msg") or "Invalid value"),
                    )
                )
        roles = attack.get("roles") or {}
        for role in sorted(params.REQUIRED_ROLES - set(roles)):
            issues.append(
                Issue(root + ("roles", role), f"{name} requires the {role} model")
            )
    return issues


__all__ = ["CampaignInvalid", "Issue", "campaign_issues", "issues_from"]
