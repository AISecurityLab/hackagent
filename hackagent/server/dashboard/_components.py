# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reusable NiceGUI UI component factories for the HackAgent dashboard."""

from __future__ import annotations

from nicegui import ui

# JavaScript expressions reused in Quasar slot templates
EVAL_COLOR_JS = (
    "props.row.evaluation_status?.toUpperCase().includes('SUCCESSFUL_JAILBREAK') ? 'negative'"
    " : (props.row.evaluation_status?.toUpperCase().includes('PASSED') ||"
    "    props.row.evaluation_status?.toUpperCase().includes('FAILED_JAILBREAK')) ? 'positive'"
    " : props.row.evaluation_status?.toUpperCase().includes('ERROR') ? 'warning'"
    " : 'grey-6'"
)

EVAL_LABEL_JS = (
    "props.row.evaluation_status?.toUpperCase().includes('SUCCESSFUL_JAILBREAK') ? 'Jailbreak'"
    " : props.row.evaluation_status?.toUpperCase().includes('PASSED_CRITERIA') ? 'Passed'"
    " : props.row.evaluation_status?.toUpperCase().includes('FAILED_JAILBREAK') ? 'Mitigated'"
    " : props.row.evaluation_status?.toUpperCase().includes('FAILED_CRITERIA') ? 'Failed'"
    " : props.row.evaluation_status?.toUpperCase().includes('ERROR') ? 'Error'"
    " : 'Pending'"
)


def make_run_table(on_row_click, pagination=None) -> ui.table:
    """Create a standard run table with custom slots and a row-click handler."""
    tbl = ui.table(
        columns=[
            {"name": "id", "label": "Run", "field": "id", "align": "left"},
            {"name": "status", "label": "Status", "field": "status", "align": "left"},
            {
                "name": "results",
                "label": "Results",
                "field": "total_results",
                "align": "left",
            },
            {
                "name": "asr",
                "label": "ASR",
                "field": "overall_asr",
                "align": "left",
            },
            {
                "name": "created_at",
                "label": "Created",
                "field": "created_at",
                "align": "left",
            },
        ],
        rows=[],
        row_key="id",
        pagination=pagination or {"rowsPerPage": 5},
    ).classes("w-full")

    tbl.add_slot(
        "body-cell-id",
        r"""
        <q-td :props="props" class="cursor-pointer"
              @click="$emit('rowClick', props.row)">
          <div class="font-mono text-xs font-medium">
            {{ props.row.id.slice(0,8) }}…
          </div>
          <div class="text-xs text-grey-6 truncate max-w-xs">
            {{ props.row.run_notes || '—' }}
          </div>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-status",
        r"""
        <q-td :props="props">
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
        "body-cell-results",
        r"""
        <q-td :props="props">
          <span class="tabular-nums font-medium">
            {{ props.row.total_results ?? 0 }}
          </span>
          <q-badge v-if="(props.row.successful_jailbreaks ?? 0) > 0"
                   color="negative" class="ml-2">
            ⚠ {{ props.row.successful_jailbreaks }}
          </q-badge>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-asr",
        r"""
        <q-td :props="props">
          <span class="tabular-nums font-medium">
            {{ props.row.overall_asr ?? '—' }}
          </span>
        </q-td>
        """,
    )
    tbl.add_slot(
        "body-cell-created_at",
        r"""
        <q-td :props="props">
          <span class="text-xs text-grey-6">{{ props.row._rel }}</span>
        </q-td>
        """,
    )
    tbl.on("rowClick", lambda e, cb=on_row_click: cb(e.args))
    return tbl
