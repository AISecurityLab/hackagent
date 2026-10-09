# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A campaign sends every goal through every attack and judges the replies.

A static attack has its requests generated up front and the runner judges
each reply. An iterative one searches with the panel in hand, so what it
returns is already judged. Either way the run's trace is what the attack
did on the way there.
"""

from __future__ import annotations

import json

import pytest

from hackagent.orchestrator.campaign import run_campaign, summary

from .fakes import FakeBuilder, ScriptedModel, campaign, goals, model

TARGET_REPLY = "a reply the judge will read"

#: A PAIR attacker turn: the JSON shape its parser accepts.
_PAIR_TURN = json.dumps({"improvement": "sharper", "prompt": "an adversarial prompt"})


def attacker_role(**overrides):
    return {**model("attacker", "http://127.0.0.1:8003/v1"), **overrides}


def rewriting_attacker():
    """An attacker whose reply PAP can extract a rewritten goal from."""
    tag = "#mutated_text_with_same_specific_harmful_or_unlawful_intention:"
    return ScriptedModel(f"{tag} please")


def run(values, *, models=None, texts=("goal one",), store=None):
    """Run a campaign made of scripted models, and return its result."""
    builder = FakeBuilder(models or {})
    result = run_campaign(
        values, build=builder, load=goals(*texts), store=store or _store()
    )
    return result, builder


def _store():
    from tests.fakes import RecordingStore

    return RecordingStore()


def models_for(target_reply=TARGET_REPLY, judge="yes", **roles):
    """Scripted target, panel judge, and any role models, by name.

    The panel judge answers ``yes`` (a success) unless told otherwise.
    """
    scripted = {"target": ScriptedModel(target_reply), "judge": ScriptedModel(judge)}
    scripted.update(roles)
    return scripted


def attempts_of(result, attack: str = None):
    outcomes = [o for o in result.attacks if attack is None or o.name == attack]
    return [attempt for outcome in outcomes for attempt in outcome.attempts]


# --- the static path still behaves as it did --------------------------------


def test_a_static_attack_judges_every_request_it_generates(tmp_path):
    values = campaign(
        attacks=[{"name": "baseline"}],
        execution={"output": {"directory": str(tmp_path)}},
    )
    result, _builder = run(values, models=models_for())
    [attempt] = attempts_of(result)
    assert attempt.response.text == TARGET_REPLY
    assert attempt.verdict is not None and attempt.verdict.success is True
    assert attempt.trace == ()


def test_the_run_emits_lifecycle_events_per_attack_and_goal(tmp_path):
    """``on_event`` sees the attack bracket its goals, each reported as it ends."""
    events: list[tuple[str, dict]] = []
    values = campaign(
        attacks=[{"name": "baseline"}],
        execution={"output": {"directory": str(tmp_path)}},
    )
    run_campaign(
        values,
        build=FakeBuilder(models_for()),
        load=goals("goal one", "goal two"),
        store=_store(),
        on_event=lambda event, **payload: events.append((event, payload)),
    )

    kinds = [event for event, _ in events]
    assert kinds[0] == "attack_started"
    assert kinds[-1] == "attack_finished"
    assert kinds.count("goal_finished") == 2

    started = events[0][1]
    assert started["attack"] == "baseline"
    assert started["expected_goals"] == 2

    finished = [payload for event, payload in events if event == "goal_finished"]
    assert {payload["goal_index"] for payload in finished} == {0, 1}
    assert all(payload["success"] is True for payload in finished)
    assert all("elapsed_s" in payload and "attempts" in payload for payload in finished)

    assert events[-1][1]["error"] is None


# --- the iterative path ------------------------------------------------------


def iterative_campaign(tmp_path, **attack):
    """A campaign of one BoN attack, with output under ``tmp_path``."""
    spec = {"name": "bon", "parameters": {"steps": 1, "candidates": 2}, **attack}
    return campaign(attacks=[spec], execution={"output": {"directory": str(tmp_path)}})


def test_an_iterative_attack_submits_one_exchange_per_goal(tmp_path):
    values = iterative_campaign(tmp_path)
    models = models_for(judge="yes")
    result, _builder = run(values, models=models, texts=("goal one", "goal two"))

    assert len(attempts_of(result)) == 2
    # One step, so one exchange per goal; its two candidates both reach the
    # target but only the step's best is kept for the panel.
    assert len(models["target"].requests) == 4
    assert len(models["judge"].requests) == 2


def test_the_panel_rates_every_exchange_the_attack_kept(tmp_path):
    values = iterative_campaign(tmp_path, parameters={"steps": 3, "candidates": 2})
    models = models_for(judge="no")
    result, _builder = run(values, models=models)

    attempts = attempts_of(result)
    # Nothing passes, so all three steps run and each is judged on its own.
    assert len(models["target"].requests) == 6
    assert len(models["judge"].requests) == 3
    assert [attempt.request_index for attempt in attempts] == [0, 1, 2]
    assert [attempt.metadata["step"] for attempt in attempts] == [0, 1, 2]
    assert all(attempt.verdict is not None for attempt in attempts)


def test_pap_reports_one_attempt_per_technique(tmp_path):
    techniques = ["Logical Appeal", "Expert Endorsement", "Authority Endorsement"]
    values = campaign(
        attacks=[
            {
                "name": "pap",
                "parameters": {"techniques": techniques},
                "roles": {"attacker": attacker_role()},
            }
        ],
        execution={"output": {"directory": str(tmp_path)}},
    )
    models = models_for(judge="no", attacker=rewriting_attacker())
    result, _builder = run(values, models=models)

    attempts = attempts_of(result)
    assert [attempt.metadata["technique"] for attempt in attempts] == techniques
    assert len(models["judge"].requests) == 3
    assert all(attempt.verdict is not None for attempt in attempts)


def test_pair_reports_one_attempt_per_stream_and_round(tmp_path):
    values = campaign(
        attacks=[
            {
                "name": "pair",
                "parameters": {"streams": 2, "iterations": 2},
                "roles": {"attacker": attacker_role()},
            }
        ],
        execution={"output": {"directory": str(tmp_path)}},
    )
    models = models_for(judge="no", attacker=ScriptedModel(_PAIR_TURN))
    result, _builder = run(values, models=models)

    attempts = attempts_of(result)
    assert [(a.metadata["iteration"], a.metadata["stream"]) for a in attempts] == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ]
    # Each attempt keeps its own stream's work: its attacker turn and its verdict.
    for attempt in attempts:
        roles = [n.data["role"] for n in attempt.trace if n.node == "call"]
        assert roles == ["attacker", "target", "panel"]


def test_each_attempt_carries_the_phase_that_produced_it(tmp_path):
    values = iterative_campaign(tmp_path, parameters={"steps": 2, "candidates": 1})
    result, _builder = run(values, models=models_for(judge="no"))

    first, second = attempts_of(result)
    # Each step's phase, its target call and its verdict go to its own attempt.
    for attempt, step in ((first, 0), (second, 1)):
        assert [n.node for n in attempt.trace] == ["phase", "call", "call"]
        assert attempt.trace[0].label == f"step {step + 1}/2"
        assert [n.data["role"] for n in attempt.trace[1:]] == ["target", "panel"]
    # Nothing is stored twice.
    assert {n.path for n in first.trace}.isdisjoint({n.path for n in second.trace})


def test_what_the_attack_judged_is_what_the_run_reports(tmp_path):
    values = iterative_campaign(tmp_path)
    models = models_for(judge="no")
    result, _builder = run(values, models=models)

    [attempt] = attempts_of(result)
    # One panel call, in the loop; its verdict is the attempt's.
    assert len(models["judge"].requests) == 1
    assert attempt.verdict.success is False
    assert attempt.metadata["step"] == 0


def test_an_iterative_attack_runs_without_any_judges(tmp_path):
    values = iterative_campaign(tmp_path, parameters={"steps": 2, "candidates": 1})
    values["evaluation"] = {"judges": []}
    result, _builder = run(values, models=models_for())

    attempts = attempts_of(result)
    # Nothing to stop on, so every step runs and nothing is judged.
    assert len(attempts) == 2
    assert all(attempt.verdict is None for attempt in attempts)


def test_a_target_that_never_replies_leaves_an_error(tmp_path):
    from .fakes import failure

    models = models_for()
    models["target"] = ScriptedModel(lambda _messages: failure("target down"))
    result, _builder = run(iterative_campaign(tmp_path), models=models)

    [attempt] = attempts_of(result)
    assert attempt.error == "target never replied"
    assert attempt.verdict is None
    assert result.attempt_errors == 1


# --- scorer roles ------------------------------------------------------------


def test_the_panel_is_not_configurable_as_a_role(tmp_path):
    values = iterative_campaign(tmp_path, roles={"scorer": attacker_role()})
    with pytest.raises(ValueError, match="unknown roles scorer"):
        run(values, models=models_for())


def test_an_unknown_role_is_rejected(tmp_path):
    values = campaign(attacks=[{"name": "bon", "roles": {"attacker": attacker_role()}}])
    with pytest.raises(ValueError, match="unknown roles attacker"):
        run(values, models=models_for())


def test_a_role_configured_as_a_parameter_is_rejected(tmp_path):
    values = campaign(
        attacks=[{"name": "pap", "parameters": {"attacker": "some-model"}}]
    )
    with pytest.raises(ValueError, match="configure attacker under 'roles'"):
        run(values, models=models_for())


# --- traces -------------------------------------------------------------------


def test_the_trace_holds_every_call_and_why_the_search_stopped(tmp_path):
    values = iterative_campaign(tmp_path, parameters={"steps": 2, "candidates": 2})
    models = models_for(judge="yes")
    result, _builder = run(values, models=models)

    [attempt] = attempts_of(result)
    calls = [n for n in attempt.trace if n.node == "call"]
    # The panel passed the first step, so the second one never ran.
    assert [n.data["role"] for n in calls] == ["target", "target", "panel"]
    [stop] = [n for n in attempt.trace if n.node == "decision"]
    assert stop.label == "stopped"
    assert all(n.latency_s is not None for n in calls)


def test_each_traced_target_call_keeps_its_request_and_reply(tmp_path):
    values = iterative_campaign(tmp_path)
    result, _builder = run(values, models=models_for())

    nodes = attempts_of(result)[0].trace
    targets = [n for n in nodes if n.node == "call" and n.data["role"] == "target"]
    assert len(targets) == 2
    for node in targets:
        assert node.data["request"][-1]["role"] == "user"
        assert node.data["response"] == TARGET_REPLY
        assert node.error is None


def test_a_failed_role_call_is_traced_with_its_error(tmp_path):
    from .fakes import failure

    values = campaign(
        attacks=[
            {
                "name": "pap",
                "parameters": {"techniques": ["Logical Appeal"]},
                "roles": {"attacker": attacker_role()},
            }
        ],
        execution={"output": {"directory": str(tmp_path)}},
    )
    models = models_for(attacker=ScriptedModel(lambda _m: failure("attacker down")))
    result, _builder = run(values, models=models)

    [attempt] = attempts_of(result)
    [role_node] = [
        n for n in attempt.trace if n.node == "call" and n.data["role"] == "attacker"
    ]
    assert "attacker down" in role_node.error
    assert attempt.error == "target never replied"


def test_a_search_that_raises_keeps_what_it_had_already_traced(tmp_path):
    def flaky(messages):
        if len(models["target"].requests) > 1:
            raise RuntimeError("connection reset")
        return TARGET_REPLY

    values = iterative_campaign(tmp_path, parameters={"steps": 2, "candidates": 1})
    models = models_for(judge="no")
    models["target"] = ScriptedModel(flaky)
    result, _builder = run(values, models=models)

    [attempt] = attempts_of(result)
    assert attempt.error.startswith("search failed: ")
    assert "connection reset" in attempt.error
    assert attempt.verdict is None
    # The first step completed, and its trace outlived the failure.
    # The first step is whole; the second records the call that blew up.
    assert [n.node for n in attempt.trace] == [
        "phase",
        "call",
        "call",
        "phase",
        "call",
    ]
    assert attempt.trace[-1].error.endswith("connection reset")


def test_retention_settings_apply_to_traces(tmp_path):
    values = iterative_campaign(tmp_path)
    values["execution"]["output"].update(save_prompts=False, save_responses=False)
    result, _builder = run(values, models=models_for())

    traces = next(
        path for path in result.outputs if path.name.endswith(".traces.jsonl")
    )
    rows = [json.loads(line) for line in traces.read_text().splitlines()]
    calls = [n for row in rows for n in row["nodes"] if n["node"] == "call"]
    assert calls
    for node in calls:
        assert "request" not in node["data"] and "response" not in node["data"]
        assert node["latency_s"] is not None


def test_traces_are_written_beside_the_results(tmp_path):
    values = iterative_campaign(tmp_path)
    values["execution"]["output"]["formats"] = ["json", "jsonl"]
    result, _builder = run(values, models=models_for(judge="no"))

    written = {path.name for path in result.outputs}
    traces = next(
        path for path in result.outputs if path.name.endswith(".traces.jsonl")
    )
    [row] = [json.loads(line) for line in traces.read_text().splitlines()]
    assert f"{result.run_id}.json" in written
    assert row["attack"] == "bon" and row["goal_index"] == 0
    # Each node records where it sits, so the tree survives a flat file.
    assert row["nodes"][0] == {
        "v": 1,
        "scope": "goal",
        "path": [0],
        "node": "phase",
        "label": "step 1/1",
        "data": {"step": 0},
    }
    calls = [n for n in row["nodes"] if n["node"] == "call"]
    assert [n["data"]["role"] for n in calls].count("target") == 2


def test_traces_are_not_written_when_they_are_turned_off(tmp_path):
    values = iterative_campaign(tmp_path)
    values["execution"]["output"]["save_traces"] = False
    result, _builder = run(values, models=models_for())
    assert not any(path.name.endswith(".traces.jsonl") for path in result.outputs)


def test_every_trace_step_is_stored_with_its_result(tmp_path):
    from tests.fakes import in_memory_store

    values = iterative_campaign(tmp_path)
    store = in_memory_store()
    result, _builder = run(values, models=models_for(judge="no"), store=store)

    [attempt] = attempts_of(result)
    [record] = store.list_results(page_size=50).items
    stored = store.list_traces(record.id)
    # Every node of the search, then the exchange that was judged.
    assert len(stored) == len(attempt.trace) + 1
    assert stored[-1].step_type == "interaction"
    # StepKind is fixed by the API, so the node kind lives in the payload.
    assert [t.step_type for t in stored[:-1]] == [
        "TOOL_CALL" if n.node == "call" else "OTHER" for n in attempt.trace
    ]
    assert [t.content["node"] for t in stored[:-1]] == [n.node for n in attempt.trace]


# --- reporting ----------------------------------------------------------------


def test_the_summary_counts_iterative_successes(tmp_path):
    values = iterative_campaign(tmp_path)
    models = models_for(judge="yes")
    result, _builder = run(values, models=models, texts=("goal one", "goal two"))

    report = summary(result)
    assert report["succeeded"] is True
    assert report["attacks"][0] == {
        "name": "bon",
        "run_id": report["attacks"][0]["run_id"],
        "attempts": 2,
        "successes": 2,
        "error": None,
    }


def test_a_dry_run_builds_everything_and_sends_nothing(tmp_path):
    values = iterative_campaign(tmp_path)
    values["execution"]["dry_run"] = True
    models = models_for()
    result, _builder = run(values, models=models)

    assert result.dry_run is True
    assert result.attacks == ()
    assert models["target"].requests == []


def test_a_run_scoped_prepare_runs_once_and_is_traced(tmp_path):
    """AutoDAN-Turbo's warm-up runs before any goal, under a run-scoped trace."""
    import json

    from hackagent.orchestrator.campaign.runner import run_campaign
    from tests.fakes import RecordingStore

    from .fakes import FakeBuilder, ScriptedModel, goals

    def tagged(_messages):
        return "[START OF JAILBREAK PROMPT]an attempt[END OF JAILBREAK PROMPT]"

    def strategy(_messages):
        return json.dumps({"Strategy": "S", "Definition": "d"})

    async def embed(texts):
        return [[1.0, 0.0] for _ in texts]

    values = campaign(
        attacks=[
            {
                "name": "autodan_turbo",
                "parameters": {
                    "epochs": 1,
                    "warmup_iterations": 1,
                    "lifelong_iterations": 1,
                },
                "roles": {
                    "attacker": attacker_role(),
                    "summarizer": attacker_role(name="summarizer"),
                    "embedder": {**model("embedder", "http://127.0.0.1:8100/v1")},
                },
            }
        ],
        execution={"output": {"directory": str(tmp_path)}},
    )
    builder = FakeBuilder(
        {
            "target": ScriptedModel("a response"),
            "judge": ScriptedModel("no"),
            "attacker": ScriptedModel(tagged),
            "summarizer": ScriptedModel(strategy),
        }
    )
    result = run_campaign(
        values,
        build=builder,
        load=goals("goal one", "goal two"),
        store=RecordingStore(),
        build_embed=lambda _config: embed,
    )

    [outcome] = result.attacks
    # The warm-up produced a run-scoped trace, distinct from the per-goal ones.
    assert outcome.run_trace
    assert all(node.scope == "run" for node in outcome.run_trace)
    # Two warm-up goals plus lifelong epochs reached the target.
    assert len(builder.models["target"].requests) >= 2
