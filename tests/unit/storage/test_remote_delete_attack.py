# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Deleting an attack on the platform deletes every one of its runs."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from hackagent.storage.remote import RemoteBackend


def test_delete_attack_rereads_the_first_page_as_runs_go():
    runs = [SimpleNamespace(id=uuid4()) for _ in range(250)]
    pages_read = []

    def list_runs(*, attack_id, page, page_size):
        pages_read.append(page)
        start = (page - 1) * page_size
        return SimpleNamespace(items=runs[start : start + page_size])

    def delete_run(run_id):
        runs[:] = [run for run in runs if run.id != run_id]

    backend = RemoteBackend.__new__(RemoteBackend)
    backend._client = object()
    backend.list_runs = list_runs
    backend.delete_run = delete_run
    with patch("hackagent.storage.remote.attack_destroy.sync_detailed") as destroy:
        backend.delete_attack(uuid4())

    assert runs == []
    assert set(pages_read) == {1}
    destroy.assert_called_once()
