"""Declarative dataset sources and selection settings."""

import random
from typing import Any, Literal, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hackagent.core.contracts import Goal
from hackagent.datasets import taxonomy
from hackagent.datasets.presets import PRESETS
from hackagent.datasets.registry import load_goals_and_extra_fields_from_config


class DatasetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DatasetSource(DatasetModel):
    """Where goals are loaded from: a built-in preset, a provider such as
    HuggingFace or a local file, or goals written inline."""

    type: Literal["preset", "provider", "inline"] = Field(
        default="preset",
        description=(
            "``preset`` loads a built-in benchmark named by ``dataset.preset``; "
            "``provider`` loads from ``provider`` with the fields below; ``inline``"
            " uses the ``goals`` listed here."
        ),
    )
    provider: Optional[str] = Field(
        default=None,
        description=(
            "For ``type: provider``: where to load from — ``huggingface``, ``file``"
            " (a local JSON/JSONL/CSV file) or ``url_json`` (a JSON file at a URL)."
        ),
    )
    path: Optional[str] = Field(
        default=None,
        description=(
            "For ``type: provider``: the HuggingFace dataset id (e.g. "
            "``walledai/AdvBench``), or the path of the local file."
        ),
    )
    name: Optional[str] = Field(
        default=None,
        description=(
            "For HuggingFace datasets with several configurations: which one to load."
        ),
    )
    split: Optional[str] = Field(
        default=None,
        description="For HuggingFace datasets: which split to read (``train``, ``test``…).",
    )
    goal_field: Optional[str] = Field(
        default=None,
        description="Name of the column or key that holds the goal text, e.g. ``prompt``.",
    )
    goals: tuple[str, ...] = Field(
        default=(),
        description="For ``type: inline``: the goals themselves, one string per goal.",
    )
    options: Mapping[str, Any] = Field(
        default_factory=dict,
        description=(
            "Any other provider setting, passed through unchanged (e.g. ``url`` for"
            " ``url_json``, ``trust_remote_code`` for HuggingFace)."
        ),
    )


class DatasetFilters(DatasetModel):
    """Keep only goals that match these filters."""

    categories: tuple[str, ...] = Field(
        default=(),
        description=(
            "Risk taxonomy categories or subcategories to keep, as a code (``E``, "
            "``E2``) or a name (``Cybersecurity Threats``). Matched on each goal's "
            "labels, so it needs ``dataset.classifier``."
        ),
    )

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_taxonomy_code(value) for value in values)


class DatasetSelection(DatasetModel):
    """Which of the loaded goals to run, and in what order."""

    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="Run at most this many goals. Leave unset to run them all.",
    )
    shuffle: bool = Field(
        default=False,
        description=(
            "Shuffle the goals before applying ``limit``, so a limited run is a "
            "random sample instead of the first goals in the file."
        ),
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for ``shuffle``, so the same sample is drawn every run.",
    )
    filters: DatasetFilters = Field(
        default_factory=DatasetFilters,
        description="Keep only goals that match these filters.",
    )


class DatasetSpec(DatasetModel):
    """Where goals come from and which of them to run."""

    preset: Optional[str] = Field(
        default=None,
        description=(
            "Name of a built-in benchmark, e.g. ``harmbench`` or ``advbench``. Used"
            " when ``source.type`` is ``preset`` (the default)."
        ),
    )
    source: DatasetSource = Field(
        default_factory=DatasetSource,
        description="Where to load goals from when not using a preset.",
    )
    selection: DatasetSelection = Field(
        default_factory=DatasetSelection,
        description="Which of the loaded goals to run.",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "DatasetSpec":
        if self.source.type == "preset":
            if not self.preset:
                raise ValueError("A preset dataset source requires 'preset'.")
            if self.preset not in PRESETS:
                known = ", ".join(sorted(PRESETS))
                raise ValueError(
                    f"Unknown dataset preset {self.preset!r}. Available: {known}."
                )
        elif self.source.type == "inline":
            if not self.source.goals:
                raise ValueError("An inline dataset source requires 'source.goals'.")
        elif not self.source.provider:
            raise ValueError("A provider dataset source requires 'source.provider'.")
        return self

    def to_provider_config(self) -> dict[str, Any]:
        """Translate a declarative source to the dataset provider contract.

        With a category filter the provider loads everything: which goals
        match is known only once they are labelled, and the selection is made
        from the matches by :func:`select_goals`.
        """
        config: dict[str, Any] = {}
        if not self.selection.filters.categories:
            config.update(
                limit=self.selection.limit,
                shuffle=self.selection.shuffle,
                seed=self.selection.seed,
            )
        if self.source.type == "preset":
            config["preset"] = self.preset
        else:
            config.update(
                {
                    "provider": self.source.provider,
                    "path": self.source.path,
                    "name": self.source.name,
                    "split": self.source.split,
                    "goal_field": self.source.goal_field,
                    **dict(self.source.options),
                }
            )
        return {key: value for key, value in config.items() if value is not None}


def load_goals(spec: DatasetSpec) -> list[Goal]:
    """Load and select the goals ``spec`` describes."""
    if spec.source.type == "inline":
        texts: list[str] = [text for text in spec.source.goals if text.strip()]
        extra_by_index: dict[int, dict[str, Any]] = {}
        selection = spec.selection
        # A category filter needs labels, applied later; shuffle/limit here.
        if not selection.filters.categories:
            if selection.shuffle:
                random.Random(selection.seed).shuffle(texts)
            if selection.limit:
                texts = texts[: selection.limit]
    else:
        texts, extra_by_index = load_goals_and_extra_fields_from_config(
            spec.to_provider_config()
        )
    if not texts:
        raise ValueError("The dataset selection produced no goals.")
    return [
        Goal(text=text, index=index, extra=dict(extra_by_index.get(index, {})))
        for index, text in enumerate(texts)
    ]


def _taxonomy_code(value: str) -> str:
    for resolve in (taxonomy.resolve_subcategory, taxonomy.resolve_category):
        try:
            return resolve(value)
        except ValueError:
            pass
    raise ValueError(f"Unknown taxonomy category or subcategory: {value!r}")


def _codes(goal: Goal) -> set[str]:
    try:
        subcategory = taxonomy.resolve_subcategory(goal.labels.get("subcategory", ""))
    except ValueError:
        return set()
    return {subcategory, taxonomy.category_of(subcategory)}


def select_goals(goals: Sequence[Goal], selection: DatasetSelection) -> list[Goal]:
    """Labelled goals matching ``selection``'s categories, shuffled and limited.

    Goals are renumbered from 0, so attempts and results index the selection.
    """
    wanted = set(selection.filters.categories)
    kept = [goal for goal in goals if wanted & _codes(goal)]
    if selection.shuffle:
        random.Random(selection.seed).shuffle(kept)
    kept = kept[: selection.limit]
    if not kept:
        raise ValueError(
            f"No goal is labelled with any of {sorted(wanted)}; "
            f"{len(goals)} were classified."
        )
    return [goal.model_copy(update={"index": index}) for index, goal in enumerate(kept)]
