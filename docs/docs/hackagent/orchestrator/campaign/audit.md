---
sidebar_label: audit
title: hackagent.orchestrator.campaign.audit
---

Measure a campaign&#x27;s judges before trusting what they report.

A campaign whose panel misses half the jailbreaks still reports a
reassuring success rate, and nothing in the run itself will say so. An
audit judges exchanges people have already labelled and reports what the
panel got right, what it invented, and what it missed.

It is configured in the campaign file, under the panel it measures::

    evaluation:
      judges: [...]
      audit:
        enabled: true
        on_failure: stop

A run then audits before it attacks, because a report that arrives after
the calls are spent cannot stop anything. :func:`run_audit` does the same
thing on its own, for tuning a panel without spending a run.

The two halves meet here and nowhere lower: loading labelled samples is
:mod:`hackagent.datasets.calibration`&#x27;s job and scoring the panel is
:mod:`hackagent.evaluation.audit`&#x27;s, and those packages may not import
each other.

## AuditFailed Objects

```python
class AuditFailed(RuntimeError)
```

A judge changed its mind too often and the campaign said to stop.

`report` is the full audit, so a caller can show what failed rather
than only that something did.

#### audit\_configured\_panel

```python
def audit_configured_panel(
        panel: Optional[Panel],
        spec: AuditSpec,
        *,
        concurrency: int = 1,
        load: CalibrationLoader = load_calibration) -> Optional[AuditReport]
```

Run the audit a campaign configured. `None` when it configured none.

Raises :class:`AuditFailed` when a judge fails its robustness check
and `on_failure` is `stop`. Accuracy is reported, never gated:
what counts as enough depends on what the panel is for.

#### run\_audit

```python
def run_audit(source: str | Path | Mapping[str, Any] | CampaignSpec,
              *,
              calibration: Optional[CalibrationSpec] = None,
              robustness: Optional[RobustnessSpec] = None,
              on_failure: Optional[str] = None,
              report_path: Optional[str | Path] = None,
              build: ModelBuilder = build_model,
              load: CalibrationLoader = load_calibration) -> AuditReport
```

Audit the panel `source` configures, without running the campaign.

The campaign&#x27;s own `evaluation.audit` block supplies the settings;
each argument here overrides it. Asking for an audit runs one, whether
or not the file enabled it.

#### write\_report

```python
def write_report(report: AuditReport, path: str | Path) -> Path
```

Write the full report as JSON, creating its directory.

#### read\_report

```python
def read_report(path: str | Path) -> AuditReport
```

Load a report written by :func:`write_report`.

#### format\_report

```python
def format_report(report: AuditReport) -> str
```

The report as a table, panel row last, for a terminal or a log.

