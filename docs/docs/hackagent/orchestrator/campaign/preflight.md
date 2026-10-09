---
sidebar_label: preflight
title: hackagent.orchestrator.campaign.preflight
---

Check that a campaign&#x27;s models answer before it starts attacking.

Building a model validates its configuration but sends nothing, so a wrong
endpoint or a down server only shows up on the first real call — after the
run has started and partly recorded. When `execution.preflight` is on, the
target and every judge are pinged first, and an unreachable one stops the
run with a message naming it rather than a wall of mid-run errors.

Roles and embedders are not pinged: they sit behind the per-attack
completion callables, and their first use surfaces the same error. The
target and the panel are what every attack and every verdict depend on, so
they are the ones worth a check up front.

## PreflightError Objects

```python
class PreflightError(RuntimeError)
```

One or more of a campaign&#x27;s models could not be reached.

#### preflight

```python
async def preflight(resolved: ResolvedCampaign) -> None
```

Ping the target and judges; raise :class:`PreflightError` on any failure.

