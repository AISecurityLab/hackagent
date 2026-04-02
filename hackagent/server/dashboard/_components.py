# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reusable NiceGUI UI component factories for the HackAgent dashboard."""

from __future__ import annotations

import time
from typing import Any

from nicegui import ui

# JavaScript expressions reused in Quasar slot templates
EVAL_COLOR_JS = (
    "(props.row.evaluation_notes || '').toLowerCase().includes('failed with exception') ? 'warning'"
    " : props.row.evaluation_status?.toUpperCase().includes('SUCCESSFUL_JAILBREAK') ? 'negative'"
    " : (props.row.evaluation_status?.toUpperCase().includes('PASSED_CRITERIA') ||"
    "    props.row.evaluation_status?.toUpperCase().includes('FAILED_JAILBREAK')) ? 'positive'"
    " : (props.row.evaluation_status?.toUpperCase().includes('FAILED_CRITERIA') ||"
    "    props.row.evaluation_status?.toUpperCase().includes('ERROR')) ? 'warning'"
    " : 'grey-6'"
)

EVAL_LABEL_JS = (
    "(props.row.evaluation_notes || '').toLowerCase().includes('failed with exception') ? 'Failed'"
    " : props.row.evaluation_status?.toUpperCase().includes('SUCCESSFUL_JAILBREAK') ? 'Jailbreak'"
    " : props.row.evaluation_status?.toUpperCase().includes('PASSED_CRITERIA') ? 'Mitigated'"
    " : props.row.evaluation_status?.toUpperCase().includes('FAILED_JAILBREAK') ? 'Mitigated'"
    " : (props.row.evaluation_status?.toUpperCase().includes('FAILED_CRITERIA') ||"
    "    props.row.evaluation_status?.toUpperCase().includes('ERROR')) ? 'Failed'"
    " : 'Pending'"
)


def make_run_table(
    on_row_click,
    pagination=None,
    include_agent: bool = False,
    include_progressive_run: bool = False,
    include_results: bool = True,
    include_goal_latency_avg: bool = False,
    selection: str | None = None,
    on_select=None,
) -> ui.table:
    """Create a standard run table with custom slots and a row-click handler."""
    run_label = "Run #" if include_progressive_run else "Run"
    run_field = "run_progress" if include_progressive_run else "id"

    columns = [
        {
            "name": "id",
            "label": run_label,
            "field": run_field,
            "align": "left",
            "sortable": True,
        },
    ]
    if include_agent:
        columns.append(
            {
                "name": "agent_name",
                "label": "Agent",
                "field": "agent_name",
                "align": "left",
                "sortable": True,
            }
        )
    columns.append(
        {
            "name": "attack_type",
            "label": "Attack",
            "field": "attack_type",
            "align": "left",
            "sortable": True,
        }
    )
    columns.extend(
        [
            {
                "name": "status",
                "label": "Status",
                "field": "status",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "latency",
                "label": "Latency",
                "field": "_latency_s",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "created_at",
                "label": "Timestamp",
                "field": "created_at",
                "align": "left",
                "sortable": True,
            },
        ]
    )
    if include_goal_latency_avg:
        columns.insert(
            len(columns) - 1,
            {
                "name": "goal_latency_avg",
                "label": "Per-Goal Latency (AVG)",
                "field": "_goal_latency_avg_s",
                "align": "left",
                "sortable": True,
            },
        )
    if include_results:
        columns.insert(
            len(columns) - 1,
            {
                "name": "results",
                "label": "Results",
                "field": "total_results",
                "align": "left",
                "sortable": True,
            },
        )

    tbl = ui.table(
        columns=columns,
        rows=[],
        row_key="id",
        pagination=pagination or {"rowsPerPage": 5},
        selection=selection,
    ).classes("w-full")

    tbl.add_slot(
        "body-cell-id",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
                    <div class="font-mono text-sm font-medium">
                        {{ props.row.run_progress ?? props.row.id.slice(0,8) + '…' }}
                    </div>
                    <div v-if="!(props.row.run_progress)" class="text-xs text-grey-6 truncate max-w-xs">
                        {{ props.row.run_notes || '—' }}
                    </div>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-attack_type",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <q-badge color="orange" :label="props.row.attack_type || '—'" />
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-agent_name",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <span class="text-sm">{{ props.row.agent_name || '—' }}</span>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-status",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <q-badge
            :color="props.row.status === 'COMPLETED' ? 'positive'
                  : props.row.status === 'RUNNING'   ? 'info'
                  : props.row.status === 'FAILED'    ? 'negative'
                  : 'warning'"
            :label="props.row.status" />
          <q-spinner v-if="props.row.status === 'RUNNING'"
                     color="info" size="xs" class="ml-2" />
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-latency",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <span class="tabular-nums text-sm">{{ props.row._latency || '—' }}</span>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-goal_latency_avg",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <span class="tabular-nums text-sm">{{ props.row._goal_latency_avg || '—' }}</span>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-results",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <span class="tabular-nums font-medium">
            {{ props.row.total_results ?? 0 }}
          </span>
          <q-badge v-if="(props.row.successful_jailbreaks ?? 0) > 0"
                   color="negative" class="ml-2">
                        jailbreaks: {{ props.row.successful_jailbreaks }}
                    </q-badge>
                    <q-badge v-if="(props.row.failed_attacks ?? 0) > 0"
                                     color="positive" class="ml-2">
                        failed attacks: {{ props.row.failed_attacks }}
          </q-badge>
                    <q-badge
                        v-if="((props.row.successful_jailbreaks ?? 0) + (props.row.failed_attacks ?? 0)) > 0"
                        color="info"
                        class="ml-2"
                    >
                        ASR:
                        {{ (((props.row.successful_jailbreaks ?? 0) * 100) / ((props.row.successful_jailbreaks ?? 0) + (props.row.failed_attacks ?? 0))).toFixed(1) }}%
                    </q-badge>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-created_at",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <div class="text-sm">{{ props.row._rel }}</div>
          <div class="text-xs text-grey-6">{{ props.row._date || '—' }}</div>
        </q-td>
        """,
    )

    def _extract_row(payload: Any) -> dict | None:
        """Normalize NiceGUI/Quasar click payloads to a run row dictionary."""
        if isinstance(payload, dict):
            if "id" in payload:
                return payload
            row = payload.get("row")
            if isinstance(row, dict):
                return row
            return None

        if isinstance(payload, (list, tuple)):
            for item in payload:
                row = _extract_row(item)
                if row is not None:
                    return row
        return None

    _last_click_row_id: str | None = None
    _last_click_ts: float = 0.0

    def _handle_row_click(e, cb=on_row_click) -> None:
        nonlocal _last_click_row_id, _last_click_ts
        row = _extract_row(e.args)
        if row is not None:
            row_id = str(row.get("id", ""))
            now = time.monotonic()
            # Quasar may fire both custom `rowClick` and native `row-click` for one
            # user action; collapse near-simultaneous duplicates.
            if (
                row_id
                and row_id == _last_click_row_id
                and (now - _last_click_ts) < 0.25
            ):
                return
            _last_click_row_id = row_id
            _last_click_ts = now
            cb(row)

    tbl.on("rowClick", _handle_row_click)
    # Also handle native Quasar row-click (fires as 'row-click' in kebab-case)
    tbl.on("row-click", _handle_row_click)
    if on_select is not None:
        tbl.on("selection", lambda e, cb=on_select: cb(e))
    return tbl
