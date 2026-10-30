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

import json
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Optional

from hackagent.core.async_utils import run_coroutine_blocking
from hackagent.core.contracts import LabelledSample
from hackagent.core.logging import get_logger
from hackagent.datasets.calibration import CalibrationSpec, load_calibration
from hackagent.evaluation.audit import (
    PANEL,
    AuditReport,
    EnsembleReport,
    RobustnessSpec,
    audit_panel,
)
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
    """Synchronous form of :func:`aaudit_configured_panel`.

    Safe to call while an event loop is already running.
    """
    return run_coroutine_blocking(
        lambda: aaudit_configured_panel(panel, spec, concurrency=concurrency, load=load)
    )


async def aaudit_configured_panel(
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
    report = await audit_panel(
        panel,
        samples,
        robustness=spec.robustness,
        concurrency=concurrency,
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


def _rate(value: Optional[float], width: int) -> str:
    """A rate, or a dash when the calibration sample could not measure it."""
    return f"{'-':>{width}}" if value is None else f"{value:>{width}.3f}"


def _wrapped(line: str, width: int = 78) -> list[str]:
    """One line, folded to the table's width, continuations indented under it."""
    indent = len(line) - len(line.lstrip())
    return textwrap.wrap(line, width=width, subsequent_indent=" " * (indent + 2)) or [
        line
    ]


def _ensemble_lines(ensemble: Optional[EnsembleReport]) -> list[str]:
    """Whether the panel earned its judges, in a line or four."""
    if ensemble is None or ensemble.worth_it is None:
        return []
    panel = ensemble.configured.metrics.youden_j or 0.0
    single = ensemble.best_single.metrics.youden_j or 0.0
    best = ensemble.best_rule
    name = ensemble.best_single.judges[0]

    if panel > single:
        standing = f"the panel is ahead by {panel - single:.3f}"
    elif panel < single:
        standing = f"the panel is behind by {single - panel:.3f}"
    else:
        standing = "the two are level"
    lines = [f"panel J={panel:.3f} against {name} alone at {single:.3f}: {standing}."]

    disagreement = ensemble.disagreement
    if disagreement is not None:
        split = disagreement.panel_right + disagreement.judge_right
        if not split:
            lines.append(
                f"  they never once disagreed, so the rest of the panel changed "
                f"no verdict {name} had not already reached."
            )
        else:
            lines.append(
                f"  {split} samples separate them, {disagreement.panel_right} to the "
                f"panel and {disagreement.judge_right} to {name}: "
                + (
                    f"too few to call either way, p={disagreement.p_value:.2f}."
                    if disagreement.p_value > 0.05
                    else f"a real difference, p={disagreement.p_value:.2f}."
                )
            )

    if (best.metrics.youden_j or 0.0) > max(panel, single) + 1e-9:
        lines.append(
            f"  {best.rule} of {', '.join(best.judges)} would reach "
            f"J={best.metrics.youden_j:.3f} here, but it was picked knowing the answers."
        )

    penalty = ensemble.correlation_penalty
    if penalty is not None and ensemble.independent_j is not None:
        if penalty > 0.01:
            lines.append(
                f"  judges that never erred together would reach "
                f"{ensemble.independent_j:.3f}; sharing blind spots costs {penalty:.3f}, "
                "and a judge unlike the others would win more of it back than a "
                "better one like them."
            )
        elif penalty < -0.01:
            lines.append(
                f"  judges erring independently would reach only "
                f"{ensemble.independent_j:.3f}: these cover each other's misses, which "
                "is the whole case for running a panel."
            )
        else:
            lines.append(
                f"  the judges err about independently, as the "
                f"{ensemble.independent_j:.3f} this predicts bears out."
            )
    return [folded for line in lines for folded in _wrapped(line)]


def format_report(report: AuditReport) -> str:
    """The report as a table, panel row last, for a terminal or a log."""
    # A bound judge is named ``kind:identifier``, which outgrows a fixed
    # column the moment a model id is long. Widen to the names in hand.
    name_width = max(24, *(len(row.judge) for row in report.judges))
    header = (
        f"{'judge':<{name_width}} {'prec':>6} {'recall':>7} {'f1':>6} {'acc':>6} "
        f"{'bal acc':>8} {'J':>6} {'flips':>6}"
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
            f"{row.judge:<{name_width}} {row.metrics.precision:>6.3f} "
            f"{row.metrics.recall:>7.3f} "
            f"{row.metrics.f1:>6.3f} {row.metrics.accuracy:>6.3f} "
            f"{_rate(row.metrics.balanced_accuracy, 8)} "
            f"{_rate(row.metrics.youden_j, 6)} {flips}"
        )
        if row.passed is False and row.robustness is not None:
            lines.append(
                f"{'':<{name_width}} ! flip rate above the "
                f"{row.robustness.max_flip_rate:.3f} limit"
            )
    panel = report.report_for(PANEL)
    if panel is not None and (panel.metrics.youden_j or 0) > 0:
        lines.append(
            f"J={panel.metrics.youden_j:.3f}: this panel reports "
            f"{panel.metrics.youden_j:.0%} of any true difference between targets."
        )
    sweep = report.threshold
    if sweep is not None and sweep.improvement > 0:
        lines.append(
            f"threshold {sweep.threshold:.1f} scores J={sweep.youden_j:.3f}; "
            f"{sweep.best_threshold:.1f} would score {sweep.best_youden_j:.3f} "
            "on these same samples."
        )
    lines.extend(_ensemble_lines(report.ensemble))
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
    "aaudit_configured_panel",
    "audit_configured_panel",
    "format_report",
    "read_report",
    "run_audit",
    "write_report",
]
