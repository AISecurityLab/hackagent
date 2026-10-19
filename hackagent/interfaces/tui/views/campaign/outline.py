# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The outline of a campaign: one node per part of the schema being edited."""

from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Iterable
from typing import Any, Literal, Optional

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from hackagent.datasets.config import PresetSource, ProviderSource
from hackagent.datasets.presets import PRESETS
from hackagent.evaluation.judges import EVALUATOR_MAP
from hackagent.models.config import ModelConfig
from hackagent.orchestrator.campaign.spec import (
    CampaignDatasetSpec,
    CampaignMetadata,
    EvaluationSpec,
    ExecutionSpec,
    GuardrailModelConfig,
    JudgeSpec,
    ScoringSpec,
)

from .draft import CampaignDraft
from .schema import (
    FieldDef,
    Group,
    Path,
    attack_fields,
    attack_roles,
    field_groups,
    role_description,
)

NodeKind = Literal["section", "group", "attack", "model", "add_attack", "add_judge"]

# Free-text fields that only accept a registered name, keyed by the model they
# belong to: two models can share a field name and mean different things.
_CHOICES: dict[tuple[type[BaseModel], str], tuple[str, ...]] = {
    (PresetSource, "name"): tuple(sorted(PRESETS)),
    (ProviderSource, "provider"): ("huggingface", "file", "url_json"),
    (ScoringSpec, "type"): tuple(sorted(EVALUATOR_MAP)),
}

#: Panels whose title reads better than the field name it comes from.
_TITLES = {
    "source": "Source",
    "selection": "Selection",
    "filters": "Filters",
    "classifier": "Classifier",
    "connection": "Connection",
    "generation": "Generation",
    "scoring": "Scoring",
    "audit": "Audit",
    "dataset": "Calibration set",
    "robustness": "Robustness",
    "concurrency": "Concurrency",
    "retries": "Retries",
    "output": "Output",
    "storage": "Storage",
}


def _named(fields: Iterable[FieldDef]) -> list[FieldDef]:
    """Give a field its registered choices, where the schema only says `str`."""
    return [
        replace(field, kind="choice", choices=choices)
        if field.kind == "str"
        and (choices := _CHOICES.get((field.owner, field.path[-1])))
        else field
        for field in fields
    ]


@dataclass(frozen=True)
class Node:
    """One entry of the outline and the panel it opens."""

    kind: NodeKind
    root: Path
    title: str
    description: str = ""
    model: Optional[type[BaseModel]] = None
    optional: bool = False
    attack: Optional[str] = None
    #: Set instead of ``model`` when this panel edits a tagged union.
    union: Optional[FieldInfo] = None

    def groups(self, draft: Optional[CampaignDraft] = None) -> list[Group]:
        """The boxes this panel shows, each a nested model of the schema.

        ``draft`` is needed where the schema branches: a tagged union shows the
        tag and only the fields of the variant the document currently names.
        """
        if self.kind == "attack" and self.attack:
            return [Group("", (), False, "", tuple(_named(attack_fields(self.attack))))]
        if self.model is None:
            return []
        chosen = None
        if draft is not None:
            root = self.root

            def chosen(path: Path) -> Any:  # noqa: F811
                return draft.get(root + path)[1]

        return [
            replace(group, fields=tuple(_named(group.fields)))
            for group in field_groups(self.model, chosen=chosen)
        ]

    def fields(self, draft: Optional[CampaignDraft] = None) -> list[FieldDef]:
        """Every row of this panel, boxes flattened."""
        return [field for group in self.groups(draft) for field in group.fields]

    def enabled(self, draft: CampaignDraft) -> bool:
        return not self.optional or draft.get(self.root)[0]


@dataclass
class Outline:
    node: Node
    children: list["Outline"]


def _doc(model: type[BaseModel]) -> str:
    return (model.__doc__ or "").strip().split("\n\n")[0].replace("\n", " ")


def build_outline(draft: CampaignDraft) -> list[Outline]:
    """The outline for the draft's current shape (its attacks, judges...)."""
    from hackagent.attacks.techniques.registry import ATTACKS

    attacks: list[Outline] = []
    for index, attack in enumerate(draft.items(("attacks",))):
        name = attack.get("name") if isinstance(attack, dict) else None
        root = ("attacks", index)
        if name not in ATTACKS:
            attacks.append(Outline(Node("attack", root, str(name or "?")), []))
            continue
        roles, required = attack_roles(name)
        attacks.append(
            Outline(
                Node("attack", root, name, attack=name),
                [
                    Outline(
                        Node(
                            "model",
                            root + ("roles", role),
                            role,
                            role_description(name, role),
                            ModelConfig,
                            optional=role not in required,
                        ),
                        [],
                    )
                    for role in roles
                ],
            )
        )
    attacks.append(
        Outline(Node("add_attack", ("attacks", len(attacks)), "add attack"), [])
    )

    judges = [
        Outline(
            Node(
                "model",
                ("evaluation", "judges", index),
                f"judge {index + 1}",
                _doc(JudgeSpec),
                JudgeSpec,
            ),
            [],
        )
        for index in range(len(draft.items(("evaluation", "judges"))))
    ]
    judges.append(Outline(Node("add_judge", ("evaluation", "judges"), "add judge"), []))

    def guardrail(side: str, text: str) -> Outline:
        return Outline(
            Node(
                "model",
                ("guardrails", side),
                side,
                text,
                GuardrailModelConfig,
                optional=True,
            ),
            [],
        )

    # Only the campaign's own sections: running it opens a screen of its own,
    # so the outline has one job.
    return [
        Outline(
            Node(
                "section",
                ("campaign",),
                "Overview",
                _doc(CampaignMetadata),
                CampaignMetadata,
            ),
            [],
        ),
        Outline(
            Node(
                "section",
                ("dataset",),
                "Dataset",
                _doc(CampaignDatasetSpec),
                CampaignDatasetSpec,
            ),
            [],
        ),
        Outline(
            Node(
                "section",
                ("target",),
                "Target",
                "The model or agent under test.",
                ModelConfig,
            ),
            [],
        ),
        Outline(
            Node(
                "group",
                ("guardrails",),
                "Guardrails",
                "Classifiers that defend the target. Both fail open.",
            ),
            [
                guardrail("before", "Checks each prompt; blocks an unsafe one."),
                guardrail("after", "Checks each reply; withholds an unsafe one."),
            ],
        ),
        Outline(
            Node(
                "group",
                ("attacks",),
                "Attacks",
                "Each attack turns every goal into requests to the target.",
            ),
            attacks,
        ),
        Outline(
            Node(
                "section",
                ("evaluation",),
                "Evaluation",
                _doc(EvaluationSpec),
                EvaluationSpec,
            ),
            judges,
        ),
        Outline(
            Node(
                "section",
                ("execution",),
                "Execution",
                _doc(ExecutionSpec),
                ExecutionSpec,
            ),
            [],
        ),
    ]


def issue_matches(root: Path, loc: Path) -> bool:
    return tuple(loc[: len(root)]) == tuple(root)


__all__ = ["Group", "Node", "Outline", "build_outline", "issue_matches"]
