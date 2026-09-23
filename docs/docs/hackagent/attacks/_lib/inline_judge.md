---
sidebar_label: inline_judge
title: hackagent.attacks._lib.inline_judge
---

Adapters that expose generation-loop judge APIs over ``ports.Judge``.

Inline-judge techniques (BoN, PAP, tool_output_ipi, TAP) historically built
``InlineStepJudge`` / ``TapEvaluation`` from raw judge configs. On the Phase 4
seam they receive ``ctx.judge`` instead; these adapters keep the call sites
stable while routing every score through the Judge port.

## CtxJudgeAdapter Objects

```python
class CtxJudgeAdapter()
```

``InlineStepJudge``-compatible wrapper around :class:`~hackagent.attacks.ports.Judge`.

``is_jailbreak`` uses ``judge.score`` and the canonical 0--10 jailbreak
threshold from *config* (default 7.0).

## CtxTapEvaluator Objects

```python
class CtxTapEvaluator()
```

Minimal TAP evaluator surface backed by ``ctx.judge.score``.

Implements the methods ``TapSearch`` calls: ``evaluate_on_topic``,
``extract_scores``, and ``score_candidates``. On-topic checks default to
keeping every candidate when no separate on-topic judge is configured on
the Panel (Phase 6).

#### resolve\_inline\_step\_judge

```python
def resolve_inline_step_judge(config: Mapping[str, Any],
                              logger: logging.Logger,
                              *,
                              client: Any = None)
```

Return a step-judge for generation loops.

Prefers ``config[&quot;_judge&quot;]`` (a :class:`~hackagent.attacks.ports.Judge`)
when present; otherwise builds the legacy ``InlineStepJudge``.

#### postprocess\_inline\_results

```python
def postprocess_inline_results(input_data: List[Dict[str,
                                                     Any]], attack_label: str,
                               logger: logging.Logger) -> List[Dict[str, Any]]
```

Fill default success fields for rows already scored during generation.

Does not sync results or talk to storage. Server writes belong to tracking.

#### make\_postprocess\_execute

```python
def make_postprocess_execute(attack_label: str)
```

Pipeline step that only normalises inline-judge rows.

#### attach\_ctx\_judge

```python
def attach_ctx_judge(config: Dict[str, Any], ctx: Any) -> None
```

Expose ``ctx.judge`` on the mutable config dict for generation steps.

#### verdict\_from\_judge

```python
def verdict_from_judge(judge: Judge,
                       *,
                       goal: str,
                       prompt: str = "",
                       response: str = "")
```

Score via ``judge.evaluate`` and return ``(score, success, explanation)``.

Custom-loop techniques normalise through :class:`~hackagent.core.contracts.Verdict`.

