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
from hackagent.datasets.intents import load_goals_from_intents_config
from hackagent.datasets.presets import PRESETS
from hackagent.datasets.registry import load_goals_and_extra_fields_from_config


class DatasetModel(BaseModel):
    """Base of the dataset config models: frozen, and unknown keys are rejected."""

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
        """Reject a preset name that is not built in, listing the known ones."""
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


class IntentSelection(DatasetModel):
    """One category of bundled OmniSafeBench goals."""

    category: str = Field(description="Risk category code or name, e.g. `E`.")
    subcategories: Optional[tuple[str, ...]] = Field(
        default=None,
        min_length=1,
        description="Subcategory codes or names; omit to include the whole category.",
    )
    samples_per_subcategory: int = Field(
        default=1,
        ge=1,
        strict=True,
        description="Take up to this many bundled goals from each subcategory.",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        """Use the canonical category code."""
        return taxonomy.resolve_category(value)

    @field_validator("subcategories")
    @classmethod
    def validate_subcategories(
        cls, values: Optional[tuple[str, ...]]
    ) -> Optional[tuple[str, ...]]:
        """Use unique canonical subcategory codes."""
        if values is None:
            return None
        codes = tuple(taxonomy.resolve_subcategory(value) for value in values)
        if len(set(codes)) != len(codes):
            raise ValueError("Subcategories must not repeat")
        return codes

    @model_validator(mode="after")
    def validate_parent(self) -> "IntentSelection":
        """Keep every subcategory under its actual category."""
        if any(
            taxonomy.category_of(code) != self.category
            for code in self.subcategories or ()
        ):
            raise ValueError("Every subcategory must belong to its selected category")
        return self


class IntentsSource(DatasetModel):
    """Prelabelled OmniSafeBench goals shipped with HackAgent; no download."""

    type: Literal["intents"] = Field(description="Load bundled OmniSafeBench goals.")
    selections: tuple[IntentSelection, ...] = Field(
        min_length=1, description="Categories and subcategories to include, in order."
    )

    @model_validator(mode="after")
    def validate_unique_categories(self) -> "IntentsSource":
        """Prevent overlapping entries from duplicating goals."""
        categories = [selection.category for selection in self.selections]
        if len(set(categories)) != len(categories):
            raise ValueError("Select each category only once")
        return self


#: Where goals come from. ``type`` picks the shape, so only the fields that
#: belong to that shape exist — a preset source has no ``goals``, an inline one
#: has no ``split``.
DatasetSource = Annotated[
    Union[PresetSource, InlineSource, ProviderSource, IntentsSource],
    Field(discriminator="type"),
]


class DatasetFilters(DatasetModel):
    """Keep only goals that match these filters."""

    categories: tuple[str, ...] = Field(
        default=(),
        description=(
            "Risk taxonomy categories or subcategories to keep, as a code (`E`, "
            "`E2`) or a name (`Cybersecurity Threats`). Matched on each goal's "
            "labels. Bundled intents already have labels; other sources need `dataset.classifier`."
        ),
    )

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalise each category to its taxonomy code.

        Raises:
            ValueError: When a value names no taxonomy category or subcategory.
        """
        return tuple(_taxonomy_code(value) for value in values)


class DatasetSelection(DatasetModel):
    """Which of the loaded goals to run, and in what order."""

    start: int = Field(
        default=0,
        ge=0,
        description="Zero-based start of the goal range, inclusive. Applied after category filters and before shuffle and limit.",
    )
    end: Optional[int] = Field(
        default=None,
        ge=1,
        description="Zero-based end of the goal range, exclusive. Leave unset to include the remaining goals.",
    )

    @model_validator(mode="after")
    def validate_range(self) -> "DatasetSelection":
        """Reject reversed or empty ranges."""
        if self.end is not None and self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self

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
        if "selections" in source:
            return "intents"
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
        if (
            not self.selection.filters.categories
            and self.selection.start == 0
            and self.selection.end is None
        ):
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
    if isinstance(spec.source, IntentsSource):
        texts, labels = load_goals_from_intents_config(
            [
                entry.model_dump(mode="json", exclude_none=True)
                for entry in spec.source.selections
            ]
        )
        goals = [
            Goal(text=text, index=index, labels=labels[index])
            for index, text in enumerate(texts)
        ]
        selection = spec.selection
        # Label-based filters and their range are applied by the campaign runner.
        if selection.filters.categories:
            return goals
        goals = goals[selection.start : selection.end]
        if selection.shuffle:
            random.Random(selection.seed).shuffle(goals)
        goals = goals[: selection.limit]
        if not goals:
            raise ValueError("The dataset selection produced no goals.")
        return [
            goal.model_copy(update={"index": index}) for index, goal in enumerate(goals)
        ]
    if isinstance(spec.source, InlineSource):
        texts: list[str] = [text for text in spec.source.goals if text.strip()]
        extra_by_index: dict[int, dict[str, Any]] = {}
        selection = spec.selection
        # A category filter needs labels, applied later; shuffle/limit here.
        if not selection.filters.categories:
            texts = texts[selection.start : selection.end]
            if selection.shuffle:
                random.Random(selection.seed).shuffle(texts)
            if selection.limit:
                texts = texts[: selection.limit]
    else:
        texts, extra_by_index = load_goals_and_extra_fields_from_config(
            spec.to_provider_config()
        )
        selection = spec.selection
        if not selection.filters.categories and (
            selection.start != 0 or selection.end is not None
        ):
            indices = list(range(len(texts)))[selection.start : selection.end]
            if selection.shuffle:
                random.Random(selection.seed).shuffle(indices)
            indices = indices[: selection.limit]
            texts = [texts[index] for index in indices]
            extra_by_index = {
                new: dict(extra_by_index.get(old, {}))
                for new, old in enumerate(indices)
            }
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
        pass
    else:
        return {subcategory, taxonomy.category_of(subcategory)}
    # Placed in a category with an unspecified subcategory: only it matches.
    try:
        return {taxonomy.resolve_category(goal.labels.get("category", ""))}
    except ValueError:
        return set()


def select_goals(goals: Sequence[Goal], selection: DatasetSelection) -> list[Goal]:
    """Labelled goals matching ``selection``'s categories, shuffled and limited.

    Goals are renumbered from 0, so attempts and results index the selection.
    """
    wanted = set(selection.filters.categories)
    matching = [goal for goal in goals if wanted & _codes(goal)]
    if not matching:
        raise ValueError(
            f"No goal is labelled with any of {sorted(wanted)}; "
            f"{len(goals)} were classified."
        )
    kept = matching[selection.start : selection.end]
    if not kept:
        end = "the end" if selection.end is None else str(selection.end)
        raise ValueError(
            f"The selection range {selection.start} to {end} is past the "
            f"{len(matching)} goal(s) labelled with any of {sorted(wanted)}."
        )
    if selection.shuffle:
        random.Random(selection.seed).shuffle(kept)
    kept = kept[: selection.limit]
    return [goal.model_copy(update={"index": index}) for index, goal in enumerate(kept)]
