# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""One run: context, judge once, persist rows that have a result id, flush."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import RunStatus, Verdict
from hackagent.core.settings import Settings
from hackagent.evaluation.panel import Panel
from hackagent.orchestrator.results.persistence import StoreSink
from hackagent.orchestrator.execution.runner import _instantiate, run
from tests.fakes.context import FakeLLMFactory, make_ctx
from tests.fakes.llm import FakeLLM
from tests.fakes.router import FakeRouter
from tests.fakes.storage import in_memory_store

_NO_FILE = "/nonexistent/hackagent/config.json"
_INTENTS = [{"category": "A"}]


class _Bus:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def emit(self, event_type, **payload) -> None:
        self.events.append((event_type, payload))


class _FlushWatch:
    def __init__(self, store, *, error: Exception | None = None) -> None:
        self._store = store
        self.flushes = 0
        self.error = error

    def flush(self) -> None:
        self.flushes += 1
        if self.error is not None:
            raise self.error
        self._store.flush()

    def __getattr__(self, name):
        return getattr(self._store, name)


def _settings() -> Settings:
    return Settings.resolve(api_key="", env={}, config_path=_NO_FILE)


def _technique(run_fn, seen):
    class _Attack:
        @classmethod
        def get_effective_model_roles(cls, config):
            return []

        def __init__(self, config, ctx):
            self.config = config
            self.ctx = ctx
            self.agent_router = ctx.target
            self.backend = None
            seen.append(self)

        def run(self, goals):
            return run_fn(self, goals)

    return _Attack


def _agent(store, *, target, models):
    record = store.create_or_update_agent(
        name="target",
        agent_type="OPENAI_SDK",
        endpoint="http://target.invalid",
        metadata={},
    )
    return SimpleNamespace(
        settings=_settings(),
        backend=store,
        agent_record=record,
        organization_id=record.organization,
        target=target,
        models=models,
        router=None,
        guardrails={},
        target_config={},
    )


def _rows_for(attack, goals):
    assert len(goals) == 4
    sink = attack.config["_backend"]
    run_id = UUID(attack.config["_run_id"])
    records = [
        sink.create_result(run_id, goal, index, {}, {})
        for index, goal in enumerate(goals)
    ]
    attack.records = records
    return [
        AttackResult(
            goal=goals[0],
            prompt="p0",
            response="kept",
            verdict=Verdict(success=False, score=1.0, explanation="attack verdict"),
            metadata={"result_id": str(records[0].id)},
        ),
        AttackResult(
            goal=goals[1],
            prompt="p1",
            response="judge me",
            metadata={"result_id": str(records[1].id)},
        ),
        AttackResult(
            goal=goals[2],
            prompt="p2",
            response="",
            metadata={"result_id": str(records[2].id)},
        ),
        AttackResult(
            goal=goals[3],
            prompt="p3",
            response="already flagged",
            metadata={"result_id": str(records[3].id), "success": True},
        ),
    ]


def test_run_judges_once_persists_result_ids_and_flushes(tmp_path, monkeypatch):
    seen = []
    judge_llm = FakeLLM(default="yes")
    target = FakeLLM(default="target")
    store = in_memory_store()
    watched = _FlushWatch(store)
    bus = _Bus()
    try:
        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.load_attack",
            lambda _attack_id: _technique(_rows_for, seen),
        )
        rows = run(
            _agent(watched, target=target, models=FakeLLMFactory(judge_llm)),
            {
                "attack_type": "baseline",
                "intents": _INTENTS,
                "output_dir": str(tmp_path),
                "max_tokens": 8,
                "judge": {
                    "identifier": "fake-judge",
                    "type": "harmbench",
                },
            },
            _tui_event_bus=bus,
        )
        attack = seen[0]
        ctx = attack.ctx
        assert isinstance(ctx.judge, Panel)
        assert isinstance(ctx.events.sink, StoreSink)
        assert ctx.events.sink.store is watched
        assert ctx.workspace.root == tmp_path / ctx.run_id
        assert ctx.target is not target
        assert ctx.target.params["max_tokens"] == 8

        assert len(judge_llm.requests) == 1
        assert "judge me" in judge_llm.requests[0]["messages"][-1]["content"]
        assert rows[0]["best_score"] == 1.0
        assert rows[0]["success"] is False
        assert rows[1]["eval_hb"] == 1
        assert rows[1]["success"] is True
        assert "verdict" not in rows[2]
        assert "eval_hb" not in rows[2]

        stored = [store.get_result(record.id) for record in attack.records]
        assert stored[0].evaluation_status == "FAILED_JAILBREAK"
        assert stored[0].evaluation_notes == "attack verdict"
        assert stored[1].evaluation_status == "SUCCESSFUL_JAILBREAK"
        assert stored[1].evaluation_metrics["eval_hb"] == 1
        assert stored[2].evaluation_status == "NOT_EVALUATED"
        assert stored[3].evaluation_status == "NOT_EVALUATED"

        runs = store.list_runs()
        assert runs.total == 1
        assert runs.items[0].status == RunStatus.COMPLETED.value
        assert watched.flushes == 1
        steps = [(kind, payload.get("step_name")) for kind, payload in bus.events]
        assert steps[0] == ("step_started", "Attack Execution")
        assert ("step_started", "Evaluation Pipeline") in steps
        assert ("step_ended", "Evaluation Pipeline") in steps
        assert steps[-1][0] == "step_ended"
        assert steps[-1][1] == "Attack Execution"
        ended = [payload for kind, payload in bus.events if kind == "step_ended"]
        assert all(payload["success"] is True for payload in ended)
    finally:
        store.close()


def test_rejudge_replaces_an_attack_verdict(tmp_path, monkeypatch):
    seen = []
    judge_llm = FakeLLM(default="yes")
    store = in_memory_store()
    try:

        def _one(attack, goals):
            return [
                AttackResult(
                    goal=goals[0],
                    prompt="p",
                    response="again",
                    verdict=Verdict(success=False, score=1.0),
                )
            ]

        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.load_attack",
            lambda _attack_id: _technique(_one, seen),
        )
        rows = run(
            _agent(
                store,
                target=FakeLLM(),
                models=FakeLLMFactory(judge_llm),
            ),
            {
                "attack_type": "baseline",
                "intents": [
                    {
                        "category": "A",
                        "subcategories": ["A1"],
                        "samples_per_subcategory": 1,
                    }
                ],
                "output_dir": str(tmp_path),
                "judge": {"identifier": "fake-judge", "type": "harmbench"},
            },
            run_config_override={"rejudge": True},
        )
        assert len(judge_llm.requests) == 1
        assert rows[0]["best_score"] == 10.0
        assert rows[0]["success"] is True
    finally:
        store.close()


def test_preflight_failure_does_not_create_a_run(tmp_path, monkeypatch):
    store = in_memory_store()
    try:
        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.load_attack",
            lambda _attack_id: _technique(lambda _attack, goals: [], []),
        )
        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.check_models",
            lambda *args, **kwargs: "unreachable",
        )
        rows = run(
            _agent(store, target=FakeLLM(), models=FakeLLMFactory()),
            {
                "attack_type": "baseline",
                "intents": _INTENTS,
                "output_dir": str(tmp_path),
            },
        )
        assert rows == []
        assert store.list_runs().total == 0
        assert store.list_attacks().total == 0
    finally:
        store.close()


def test_unconnectable_judge_marks_the_run_failed(tmp_path, monkeypatch):
    class _OfflineFactory(FakeLLMFactory):
        def for_role(self, spec):
            raise RuntimeError(f"offline: {spec.identifier}")

    seen = []
    store = in_memory_store()
    try:
        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.load_attack",
            lambda _attack_id: _technique(lambda _attack, goals: [], seen),
        )
        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.check_models",
            lambda *a, **kw: None,
        )
        with pytest.raises(ValueError, match="could not be connected"):
            run(
                _agent(store, target=FakeLLM(), models=_OfflineFactory()),
                {
                    "attack_type": "baseline",
                    "intents": _INTENTS,
                    "output_dir": str(tmp_path),
                    "judge": {"identifier": "fake-judge", "type": "harmbench"},
                },
            )
        assert seen == []
        run_record = store.list_runs().items[0]
        assert run_record.status == RunStatus.FAILED.value
        assert "could not be connected" in (run_record.run_notes or "")
    finally:
        store.close()


def test_evaluation_failure_returns_rows_marks_the_run_failed_and_flushes(
    tmp_path, monkeypatch
):
    store = in_memory_store()
    watched = _FlushWatch(store)
    try:

        def _one(_attack, goals):
            return [
                AttackResult(
                    goal=goals[0],
                    prompt="p",
                    response="kept",
                    verdict=Verdict(success=False, score=1.0),
                )
            ]

        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.load_attack",
            lambda _attack_id: _technique(_one, []),
        )

        def _boom(*args, **kwargs):
            raise RuntimeError("judge down")

        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.judge_unjudged", _boom
        )
        rows = run(
            _agent(watched, target=FakeLLM(), models=FakeLLMFactory()),
            {
                "attack_type": "baseline",
                "intents": [
                    {
                        "category": "A",
                        "subcategories": ["A1"],
                        "samples_per_subcategory": 1,
                    }
                ],
                "output_dir": str(tmp_path),
            },
        )
        assert rows[0]["best_score"] == 1.0
        run_record = store.list_runs().items[0]
        assert run_record.status == RunStatus.FAILED.value
        assert "Evaluation Pipeline" in (run_record.run_notes or "")
        assert watched.flushes == 1
    finally:
        store.close()


def test_flush_failure_keeps_the_rows_and_records_the_audit(tmp_path, monkeypatch):
    store = in_memory_store()
    watched = _FlushWatch(store, error=RuntimeError("flush failed"))
    try:
        monkeypatch.setattr(
            "hackagent.orchestrator.execution.runner.load_attack",
            lambda _attack_id: _technique(
                lambda _attack, goals: [
                    AttackResult(goal=goals[0], prompt="p", response="")
                ],
                [],
            ),
        )
        rows = run(
            _agent(watched, target=FakeLLM(), models=FakeLLMFactory()),
            {
                "attack_type": "baseline",
                "intents": [
                    {
                        "category": "A",
                        "subcategories": ["A1"],
                        "samples_per_subcategory": 1,
                    }
                ],
                "output_dir": str(tmp_path),
            },
        )
        assert rows[0]["goal"]
        run_record = store.list_runs().items[0]
        assert run_record.status == RunStatus.FAILED.value
        assert "Flush audit writes" in (run_record.run_notes or "")
        assert watched.flushes == 1
    finally:
        store.close()


def test_missing_attack_type_is_rejected():
    with pytest.raises(ValueError, match="attack_type"):
        run(SimpleNamespace(), {})


def test_instantiate_fills_router_and_backend_from_the_agent():
    ctx = make_ctx()
    router = FakeRouter()
    backend = object()

    class _Technique:
        def __init__(self, config, ctx):
            self.config = dict(config)
            self.ctx = ctx
            self.agent_router = ctx.target
            self.backend = None

    agent = SimpleNamespace(router=router, backend=backend)
    attack = _instantiate(_Technique, {"attack_type": "baseline"}, ctx, agent)
    assert attack.ctx is ctx
    assert attack.config == {"attack_type": "baseline"}
    assert attack.agent_router is router
    assert attack.backend is backend


def test_instantiate_keeps_a_router_that_can_already_route():
    ctx = make_ctx()
    kept_router = FakeRouter()
    kept_backend = object()

    class _Ready:
        def __init__(self, config, ctx):
            self.config = dict(config)
            self.ctx = ctx
            self.agent_router = kept_router
            self.backend = kept_backend

    attack = _instantiate(
        _Ready,
        {},
        ctx,
        SimpleNamespace(router=FakeRouter(), backend=object()),
    )
    assert attack.agent_router is kept_router
    assert attack.backend is kept_backend
