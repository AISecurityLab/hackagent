---
sidebar_label: preflight
title: hackagent.orchestrator.campaign.preflight
---

Check that every model a campaign uses answers before it starts attacking.

Building a model validates its configuration but sends nothing, so a wrong
endpoint or a down server only shows up on the first real call — after the
run has started and partly recorded. When `execution.preflight` is on, every
model is checked first: the target, its guardrails, each attack&#x27;s roles and
embedders, the judges and the goal classifier. How a model is checked is its
own business (:meth:`Model.is_reachable`); preflight only decides which ones,
checks each distinct model once, and reports every failure together.

## Probe Objects

```python
@dataclass(frozen=True)
class Probe()
```

One distinct model, every place the campaign uses it, and its check.

## PreflightError Objects

```python
class PreflightError(RuntimeError)
```

One or more of a campaign&#x27;s models could not be reached.

#### campaign\_models

```python
def campaign_models(spec: CampaignSpec) -> Iterator[tuple[str, ModelConfig]]
```

Yield `(where, config)` for every model `spec` uses.

#### model\_probes

```python
def model_probes(spec: CampaignSpec, models: Mapping[int, Model],
                 embedders: Mapping[int, Any]) -> tuple[Probe, ...]
```

One probe per distinct model, from what resolution built.

`models` and `embedders` map `id(config)` to what was built from
that config. A model the campaign uses in several places is checked once.

#### preflight

```python
async def preflight(resolved: "ResolvedCampaign") -> None
```

Check every model; raise :class:`PreflightError` naming each failure.

