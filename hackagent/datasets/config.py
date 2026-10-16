"""Declarative dataset sources and selection settings."""

import random
from typing import Annotated, Any, Literal, Mapping, Optional, Sequence, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from hackagent.core.contracts import Goal
from hackagent.datasets import taxonomy
from hackagent.datasets.presets import PRESETS
from hackagent.datasets.registry import load_goals_and_extra_fields_from_config


class DatasetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PresetSource(DatasetModel):
    """A built-in benchmark, named by its preset."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    type: Literal["preset"] = Field(
        default="preset",
        description="Marks this as a preset source: a built-in benchmark.",
    )
    name: str = Field(
        # Files that spelled this `preset` still load. `type: preset` already
        # says what kind of source this is, so the field only says which one.
        validation_alias=AliasChoices("name", "preset"),
        description=(
            "Which built-in benchmark to load, e.g. `harmbench` or `advbench`. "
            "Run `hackagent datasets list` to see them all."
        ),
    )

    @field_validator("name")
    @classmethod
    def validate_preset(cls, value: str) -> str:
        if value not in PRESETS:
            known = ", ".join(sorted(PRESETS))
            raise ValueError(f"Unknown dataset preset {value!r}. Available: {known}.")
        return value


class InlineSource(DatasetModel):
    """Goals written straight into the campaign file."""

    type: Literal["inline"] = Field(
        description="Marks this as an inline source: goals written in the file."
    )
    goals: tuple[str, ...] = Field(
        min_length=1,
        description="The goals themselves, one string per goal.",
    )


class ProviderSource(DatasetModel):
    """Goals loaded from a dataset provider: HuggingFace, a file, or a URL."""

    type: Literal["provider"] = Field(
        description="Marks this as a provider source: loaded from HuggingFace, a file or a URL."
    )
    provider: str = Field(
        description=(
            "Where to load from: `huggingface`, `file` (a local JSON/JSONL/CSV "
            "file) or `url_json` (a JSON file at a URL)."
        ),
    )
    path: Optional[str] = Field(
        default=None,
        description=(
            "The HuggingFace dataset id (e.g. `walledai/AdvBench`), or the path "
            "of the local file."
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
        description="For HuggingFace datasets: which split to read (`train`, `test`…).",
    )
    goal_field: Optional[str] = Field(
        default=None,
        description="Name of the column or key that holds the goal text, e.g. `prompt`.",
    )
    options: Mapping[str, Any] = Field(
        default_factory=dict,
        description=(
            "Any other provider setting, passed through unchanged (e.g. `url` "
            "for `url_json`, `trust_remote_code` for HuggingFace)."
        ),
    )


#: Where goals come from. ``type`` picks the shape, so only the fields that
#: belong to that shape exist — a preset source has no ``goals``, an inline one
#: has no ``split``.
DatasetSource = Annotated[
    Union[PresetSource, InlineSource, ProviderSource],
    Field(discriminator="type"),
]


class DatasetFilters(DatasetModel):
    """Keep only goals that match these filters."""

    categories: tuple[str, ...] = Field(
        default=(),
        description=(
            "Risk taxonomy categories or subcategories to keep, as a code (`E`, "
            "`E2`) or a name (`Cybersecurity Threats`). Matched on each goal's "
            "labels, so it needs `dataset.classifier`."
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
            "Shuffle the goals before applying `limit`, so a limited run is a "
            "random sample instead of the first goals in the file."
        ),
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for `shuffle`, so the same sample is drawn every run.",
    )
    filters: DatasetFilters = Field(
        default_factory=DatasetFilters,
        description="Keep only goals that match these filters.",
    )


class DatasetSpec(DatasetModel):
    """Where goals come from and which of them to run."""

    source: DatasetSource = Field(
        default_factory=lambda: PresetSource(name="harmbench"),
        description="Where to load goals from.",
    )
    selection: DatasetSelection = Field(
        default_factory=DatasetSelection,
        description="Which of the loaded goals to run.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalise_source(cls, data: Any) -> Any:
        """Accept older and shorter spellings of the source.

        ``dataset.preset`` used to sit beside ``dataset.source``, so the two
        could disagree and every source carried every other source's fields;
        files written that way still load, with the preset moved inside.

        A source that omits ``type`` is also read rather than refused: the
        fields it does carry say which kind it is, and without that a document
        can only report that it cannot find the tag.
        """
        if not isinstance(data, Mapping):
            return data
        data = dict(data)
        source = data.get("source")
        source = dict(source) if isinstance(source, Mapping) else None

        preset = data.pop("preset", None)
        if preset is not None:
            source = source or {}
            if source.get("type", "preset") == "preset":
                source.setdefault("name", preset)
                source.setdefault("type", "preset")

        if source is not None and "type" not in source:
            source["type"] = cls._infer_source_type(source)
        if source is not None:
            data["source"] = source
        return data

    @staticmethod
    def _infer_source_type(source: Mapping[str, Any]) -> str:
        """Which kind of source the fields present describe."""
        if "goals" in source:
            return "inline"
        if "provider" in source:
            return "provider"
        return "preset"

    @property
    def preset(self) -> Optional[str]:
        """The preset this dataset loads, when it loads one."""
        return self.source.name if isinstance(self.source, PresetSource) else None

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
        source = self.source
        if isinstance(source, PresetSource):
            config["preset"] = source.name
        elif isinstance(source, ProviderSource):
            config.update(
                {
                    "provider": source.provider,
                    "path": source.path,
                    "name": source.name,
                    "split": source.split,
                    "goal_field": source.goal_field,
                    **dict(source.options),
                }
            )
        return {key: value for key, value in config.items() if value is not None}


def load_goals(spec: DatasetSpec) -> list[Goal]:
    """Load and select the goals ``spec`` describes."""
    if isinstance(spec.source, InlineSource):
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
