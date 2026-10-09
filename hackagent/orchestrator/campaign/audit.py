# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Measure a campaign's judges before trusting what they report.

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
:mod:`hackagent.datasets.calibration`'s job and scoring the panel is
:mod:`hackagent.evaluation.audit`'s, and those packages may not import
each other.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Optional

from hackagent.core.contracts import LabelledSample
from hackagent.core.logging import get_logger
from hackagent.datasets.calibration import CalibrationSpec, load_calibration
from hackagent.evaluation.audit import AuditReport, RobustnessSpec, audit_panel
from hackagent.evaluation.panel import Panel
from hackagent.models import build_model
from hackagent.orchestrator.campaign.loader import load_campaign
from hackagent.orchestrator.campaign.resolve import ModelBuilder, build_panel
from hackagent.orchestrator.campaign.spec import AuditSpec, CampaignSpec

logger = get_logger(__name__)

CalibrationLoader = Callable[[CalibrationSpec], list[LabelledSample]]


class AuditFailed(RuntimeError):
    """A judge changed its mind too often and the campaign said to stop.

    ``report`` is the full audit, so a caller can show what failed rather
    than only that something did.
    """

    def __init__(self, report: AuditReport) -> None:
        failed = "; ".join(
            f"{row.judge} flipped {row.robustness.any_wrapper_flip_rate:.1%} "
            f"of its verdicts (limit {row.robustness.max_flip_rate:.1%})"
            for row in report.judges
            if row.passed is False and row.robustness is not None
        )
        super().__init__(f"The judge panel failed its audit: {failed}.")
        self.report = report


def audit_configured_panel(
    panel: Optional[Panel],
    spec: AuditSpec,
    *,
    concurrency: int = 1,
    load: CalibrationLoader = load_calibration,
) -> Optional[AuditReport]:
    """Run the audit a campaign configured. ``None`` when it configured none.

    Raises :class:`AuditFailed` when a judge fails its robustness check
    and ``on_failure`` is ``stop``. Accuracy is reported, never gated:
    what counts as enough depends on what the panel is for.
    """
    if not spec.enabled:
        return None
    if panel is None:
        raise ValueError(
            "This campaign configures no judges, so there is none to audit."
        )

    samples = load(spec.dataset)
    passes = 1 + (len(spec.robustness.resolve()) if spec.robustness.enabled else 0)
    logger.info(
        "audit | %d samples x %d judges x %d pass(es) before the first attack",
        len(samples),
        len(panel.judges),
        passes,
    )
    report = asyncio.run(
        audit_panel(
            panel,
            samples,
            robustness=spec.robustness,
            concurrency=concurrency,
        )
    )
    _log(report)
    if report.passed is False and spec.on_failure == "stop":
        raise AuditFailed(report)
    return report


def run_audit(
    source: str | Path | Mapping[str, Any] | CampaignSpec,
    *,
    calibration: Optional[CalibrationSpec] = None,
    robustness: Optional[RobustnessSpec] = None,
    on_failure: Optional[str] = None,
    report_path: Optional[str | Path] = None,
    build: ModelBuilder = build_model,
    load: CalibrationLoader = load_calibration,
) -> AuditReport:
    """Audit the panel ``source`` configures, without running the campaign.

    The campaign's own ``evaluation.audit`` block supplies the settings;
    each argument here overrides it. Asking for an audit runs one, whether
    or not the file enabled it.
    """
    spec = source if isinstance(source, CampaignSpec) else load_campaign(source)
    configured = spec.evaluation.audit
    panel = build_panel(spec.evaluation, build, retries=spec.execution.retries.judges)
    report = audit_configured_panel(
        panel,
        configured.model_copy(
            update={
                "enabled": True,
                "dataset": calibration or configured.dataset,
                "robustness": robustness or configured.robustness,
                "on_failure": on_failure or configured.on_failure,
            }
        ),
        concurrency=spec.execution.concurrency.judge,
        load=load,
    )
    assert report is not None  # enabled above
    if report_path is not None:
        write_report(report, report_path)
    return report


def write_report(report: AuditReport, path: str | Path) -> Path:
    """Write the full report as JSON, creating its directory."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info("audit | report written to %s", destination)
    return destination


def read_report(path: str | Path) -> AuditReport:
    """Load a report written by :func:`write_report`."""
    return AuditReport.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def format_report(report: AuditReport) -> str:
    """The report as a table, panel row last, for a terminal or a log."""
    header = (
        f"{'judge':<24} {'prec':>6} {'recall':>7} {'f1':>6} {'acc':>6} {'flips':>6}"
    )
    lines = [
        f"{report.samples} samples ({report.contextual_samples} with context)",
        header,
        "-" * len(header),
    ]
    for row in report.judges:
        flips = (
            f"{row.robustness.any_wrapper_flip_rate:>6.3f}"
            if row.robustness is not None
            else f"{'-':>6}"
        )
        lines.append(
            f"{row.judge:<24} {row.metrics.precision:>6.3f} {row.metrics.recall:>7.3f} "
            f"{row.metrics.f1:>6.3f} {row.metrics.accuracy:>6.3f} {flips}"
        )
        if row.passed is False and row.robustness is not None:
            lines.append(
                f"{'':<24} ! flip rate above the {row.robustness.max_flip_rate:.3f} limit"
            )
    lines.append({True: "passed", False: "FAILED", None: "not graded"}[report.passed])
    return "\n".join(lines)


def _log(report: AuditReport) -> None:
    for row in report.judges:
        logger.info(
            "audit | %-24s precision=%.3f recall=%.3f f1=%.3f | %s",
            row.judge,
            row.metrics.precision,
            row.metrics.recall,
            row.metrics.f1,
            {True: "passed", False: "FAILED", None: "not graded"}[row.passed],
        )


__all__ = [
    "AuditFailed",
    "CalibrationLoader",
    "audit_configured_panel",
    "format_report",
    "read_report",
    "run_audit",
    "write_report",
]
