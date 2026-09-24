---
sidebar_label: run_report
title: hackagent.interfaces.tui.views.results.formatters.run_report
---

Run-level report header rendering for the results detail panel.

#### build\_run\_report\_header

```python
def build_run_report_header(run: Any, *, created: str, agent_display: str,
                            org_display: str, status_display: str,
                            status_icon: str, status_color: str,
                            run_results: list[Any], attack_type_display: str,
                            attack_config: dict) -> str
```

Build the Rich-markup report header shown above a run&#x27;s test results.

**Arguments**:

- `run` - The run object being displayed.
- `created` - Pre-formatted creation timestamp.
- `agent_display` - Resolved agent name.
- `org_display` - Resolved organisation name.
- `status_display` - Run status string.
- `status_icon` - Emoji matching *status_display*.
- `status_color` - Rich colour matching *status_display*.
- `run_results` - Results belonging to the run.
- `attack_type_display` - Resolved attack type, may be empty.
- `attack_config` - Attack configuration dict, may be empty.
  

**Returns**:

  Rich markup string for the header widget.

