---
sidebar_label: quick
title: hackagent.interfaces.cli.commands.scan.quick
---

`run_quick_scan`: the canned jailbreak campaign behind `hackagent eval`.

#### run\_quick\_scan

```python
def run_quick_scan(ctx: click.Context, agent_name: str, agent_type: str,
                   endpoint: str, dataset_preset: Optional[str], limit: int,
                   judge_identifier: str, judge_type: str, timeout: int,
                   fail_fast: bool, dry_run: bool) -> None
```

Run the quick 3-attack security scan implementation.

