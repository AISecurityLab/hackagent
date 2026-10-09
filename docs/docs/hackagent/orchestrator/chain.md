---
sidebar_label: chain
title: hackagent.orchestrator.chain
---

The escalating jailbreak chain.

`hack_chain` runs a sequence of attacks against one shared pool of goals.
By default it escalates: a goal a step jailbreaks is dropped before the next
step runs, so later techniques only face the goals still standing. The whole
chain is one campaign — :func:`~hackagent.orchestrator.campaign.legacy.run_chain_as_campaign`
builds the :class:`CampaignSpec` and the runner&#x27;s `escalate` mode does the
dropping. The CLI quick scan uses this instead of reimplementing the ladder.

#### hack\_chain

```python
def hack_chain(agent: Any,
               attacks: Optional[list] = None,
               goals: Optional[list] = None,
               run_config_override: Optional[Dict[str, Any]] = None,
               fail_on_run_error: bool = True,
               escalate_only_mitigated: bool = True,
               on_event: Optional[Any] = None,
               _tui_event_bus: Optional[Any] = None) -> list
```

Run `attacks` in order against a shared pool of goals.

`attacks` defaults to the jailbreak profile&#x27;s primary techniques. With
`escalate_only_mitigated` (the default) a goal is dropped from later
steps once a step jailbreaks it; otherwise every step runs against every
goal. `fail_on_run_error` stops the chain on a failing step instead of
carrying on. `on_event` is forwarded to the campaign. See
`Target.hack_chain`.

