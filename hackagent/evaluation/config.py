"""Bind legacy judge specs to models as a :class:`Panel`."""

from typing import Callable, Optional, Sequence

from hackagent.core.contracts import JudgeSpec as RuntimeJudgeSpec
from hackagent.evaluation.panel import AGGREGATIONS, ModelJudge, Panel
from hackagent.core.contracts.protocols import CompletionModel


DEFAULT_JUDGE_AGGREGATION = "majority"


def build_panel(
    specs: Sequence[RuntimeJudgeSpec],
    models: Callable[[RuntimeJudgeSpec], CompletionModel],
    *,
    aggregation: str = DEFAULT_JUDGE_AGGREGATION,
    threshold: float = 7.0,
) -> Optional[Panel]:
    """Bind configured judges to models, failing rather than shrinking the panel."""
    if not specs:
        return None
    if aggregation not in AGGREGATIONS:
        raise ValueError(
            f"Unknown judge_aggregation {aggregation!r}. "
            f"Use one of: {', '.join(AGGREGATIONS)}."
        )
    bound = []
    for spec in specs:
        try:
            llm = models(spec)
        except Exception as exc:
            label = spec.identifier
            raise ValueError(f"Judge {label!r} could not be connected: {exc}") from exc
        kind = str(spec.type or "harmbench")
        bound.append((kind, spec.identifier, llm, spec.system_prompt))
    kinds = [kind for kind, *_ in bound]
    names = [
        kind if kinds.count(kind) == 1 else f"{kind}:{identifier}"
        for kind, identifier, *_ in bound
    ]
    unique = [
        name
        if names[:index].count(name) == 0
        else f"{name}#{names[:index].count(name) + 1}"
        for index, name in enumerate(names)
    ]
    judges = [
        ModelJudge(
            kind, llm, name=name, system_prompt=system_prompt, threshold=threshold
        )
        for (kind, _identifier, llm, system_prompt), name in zip(bound, unique)
    ]
    return Panel(judges, aggregation=aggregation, threshold=threshold)
