# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Executing a server-tracked run: claim, gateway, environment, heartbeat, finish."""

from __future__ import annotations

import asyncio
import os
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from hackagent.core.credentials import reference_name
from hackagent.models import ModelResponse, Reachability
from hackagent.orchestrator.campaign.gateway import GATEWAY_KEY_ENV
from hackagent.orchestrator.execution import AdoptedRunStore, execute
from hackagent.storage import remote
from hackagent.storage.remote import ClaimResult
from tests.fakes import RecordingStore
from tests.unit.campaign.fakes import FakeBuilder, ScriptedModel, campaign, goals, model

BASE_URL = "https://exec.example/api"
GATEWAY_KEY = "gateway-key-for-test"
GW = {"name": "gateway", "connection": {"provider": "hackagent", "type": "OPENAI"}}


class RecordingAdoptedStore(AdoptedRunStore):
    """The adopted store over an in-memory recorder instead of HTTP."""

    instances: list["RecordingAdoptedStore"] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory = RecordingStore()
        self.finished: list[tuple] = []
        self.finish_error: Exception | None = None
        for name in (
            "create_attack",
            "create_run",
            "update_run",
            "create_result",
            "update_result",
            "create_trace",
        ):
            setattr(self, name, getattr(self.memory, name))
        RecordingAdoptedStore.instances.append(self)

    def heartbeat_run(self, run_id):
        return False

    def finish_run(self, run_id, status, note=""):
        self.finished.append((run_id, status, note))
        if self.finish_error is not None:
            raise self.finish_error
        return None


class FakeHeartbeat:
    """Stands in for RunHeartbeat; a test trips its events."""

    instances: list["FakeHeartbeat"] = []

    def __init__(self, store, run_id, *, interval_s=15.0):
        self.cancel_requested = threading.Event()
        self.rejected = threading.Event()
        self.on_change = None
        FakeHeartbeat.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

    def trip(self, event):
        # The real heartbeat signals from its own thread.
        event.set()
        thread = threading.Thread(target=self.on_change)
        thread.start()
        thread.join()


@pytest.fixture(autouse=True)
def recording_store(monkeypatch):
    RecordingAdoptedStore.instances = []
    monkeypatch.setattr(execute, "AdoptedRunStore", RecordingAdoptedStore)


@pytest.fixture
def fake_heartbeat(monkeypatch):
    FakeHeartbeat.instances = []
    monkeypatch.setattr(execute, "RunHeartbeat", FakeHeartbeat)
    return FakeHeartbeat.instances


def stored_campaign(tmp_path, **sections):
    """A campaign as the server stores it: storage named but not addressed."""
    execution = {
        "output": {"directory": str(tmp_path), "formats": ["json"]},
        "storage": {"backend": "remote"},
        **sections.pop("execution", {}),
    }
    return campaign(execution=execution, **sections)


def run_detail(config):
    return {
        "id": str(uuid4()),
        "agent": str(uuid4()),
        "organization": str(uuid4()),
        "owner": 7,
        "status": "RUNNING",
        "run_config": {"_record_type": "campaign_run", "campaign_config": config},
    }


def models(target="a reply", judge="yes", **others):
    def scripted(value):
        return value if isinstance(value, ScriptedModel) else ScriptedModel(value)

    return {"target": scripted(target), "judge": scripted(judge), **others}


def execute_with(config, *, builder=None, texts=("goal one",), **kwargs):
    run = run_detail(config)
    claim = ClaimResult(run=run, run_token=None, env={})
    store = SimpleNamespace(client=MagicMock())
    outcome = execute.execute_run(
        store,
        run["id"],
        base_url=BASE_URL,
        gateway_key=GATEWAY_KEY,
        claimed_by="local:test",
        claim=claim,
        build=builder or FakeBuilder(models()),
        load=goals(*texts),
        **kwargs,
    )
    return outcome, RecordingAdoptedStore.instances[-1], run


class ProviderError(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider answered {status_code}")
        self.status_code = status_code


# --- outcomes ---------------------------------------------------------------


def test_completed_run_finishes_completed(tmp_path):
    outcome, store, run = execute_with(stored_campaign(tmp_path))

    assert outcome.note == ""
    assert outcome.status == "COMPLETED"
    assert outcome.result is not None
    assert outcome.result.campaign_run_id == run["id"]
    assert store.finished == [(store.run_id, "COMPLETED", "")]
    assert str(store.run_id) == run["id"]


def test_claims_the_run_when_no_claim_is_given(tmp_path):
    run = run_detail(stored_campaign(tmp_path))
    claims = []

    def claim_run(run_id, claimed_by):
        claims.append((run_id, claimed_by))
        return ClaimResult(run=run, run_token=None, env={})

    store = SimpleNamespace(client=MagicMock(), claim_run=claim_run)
    outcome = execute.execute_run(
        store,
        run["id"],
        base_url=BASE_URL,
        gateway_key=GATEWAY_KEY,
        claimed_by="local:test",
        build=FakeBuilder(models()),
        load=goals("goal one"),
    )

    assert claims == [(run["id"], "local:test")]
    assert outcome.status == "COMPLETED"


def test_cancel_request_finishes_cancelled(tmp_path, fake_heartbeat):
    def on_event(event, **payload):
        if event == "goal_finished":
            fake_heartbeat[-1].trip(fake_heartbeat[-1].cancel_requested)

    outcome, store, _ = execute_with(
        stored_campaign(tmp_path),
        texts=("one", "two", "three", "four"),
        on_event=on_event,
    )

    assert outcome.status == "CANCELLED"
    assert outcome.note == "Campaign cancelled"
    assert store.finished == [(store.run_id, "CANCELLED", "Campaign cancelled")]


def out_of_credits(_messages):
    return ModelResponse.failed(ProviderError(402))


PAP = {
    "name": "pap",
    "parameters": {"techniques": ["Logical Appeal", "Expert Endorsement"]},
}


def test_402_from_a_gateway_role_stops_the_run(tmp_path):
    attacker = ScriptedModel(out_of_credits)
    builder = FakeBuilder(models(gateway=attacker))

    outcome, store, _ = execute_with(
        stored_campaign(tmp_path, attacks=[{**PAP, "roles": {"attacker": GW}}]),
        builder=builder,
        texts=("one", "two", "three", "four"),
    )

    assert (outcome.status, outcome.note) == ("FAILED", "Out of credits")
    assert store.finished == [(store.run_id, "FAILED", "Out of credits")]
    # The first 402 trips the guard; nothing reaches the gateway after it.
    assert len(attacker.requests) == 1


def test_402_from_a_gateway_role_is_not_retried(tmp_path):
    from hackagent.models.retry import RetryingModel

    attacker = ScriptedModel(out_of_credits)
    fakes = FakeBuilder(models(gateway=attacker))

    def build(config, *, retries=0):
        model = fakes(config)
        return RetryingModel(model, retries) if retries else model

    outcome, _, _ = execute_with(
        stored_campaign(
            tmp_path,
            attacks=[{**PAP, "roles": {"attacker": GW}}],
            execution={"retries": {"roles": 2}},
        ),
        builder=build,
    )

    assert (outcome.status, outcome.note) == ("FAILED", "Out of credits")
    assert len(attacker.requests) == 1


def test_402_from_the_target_stays_an_attempt_error(tmp_path):
    target = ScriptedModel(out_of_credits)

    outcome, store, _ = execute_with(
        stored_campaign(tmp_path),
        builder=FakeBuilder(models(target=target)),
        texts=("one", "two"),
    )

    assert outcome.status == "COMPLETED"
    assert len(target.requests) == 2
    attempts = [a for attack in outcome.result.attacks for a in attack.attempts]
    assert attempts and all(a.error for a in attempts)
    assert store.finished == [(store.run_id, "COMPLETED", "")]


def test_402_at_preflight_on_a_gateway_judge(tmp_path):
    judge = ScriptedModel(out_of_credits)

    outcome, store, _ = execute_with(
        stored_campaign(
            tmp_path,
            evaluation={"judges": [{**GW, "scoring": {"type": "harmbench"}}]},
            execution={"preflight": True},
        ),
        builder=FakeBuilder(models(gateway=judge)),
    )

    assert (outcome.status, outcome.note) == ("FAILED", "Out of credits")
    assert store.finished == [(store.run_id, "FAILED", "Out of credits")]
    assert len(judge.requests) == 1
    assert store.memory.call_names().count("create_attack") == 0


def test_402_in_an_escaping_error_maps_to_out_of_credits(tmp_path):
    class OutOfCreditsModel(ScriptedModel):
        async def is_reachable(self) -> Reachability:
            try:
                raise ProviderError(402)
            except ProviderError:
                raise RuntimeError("the gateway refused the check") from None

    builder = FakeBuilder(models(judge=OutOfCreditsModel("yes")))
    outcome, store, _ = execute_with(
        stored_campaign(tmp_path, execution={"preflight": True}), builder=builder
    )

    assert outcome.status == "FAILED"
    assert outcome.note == "Out of credits"
    # The runner's own final status is held back, so the run ends once.
    assert store.finished == [(store.run_id, "FAILED", "Out of credits")]


def test_other_errors_become_the_note(tmp_path):
    class BrokenModel(ScriptedModel):
        async def is_reachable(self) -> Reachability:
            raise ValueError("x" * 600)

    builder = FakeBuilder(models(judge=BrokenModel("yes")))
    outcome, store, _ = execute_with(
        stored_campaign(tmp_path, execution={"preflight": True}), builder=builder
    )

    assert outcome.status == "FAILED"
    assert outcome.note.startswith("ValueError: xxx")
    assert len(outcome.note) == 500
    assert store.finished == [(store.run_id, "FAILED", outcome.note)]


def test_failure_before_the_campaign_starts_is_finished(tmp_path):
    def build(config, *, retries=0):
        raise ProviderError(402)

    outcome, store, _ = execute_with(stored_campaign(tmp_path), builder=build)

    assert (outcome.status, outcome.note) == ("FAILED", "Out of credits")
    assert store.finished == [(store.run_id, "FAILED", "Out of credits")]


def test_an_unreadable_campaign_is_finished_failed(tmp_path):
    config = stored_campaign(tmp_path)
    del config["target"]

    outcome, store, _ = execute_with(config)

    assert outcome.status == "FAILED"
    assert outcome.note.startswith("ValidationError: ")
    assert store.finished == [(store.run_id, "FAILED", outcome.note)]


def test_a_run_without_its_agent_is_finished_on_the_claiming_store(tmp_path):
    run = run_detail(stored_campaign(tmp_path))
    del run["agent"]
    finished = []
    store = SimpleNamespace(
        client=MagicMock(),
        finish_run=lambda run_id, status, note="": finished.append(
            (run_id, status, note)
        ),
    )

    outcome = execute.execute_run(
        store,
        run["id"],
        base_url=BASE_URL,
        gateway_key=GATEWAY_KEY,
        claimed_by="local:test",
        claim=ClaimResult(run=run, run_token=None, env={}),
    )

    assert (outcome.status, outcome.note) == ("FAILED", "KeyError: 'agent'")
    assert finished == [(run["id"], "FAILED", "KeyError: 'agent'")]


def test_a_refused_finish_does_not_escape(tmp_path, monkeypatch):
    original = RecordingAdoptedStore.__init__

    def refusing(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.finish_error = RuntimeError("finish_run returned 409")

    monkeypatch.setattr(RecordingAdoptedStore, "__init__", refusing)
    outcome, store, _ = execute_with(stored_campaign(tmp_path))

    assert outcome.status == "COMPLETED"
    assert len(store.finished) == 1


def test_rejected_heartbeat_returns_failed_without_finish(tmp_path, fake_heartbeat):
    def on_event(event, **payload):
        if event == "goal_finished":
            fake_heartbeat[-1].trip(fake_heartbeat[-1].rejected)

    outcome, store, _ = execute_with(
        stored_campaign(tmp_path),
        texts=("one", "two", "three", "four"),
        on_event=on_event,
    )

    assert outcome.status == "FAILED"
    assert outcome.note == "Your API key is no longer valid for this run"
    assert outcome.result is None
    assert store.finished == []


def test_interrupt_finishes_cancelled_then_passes_on(tmp_path):
    def on_event(event, **payload):
        if event == "goal_finished":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        execute_with(stored_campaign(tmp_path), on_event=on_event)

    store = RecordingAdoptedStore.instances[-1]
    assert store.finished == [(store.run_id, "CANCELLED", "Campaign cancelled")]


def test_interrupt_after_a_rejection_passes_on_without_finish(tmp_path, fake_heartbeat):
    def on_event(event, **payload):
        if event == "goal_finished":
            fake_heartbeat[-1].trip(fake_heartbeat[-1].rejected)
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        execute_with(stored_campaign(tmp_path), on_event=on_event)

    assert RecordingAdoptedStore.instances[-1].finished == []


# --- environment, agent, gateway ---------------------------------------------


def test_env_injected_and_restored(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_KEY", raising=False)
    monkeypatch.setenv(GATEWAY_KEY_ENV, "the-value-before")
    seen = {}

    def target_reply(_messages):
        seen["OPENAI_KEY"] = os.environ.get("OPENAI_KEY")
        seen[GATEWAY_KEY_ENV] = os.environ.get(GATEWAY_KEY_ENV)
        return "a reply"

    target = model("target")
    target["connection"]["api_key"] = "${OPENAI_KEY}"
    outcome, _, _ = execute_with(
        stored_campaign(tmp_path, target=target),
        builder=FakeBuilder(models(target=ScriptedModel(target_reply))),
        env={"OPENAI_KEY": "secret-for-test"},
    )

    assert outcome.status == "COMPLETED"
    assert seen == {"OPENAI_KEY": "secret-for-test", GATEWAY_KEY_ENV: GATEWAY_KEY}
    assert "OPENAI_KEY" not in os.environ
    assert os.environ[GATEWAY_KEY_ENV] == "the-value-before"


def test_env_restored_when_the_run_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_KEY", raising=False)
    monkeypatch.delenv(GATEWAY_KEY_ENV, raising=False)

    def build(config, *, retries=0):
        raise RuntimeError("no model")

    outcome, _, _ = execute_with(
        stored_campaign(tmp_path), builder=build, env={"OPENAI_KEY": "s"}
    )

    assert outcome.status == "FAILED"
    assert "OPENAI_KEY" not in os.environ
    assert GATEWAY_KEY_ENV not in os.environ


def test_agent_not_reregistered(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("an executor of a queued run must not list or create")

    monkeypatch.setattr(remote.agent_list, "sync_detailed", forbidden)
    monkeypatch.setattr(remote.agent_create, "sync_detailed", forbidden)
    monkeypatch.setattr(remote.organization_me_retrieve, "sync_detailed", forbidden)
    monkeypatch.setattr(remote.campaign_start_create, "sync_detailed", forbidden)

    outcome, store, run = execute_with(stored_campaign(tmp_path))

    assert outcome.status == "COMPLETED"
    attack = next(iter(store.memory.attacks.values()))
    assert str(attack.agent_id) == run["agent"]
    assert str(attack.organization) == run["organization"]
    child = next(iter(store.memory.runs.values()))
    assert str(child.campaign_run_id) == run["id"]


def test_gateway_bound_with_executor_base_url(tmp_path):
    built = []
    fakes = FakeBuilder(models(gateway=ScriptedModel("yes")))

    def build(config, *, retries=0):
        built.append(config)
        return fakes(config, retries=retries)

    judge = {**GW, "scoring": {"type": "harmbench"}}
    outcome, _, _ = execute_with(
        stored_campaign(
            tmp_path,
            attacks=[{"name": "baseline"}],
            evaluation={"judges": [judge]},
        ),
        builder=build,
    )

    assert outcome.status == "COMPLETED"
    gateway = next(c for c in built if c.name == "gateway")
    assert gateway.connection.endpoint == "https://exec.example/api/v1"
    assert reference_name(gateway.connection.api_key) == GATEWAY_KEY_ENV


# --- execute_spec and remote campaigns --------------------------------------

STORAGE_URL = "https://storage.example/api"
STORAGE_KEY_ENV = "CAMPAIGN_STORAGE_KEY"


class StartingStore:
    """The remote store a campaign with remote storage connects to."""

    instances: list["StartingStore"] = []

    def __init__(self, base_url, api_key, *, verify=True):
        from uuid import uuid4

        self.base_url, self.api_key, self.verify = base_url, api_key, verify
        self.client = MagicMock()
        self.run_id, self.agent_id, self.org_id = uuid4(), uuid4(), uuid4()
        self.started: list[tuple] = []
        self.finished: list[tuple] = []
        self.closed: list[dict] = []
        self.context_error: Exception | None = None
        StartingStore.instances.append(self)

    def create_or_update_agent(self, name, config):
        return SimpleNamespace(id=self.agent_id)

    def start_campaign(self, agent, spec, *, claimed_by=None):
        from datetime import datetime, timezone

        from hackagent.storage.records import CampaignRunRecord

        self.started.append((agent, spec))
        now = datetime.now(timezone.utc)
        return CampaignRunRecord(
            id=self.run_id,
            agent_id=agent,
            name="test-campaign",
            campaign_config=spec,
            audit=None,
            status="RUNNING",
            run_notes=None,
            created_at=now,
            updated_at=now,
        )

    def get_context(self):
        from hackagent.storage.records import OrganizationContext

        if self.context_error is not None:
            raise self.context_error
        return OrganizationContext(org_id=self.org_id, user_id="7")

    def finish_run(self, run_id, status, note=""):
        self.finished.append((run_id, status, note))

    def close(self, **kwargs):
        self.closed.append(kwargs)


@pytest.fixture
def starting_store(monkeypatch):
    StartingStore.instances = []
    monkeypatch.setenv(STORAGE_KEY_ENV, "storage-key")
    monkeypatch.setattr(execute.RemoteBackend, "connect", StartingStore)
    return StartingStore.instances


def remote_spec(tmp_path, **sections):
    from hackagent.orchestrator.campaign import load_campaign

    execution = {
        "output": {"directory": str(tmp_path)},
        "storage": {
            "backend": "remote",
            "base_url": STORAGE_URL,
            "api_key": "${" + STORAGE_KEY_ENV + "}",
        },
        **sections.pop("execution", {}),
    }
    return load_campaign(campaign(execution=execution, **sections))


def test_execute_spec_starts_the_run_on_the_storage_server(
    tmp_path, starting_store, monkeypatch
):
    monkeypatch.delenv(GATEWAY_KEY_ENV, raising=False)
    built, seen = [], {}
    fakes = FakeBuilder(models(gateway=ScriptedModel("yes")))

    def build(config, *, retries=0):
        built.append(config)
        seen["key"] = os.environ.get(GATEWAY_KEY_ENV)
        return fakes(config, retries=retries)

    judge = {**GW, "scoring": {"type": "harmbench"}}
    outcome = execute.execute_spec(
        remote_spec(tmp_path, evaluation={"judges": [judge]}),
        build=build,
        load=goals("goal one"),
    )

    remote_store = starting_store[-1]
    store = RecordingAdoptedStore.instances[-1]
    # The server and key are the campaign's own, not the CLI settings.
    assert (remote_store.base_url, remote_store.api_key) == (
        STORAGE_URL,
        "storage-key",
    )
    assert outcome.status == "COMPLETED"
    assert (store.run_id, store.agent_id) == (
        remote_store.run_id,
        remote_store.agent_id,
    )
    assert store.finished == [(remote_store.run_id, "COMPLETED", "")]
    gateway = next(c for c in built if c.name == "gateway")
    assert gateway.connection.endpoint == f"{STORAGE_URL}/v1"
    assert seen["key"] == "storage-key"
    # The stored campaign keeps the gateway marker, not this executor's address.
    stored_judge = remote_store.started[0][1]["evaluation"]["judges"][0]["connection"]
    assert stored_judge["provider"] == "hackagent"
    assert "endpoint" not in stored_judge and "api_key" not in stored_judge
    assert remote_store.closed == [{"close_client": True}]


def test_execute_spec_needs_the_storage_key(tmp_path, starting_store, monkeypatch):
    from hackagent.core.credentials import CredentialError
    from hackagent.orchestrator.campaign import load_campaign

    monkeypatch.delenv("HACKAGENT_API_KEY", raising=False)
    spec = load_campaign(
        campaign(
            execution={
                "output": {"directory": str(tmp_path)},
                "storage": {"backend": "remote", "base_url": STORAGE_URL},
            }
        )
    )

    with pytest.raises(CredentialError, match="HACKAGENT_API_KEY"):
        execute.execute_spec(spec)
    assert starting_store == []


def test_an_interrupted_async_campaign_finishes_then_passes_on(
    tmp_path, starting_store
):
    def on_event(event, **payload):
        if event == "goal_finished":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        asyncio.run(
            execute.arun_remote_campaign(
                remote_spec(tmp_path),
                on_event=on_event,
                build=FakeBuilder(models()),
                load=goals("goal one"),
            )
        )

    store = RecordingAdoptedStore.instances[-1]
    assert store.finished == [(store.run_id, "CANCELLED", "Campaign cancelled")]
    assert starting_store[-1].closed == [{"close_client": True}]


def test_a_started_run_whose_setup_fails_is_finished_failed(
    tmp_path, starting_store, monkeypatch
):
    original = StartingStore.__init__

    def broken_context(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.context_error = RuntimeError("context unavailable")

    monkeypatch.setattr(StartingStore, "__init__", broken_context)

    with pytest.raises(RuntimeError, match="context unavailable"):
        execute.execute_spec(remote_spec(tmp_path), load=goals("goal one"))

    remote_store = starting_store[-1]
    assert remote_store.finished == [
        (remote_store.run_id, "FAILED", "RuntimeError: context unavailable")
    ]


class EnteredHeartbeat(FakeHeartbeat):
    def __enter__(self):
        self.entered = True
        return self


def test_run_campaign_with_remote_storage_is_a_tracked_run(
    tmp_path, starting_store, monkeypatch
):
    from hackagent.orchestrator.campaign import run_campaign

    FakeHeartbeat.instances = []
    monkeypatch.setattr(execute, "RunHeartbeat", EnteredHeartbeat)
    built = []
    fakes = FakeBuilder(models(gateway=ScriptedModel("yes")))

    def build(config, *, retries=0):
        built.append(config)
        return fakes(config, retries=retries)

    result = run_campaign(
        remote_spec(tmp_path, attacks=[{**PAP, "roles": {"attacker": GW}}]),
        build=build,
        load=goals("goal one"),
    )

    remote_store = starting_store[-1]
    store = RecordingAdoptedStore.instances[-1]
    assert result.campaign_run_id == str(remote_store.run_id)
    assert len(remote_store.started) == 1
    assert FakeHeartbeat.instances[-1].entered
    assert store.finished == [(remote_store.run_id, "COMPLETED", "")]
    gateway = next(c for c in built if c.name == "gateway")
    assert gateway.connection.endpoint == f"{STORAGE_URL}/v1"
    assert reference_name(gateway.connection.api_key) == GATEWAY_KEY_ENV


def test_run_campaign_with_remote_storage_raises_when_cancelled(
    tmp_path, starting_store, fake_heartbeat
):
    from hackagent.orchestrator.campaign import run_campaign

    def on_event(event, **payload):
        if event == "goal_finished":
            fake_heartbeat[-1].trip(fake_heartbeat[-1].cancel_requested)

    with pytest.raises(execute.RunEnded) as ended:
        run_campaign(
            remote_spec(tmp_path),
            on_event=on_event,
            build=FakeBuilder(models()),
            load=goals("one", "two", "three", "four"),
        )

    store = RecordingAdoptedStore.instances[-1]
    assert ended.value.outcome.status == "CANCELLED"
    assert store.finished == [(store.run_id, "CANCELLED", "Campaign cancelled")]


def test_run_campaign_passes_the_campaign_error_on_after_finishing(
    tmp_path, starting_store
):
    from hackagent.orchestrator.campaign import run_campaign

    def build(config, *, retries=0):
        raise LookupError("no such model")

    with pytest.raises(LookupError, match="no such model"):
        run_campaign(remote_spec(tmp_path), build=build, load=goals("one"))

    store = RecordingAdoptedStore.instances[-1]
    assert store.finished == [(store.run_id, "FAILED", "LookupError: no such model")]


def test_a_dry_run_never_touches_remote_storage(tmp_path, starting_store):
    from hackagent.orchestrator.campaign import run_campaign

    result = run_campaign(
        remote_spec(tmp_path, execution={"dry_run": True}),
        build=FakeBuilder(models()),
        load=goals("one"),
    )

    assert result.dry_run
    assert starting_store == []


# --- signals, cloud runs ------------------------------------------------------


def test_interrupt_during_the_claim_still_finishes_the_run(tmp_path):
    import signal

    run = run_detail(stored_campaign(tmp_path))
    finished = []

    def claim_run(run_id, claimed_by):
        signal.raise_signal(signal.SIGINT)  # held until the claim is ours
        return ClaimResult(run=run, run_token=None, env={})

    store = SimpleNamespace(
        client=MagicMock(),
        claim_run=claim_run,
        finish_run=lambda run_id, status, note="": finished.append(
            (run_id, status, note)
        ),
    )

    with pytest.raises(KeyboardInterrupt):
        execute.execute_run(
            store,
            run["id"],
            base_url=BASE_URL,
            gateway_key=GATEWAY_KEY,
            claimed_by="local:test",
            build=FakeBuilder(models()),
            load=goals("goal one"),
        )

    assert finished == [(run["id"], "CANCELLED", "Campaign cancelled")]


def test_interrupt_during_the_finish_lets_the_finish_land(tmp_path, monkeypatch):
    import signal

    original = RecordingAdoptedStore.finish_run

    def interrupted_finish(self, run_id, status, note=""):
        signal.raise_signal(signal.SIGINT)
        return original(self, run_id, status, note)

    monkeypatch.setattr(RecordingAdoptedStore, "finish_run", interrupted_finish)

    with pytest.raises(KeyboardInterrupt):
        execute_with(stored_campaign(tmp_path))

    store = RecordingAdoptedStore.instances[-1]
    assert store.finished == [(store.run_id, "COMPLETED", "")]


def test_interrupt_ends_the_run_as_the_executor_says(tmp_path):
    def on_event(event, **payload):
        if event == "goal_finished":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        execute_with(
            stored_campaign(tmp_path),
            on_event=on_event,
            interrupted_as=("FAILED", "The executor stopped"),
        )

    store = RecordingAdoptedStore.instances[-1]
    assert store.finished == [(store.run_id, "FAILED", "The executor stopped")]


def test_an_output_directory_replaces_where_files_are_written(tmp_path):
    configured, given = tmp_path / "configured", tmp_path / "given"
    config = stored_campaign(
        tmp_path, execution={"output": {"directory": str(configured)}}
    )

    outcome, _, _ = execute_with(config, output_directory=str(given))

    assert outcome.status == "COMPLETED"
    assert outcome.result.outputs
    assert all(given in path.parents for path in outcome.result.outputs)
    assert not configured.exists()


def test_a_run_keeps_the_campaign_s_output_directory_by_default(tmp_path):
    outcome, _, _ = execute_with(stored_campaign(tmp_path))

    assert outcome.result.outputs
    assert all(path.exists() for path in outcome.result.outputs)


# --- check ----------------------------------------------------------------------


def never_build(config, *, retries=0):
    raise AssertionError(f"built {config.name} for a run that must not start")


def test_a_run_the_check_refuses_ends_failed_before_building(tmp_path):
    seen = []

    def check(spec):
        seen.append(spec.campaign.name)
        return "This executor does not run this campaign"

    outcome, store, _ = execute_with(
        stored_campaign(tmp_path), builder=never_build, check=check
    )

    assert seen == ["test-campaign"]
    assert (outcome.status, outcome.note) == (
        "FAILED",
        "This executor does not run this campaign",
    )
    assert store.finished == [
        (store.run_id, "FAILED", "This executor does not run this campaign")
    ]


def test_an_interrupt_before_building_finishes_cancelled_then_passes_on(tmp_path):
    def check(spec):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        execute_with(stored_campaign(tmp_path), builder=never_build, check=check)

    store = RecordingAdoptedStore.instances[-1]
    assert store.finished == [(store.run_id, "CANCELLED", "Campaign cancelled")]


def test_a_run_the_check_accepts_executes(tmp_path):
    outcome, _, _ = execute_with(stored_campaign(tmp_path), check=lambda spec: None)

    assert outcome.status == "COMPLETED"
