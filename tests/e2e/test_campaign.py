# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CLI subprocess → real HTTP provider → judge → SQLite → results command."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from hackagent.storage.local import LocalBackend

pytestmark = pytest.mark.e2e


def cli(tmp_path, env, *args, expected_exit=0):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hackagent.interfaces.cli.main",
            "--config-file",
            str(tmp_path / "no-config.json"),
            "--backend",
            "local",
            *args,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    return result.stdout


def test_cli_campaign_round_trips_through_http_sqlite_and_results(
    tmp_path,
    isolated_campaign_env,
    campaign_values,
    completion_server,
):
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(campaign_values))
    output = cli(
        tmp_path, isolated_campaign_env, "campaign", "run", str(path), "--json"
    )
    assert '"event": "goal_finished"' in output
    rows = json.loads(next((tmp_path / "runs").glob("*/results.json")).read_text())
    assert [r["goal"] for r in rows] == ["Goal one", "Goal two"]
    assert all(r["response"] == "The target replied." for r in rows)
    assert len(completion_server.calls("target")) == 2
    assert len(completion_server.calls("judge")) == 2
    assert [
        r["body"]["messages"][-1]["content"] for r in completion_server.calls("target")
    ] == ["Goal one", "Goal two"]
    assert all(
        r["headers"]["authorization"] == "Bearer test-provider-canary"
        for r in completion_server.requests
    )

    store = LocalBackend(isolated_campaign_env["HACKAGENT_DB_PATH"])
    try:
        [campaign] = store.list_campaign_runs().items
        assert campaign.status == "COMPLETED"
        [run] = store.list_runs().items
        assert run.status == "COMPLETED"
        results = store.list_results(run_id=run.id).items
        assert {r.goal for r in results} == {"Goal one", "Goal two"}
        assert all(r.evaluation_status == "SUCCESSFUL_JAILBREAK" for r in results)
        assert all(store.list_traces(r.id) for r in results)
        shown = cli(
            tmp_path, isolated_campaign_env, "results", "show", str(results[0].id)
        )
        assert str(results[0].id) in shown
        assert "SUCCESSFUL_JAILBREAK" in shown
    finally:
        store.close()
    folder = next((tmp_path / "runs").iterdir())
    assert [
        json.loads(line) for line in (folder / "results.jsonl").read_text().splitlines()
    ] == rows
    assert "test-provider-canary" not in "".join(
        p.read_text() for p in folder.iterdir() if p.is_file()
    )


def test_cli_dry_run_sends_nothing(
    tmp_path, isolated_campaign_env, campaign_values, completion_server
):
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(campaign_values))
    cli(
        tmp_path,
        isolated_campaign_env,
        "campaign",
        "run",
        str(path),
        "--dry-run",
        "--json",
    )
    assert completion_server.requests == []
    assert not Path(isolated_campaign_env["HACKAGENT_DB_PATH"]).exists()


def test_cli_preflight_failure_records_the_model_error_without_an_attack(
    tmp_path,
    isolated_campaign_env,
    campaign_values,
    completion_server,
):
    from tests.support.campaigns import Reply

    campaign_values["execution"]["preflight"] = True
    completion_server.defaults["target"] = Reply("probe rejected", 400)
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(campaign_values))
    output = cli(
        tmp_path, isolated_campaign_env, "campaign", "run", str(path), expected_exit=1
    )
    assert "Preflight failed" in output and "target" in output
    assert len(completion_server.calls("target")) == 1
    assert len(completion_server.calls("judge")) == 1
    store = LocalBackend(isolated_campaign_env["HACKAGENT_DB_PATH"])
    try:
        [campaign] = store.list_campaign_runs().items
        assert campaign.status == "FAILED"
        assert "target" in campaign.run_notes
        assert store.list_runs().total == 0
    finally:
        store.close()
    assert not (tmp_path / "runs").exists()


def test_cli_retention_settings_apply_to_files_database_and_traces(
    tmp_path,
    isolated_campaign_env,
    campaign_values,
    completion_server,
):
    campaign_values["execution"]["output"].update(
        save_prompts=False, save_responses=False, save_traces=False
    )
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(campaign_values))
    cli(tmp_path, isolated_campaign_env, "campaign", "run", str(path), "--json")
    assert (
        len(completion_server.calls("target"))
        == len(completion_server.calls("judge"))
        == 2
    )
    folder = next((tmp_path / "runs").iterdir())
    rows = json.loads((folder / "results.json").read_text())
    assert len(rows) == 2
    assert all(
        not {
            "prompt",
            "messages",
            "response",
            "model_response",
            "decoded_response",
        }.intersection(row)
        for row in rows
    )
    assert not (folder / "traces.jsonl").exists()
    store = LocalBackend(isolated_campaign_env["HACKAGENT_DB_PATH"])
    try:
        [run] = store.list_runs().items
        results = store.list_results(run_id=run.id).items
        assert len(results) == 2
        assert all(
            not {
                "messages",
                "response",
                "decoded_response",
                "response_body",
            }.intersection(r.metadata)
            for r in results
        )
        assert all(store.list_traces(r.id) == [] for r in results)
        assert all(r.evaluation_status == "SUCCESSFUL_JAILBREAK" for r in results)
    finally:
        store.close()
    with sqlite3.connect(isolated_campaign_env["HACKAGENT_DB_PATH"]) as db:
        payloads = db.execute("SELECT request_payload_json FROM results").fetchall()
    assert [json.loads(row[0]) for row in payloads] == [{}, {}]
    assert (
        b"The target replied."
        not in Path(isolated_campaign_env["HACKAGENT_DB_PATH"]).read_bytes()
    )
