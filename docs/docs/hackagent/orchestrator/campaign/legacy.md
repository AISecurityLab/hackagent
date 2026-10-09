---
sidebar_label: legacy
title: hackagent.orchestrator.campaign.legacy
---

Run an attack through campaigns from the `hack` call signature.

`hack` takes a flat `attack_config` dict and the connected target it was
called on; a campaign takes a :class:`~.spec.CampaignSpec` and builds its own
models. This module is the adapter between the two, translating the flat
config into a spec and reusing the already-connected target and role models.

It is a supported, first-class path, not a temporary shim: the quick-start
SDK surface (:meth:`~hackagent.client.Target.hack` and
:meth:`~hackagent.client.Target.hack_chain`), the example scripts, and the
flag-based CLI commands (`scan`, `claude`, `codex`, `attack`) all run
through it, while `hackagent campaign` and :func:`~.runner.run_campaign`
serve the full declarative `campaign.yaml` workflow. The two are peers —
one ergonomic, one declarative — over the same campaign runner.

Nothing about how models connect changes here. The target is the one `hack`
already connected, guardrails and all, and every role and judge is built from
its config dict through the same factory as a declarative campaign uses.

#### ROLE\_ALIASES

Role names that differ between a legacy config and the attack&#x27;s params.

#### runs\_as\_campaign

```python
def runs_as_campaign(attack_type: Optional[str]) -> bool
```

Whether this technique has moved to the campaign runner.

#### run\_as\_campaign

```python
def run_as_campaign(target: Any,
                    attack_config: Mapping[str, Any],
                    *,
                    run_config_override: Optional[Mapping[str, Any]] = None,
                    on_event: Optional[Any] = None) -> List[Dict[str, Any]]
```

Run one migrated attack and return rows in the shape `hack` returns.

#### run\_chain\_as\_campaign

```python
def run_chain_as_campaign(target: Any,
                          attacks: Sequence[Mapping[str, Any]],
                          *,
                          goals: Optional[Sequence[Any]] = None,
                          run_config_override: Optional[Mapping[str,
                                                                Any]] = None,
                          on_event: Optional[Any] = None,
                          escalate: bool = True) -> List[Dict[str, Any]]
```

Run a chain of migrated attacks as one escalating campaign.

Every step becomes an attack in a single :class:`CampaignSpec` sharing
one goal pool. With `escalate` on, the runner drops a goal once a step
jailbreaks it, so later steps only face the goals still standing — the
fallback ladder `hack_chain` has always run, now native to the
campaign. The rows come back in the shape `hack_chain` returns, each
tagged with its `chain_step` and `chain_attack_type`.

#### rows\_from

```python
def rows_from(result: CampaignResult) -> List[Dict[str, Any]]
```

Campaign attempts in the row shape `hack` has always returned.

#### chain\_rows\_from

```python
def chain_rows_from(result: CampaignResult, order: Sequence[str],
                    escalate: bool) -> List[Dict[str, Any]]
```

Chain rows in the shape `hack_chain` has always returned.

Each row carries `chain_step` (the attack&#x27;s position in the chain) and
`chain_attack_type` (its technique). With `escalate` on the chain is
a fallback ladder, so a goal keeps only the rows of the last step that
ran it — the step that jailbroke it, or the final step if nothing did —
matching the legacy `final_rows_by_goal` overwrite. Without escalation
every step&#x27;s rows are kept for every goal.

