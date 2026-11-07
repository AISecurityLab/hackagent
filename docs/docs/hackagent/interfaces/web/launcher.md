---
sidebar_label: launcher
title: hackagent.interfaces.web._launcher
---

Launch saved campaigns from the offline dashboard, in this process.

Offline there is no server to queue a run for a worker, and the machine
serving the dashboard is the one whose targets and models the campaign uses.
So a launch runs the campaign right here, in a background thread, recording
into the dashboard&#x27;s own store: the run pages follow it as its results land.

The thread lives as long as `hackagent web`; stopping the server ends any
run still going.

## LaunchRefused Objects

```python
class LaunchRefused(Exception)
```

The campaign cannot be launched; the message says why.

#### launch\_spec

```python
def launch_spec(campaign: Any, agent: Any,
                output_root: Path) -> Dict[str, Any]
```

The full spec a saved campaign runs with: the agent&#x27;s config as target,
local storage, and run files under `output_root`.

## LocalLauncher Objects

```python
class LocalLauncher()
```

Runs launched campaigns and cancels them on request.

#### launch

```python
def launch(campaign: Any) -> Any
```

Start `campaign` and return its campaign run once it is recorded.

Raises :class:`LaunchRefused` when the campaign does not validate or
its goals and models cannot be resolved; nothing is recorded then.

#### cancel

```python
def cancel(campaign_run_id: UUID) -> Optional[str]
```

Ask a run to stop at its next step; returns why it cannot, or None.

