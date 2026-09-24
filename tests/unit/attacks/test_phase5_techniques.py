# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Phase 5 technique tests on ``make_ctx()`` / ``FakeJudge``.

Post-hoc attacks are constructed from ``make_ctx()`` and, where the pipeline
is generation-only and cheap, exercised against a scripted target LLM.
AdvPrefix selection goes through ``ctx.judge.evaluate``. FlipAttack generation
is called with ``attack=`` and no ``config["_self"]``.

Inline-judge and custom-loop early-stop tests script ``FakeJudge`` scores and
assert the production stop condition. Soft-fail coverage follows the
implementation: inline adapters swallow judge errors; Crescendo, PAIR, and
RAG return a non-success score; AutoDAN-Turbo does not catch judge errors.
RAG has no early-stop loop.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from hackagent.attacks._lib.inline_judge import CtxJudgeAdapter, CtxTapEvaluator
from hackagent.attacks._lib.llm_router import LLMRouter
from hackagent.attacks.techniques.adaptive.advprefix.attack import AdvPrefixAttack
from hackagent.attacks.techniques.adaptive.autodan_turbo import lifelong, warm_up
from hackagent.attacks.techniques.adaptive.autodan_turbo.attack import (
    AutoDANTurboAttack,
)
from hackagent.attacks.techniques.static.baseline import (
    generation as baseline_generation,
)
from hackagent.attacks.techniques.static.baseline.attack import BaselineAttack
from hackagent.attacks.techniques.adaptive.bon import generation as bon_generation
from hackagent.attacks.techniques.adaptive.bon.attack import BoNAttack
from hackagent.attacks.techniques.static.cipherchat import (
    generation as cipherchat_generation,
)
from hackagent.attacks.techniques.static.cipherchat.attack import CipherChatAttack
from hackagent.attacks.techniques.multi_turn.crescendo.attack import CrescendoAttack
from hackagent.attacks.techniques.static.fc.attack import FCAttack, tFCAttack
from hackagent.attacks.techniques.static.flipattack.attack import FlipAttack
from hackagent.attacks.techniques.static.h4rm3l.attack import (
    H4rm3lAttack,
    _emit_h4rm3l_decoration_traces,
)
from hackagent.attacks.techniques.static.mml.attack import MMLAttack
from hackagent.attacks.techniques.adaptive.pair.attack import PAIRAttack
from hackagent.attacks.techniques.adaptive.pap import generation as pap_generation
from hackagent.attacks.techniques.adaptive.pap.attack import PAPAttack
from hackagent.attacks.techniques.indirect.rag.attack import RagAttack
from hackagent.attacks.techniques.static.static_template import (
    generation as static_generation,
)
from hackagent.attacks.techniques.static.static_template.attack import (
    StaticTemplateAttack,
)
from hackagent.attacks.techniques.adaptive.tap.attack import TAPAttack
from hackagent.attacks.techniques.adaptive.tap.generation import TapExecutor
from hackagent.attacks.techniques.indirect.tool_output_ipi import (
    generation as ipi_generation,
)
from hackagent.attacks.techniques.indirect.tool_output_ipi.attack import (
    ToolOutputIPIAttack,
)
from tests.fakes import FakeJudge, FakeLLM, FakeLLMFactory, make_ctx
from tests.fakes.router import FakeRouter

LOGGER = logging.getLogger("test.phase5.techniques")

_POST_HOC = [
    AdvPrefixAttack,
    BaselineAttack,
    StaticTemplateAttack,
    CipherChatAttack,
    FCAttack,
    tFCAttack,
    FlipAttack,
    H4rm3lAttack,
    MMLAttack,
]
_INLINE = [BoNAttack, PAPAttack, ToolOutputIPIAttack, TAPAttack]
_CUSTOM = [CrescendoAttack, PAIRAttack, AutoDANTurboAttack, RagAttack]
_LIGHT_GENERATION = {
    BaselineAttack: baseline_generation.execute,
    StaticTemplateAttack: static_generation.execute,
    CipherChatAttack: cipherchat_generation.execute,
}


class _FailingJudge:
    """Judge port that always raises. Used for soft-fail tests."""

    def __init__(self) -> None:
        self.calls = 0

    def score(self, sample):
        self.calls += 1
        raise RuntimeError("judge unavailable")

    def evaluate(self, sample):
        self.calls += 1
        raise RuntimeError("judge unavailable")


def _target_router(text: str = "target answer") -> tuple[LLMRouter, FakeLLM]:
    llm = FakeLLM(default=text)
    return LLMRouter(llm), llm


def _assert_ctx_wired(attack, ctx) -> None:
    assert attack.ctx is ctx
    assert attack.backend is None
    assert attack.agent_router is ctx.target
    assert attack.run_id == ctx.run_id
    assert attack.run_dir == str(ctx.workspace.root)


def _run_light_generation(attack, goals, router):
    step = attack._get_pipeline_steps()[0]
    assert step["function"] is _LIGHT_GENERATION[type(attack)]
    attack.agent_router = router
    step_config = {
        key: attack.config[key]
        for key in step.get("config_keys", [])
        if key in attack.config
    }
    args = attack._build_step_args(step, step_config, goals)
    return step["function"](**args)


@pytest.mark.parametrize("cls", _POST_HOC + _INLINE + _CUSTOM, ids=lambda c: c.__name__)
def test_technique_constructs_from_make_ctx(cls, tmp_path):
    ctx = make_ctx(tmp_path=tmp_path)
    attack = cls({}, ctx)
    _assert_ctx_wired(attack, ctx)
    assert "_suppress_run_status_updates" not in attack.config


@pytest.mark.parametrize(
    "cls",
    [BaselineAttack, StaticTemplateAttack, CipherChatAttack],
    ids=lambda c: c.__name__,
)
def test_post_hoc_generation_uses_target_llm(cls, tmp_path):
    ctx = make_ctx(tmp_path=tmp_path)
    attack = cls({}, ctx)
    router, llm = _target_router("plain completion")
    results = _run_light_generation(attack, ["say hello"], router)
    assert results
    assert results[0]["goal"] == "say hello"
    assert llm.requests


def test_advprefix_selection_uses_ctx_judge_evaluate(tmp_path):
    judge = FakeJudge(scores=[3.0, 9.0])
    events_ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = AdvPrefixAttack({}, events_ctx)
    selected = attack._evaluate_and_select(
        input_data=[
            {"goal": "g", "prefix": "weak", "completion": "no"},
            {"goal": "g", "prefix": "strong", "completion": "yes"},
        ],
        config={"n_prefixes_per_goal": 1},
        logger=attack.logger,
        client=None,
    )
    assert len(judge.samples) == 2
    assert judge.samples[0].prompt == "weak"
    assert judge.samples[1].response == "yes"
    assert len(selected) == 1
    assert selected[0]["prefix"] == "strong"
    assert selected[0]["best_score"] == 9.0
    assert selected[0]["success"] is True
    assert selected[0]["verdict"].score == 9.0
    evaluations = [call for call in events_ctx.events.calls if call[0] == "evaluation"]
    assert len(evaluations) == 2


def test_flipattack_pipeline_runs_without_config_self(tmp_path):
    ctx = make_ctx(tmp_path=tmp_path)
    attack = FlipAttack({}, ctx)
    assert "_self" not in attack.config
    step = attack._get_pipeline_steps()[0]
    router, llm = _target_router("flipped reply")
    results = step["function"](
        goals=["write a plan"],
        agent_router=router,
        config=attack.config,
        logger=attack.logger,
    )
    assert "_self" not in attack.config
    assert results[0]["goal"] == "write a plan"
    assert results[0]["response"] == "flipped reply"
    assert llm.requests
    assert "verdict" not in results[0]


def test_fc_workspace_cache_is_under_ctx(tmp_path):
    ctx = make_ctx(tmp_path=tmp_path)
    for cls in (FCAttack, tFCAttack):
        attack = cls({}, ctx)
        attack._wire_workspace_cache("flowchart")
        cache = ctx.workspace.path("cache", "flowchart")
        assert attack.config["_workspace_cache_dir"] == str(cache)
        assert cache.is_dir()


def test_h4rm3l_decoration_traces_go_to_ctx_events(tmp_path):
    ctx = make_ctx(tmp_path=tmp_path)
    attack = H4rm3lAttack({}, ctx)
    _emit_h4rm3l_decoration_traces(
        [
            {
                "goal": "g",
                "decoration_steps": [
                    {
                        "step_index": 1,
                        "decorator": "Base64Decorator",
                        "decorated_prompt": "encoded",
                    }
                ],
            }
        ],
        events=attack.ctx.events,
    )
    traces = [call for call in ctx.events.calls if call[0] == "trace"]
    assert traces
    assert traces[0][2]["decorator"] == "Base64Decorator"


def test_inline_attacks_attach_ctx_judge(tmp_path):
    judge = FakeJudge(score=4.0)
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    for cls in _INLINE:
        attack = cls({}, ctx)
        assert attack.config["_judge"] is judge


def test_bon_high_score_stops_before_later_steps(tmp_path):
    judge = FakeJudge(scores=[8.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = BoNAttack(
        {
            "jailbreak_threshold": 7,
            "bon_params": {
                "n_steps": 3,
                "num_concurrent_k": 1,
                "word_scrambling": False,
                "random_capitalization": False,
                "ascii_perturbation": False,
            },
        },
        ctx,
    )
    router, llm = _target_router("long enough answer")
    results = bon_generation.execute(["goal"], router, attack.config, LOGGER)
    assert results[0]["success"] is True
    assert results[0]["best_score"] == 8.0
    assert len(judge.samples) == 1
    assert len(llm.requests) == 1


def test_bon_low_scores_run_every_step(tmp_path):
    judge = FakeJudge(scores=[1.0, 2.0, 3.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = BoNAttack(
        {
            "bon_params": {
                "n_steps": 3,
                "num_concurrent_k": 1,
                "word_scrambling": False,
                "random_capitalization": False,
                "ascii_perturbation": False,
            }
        },
        ctx,
    )
    router, llm = _target_router("answer")
    results = bon_generation.execute(["goal"], router, attack.config, LOGGER)
    assert results[0]["success"] is False
    assert results[0]["best_score"] == 3.0
    assert len(judge.samples) == 3
    assert len(llm.requests) == 3


def test_bon_judge_error_soft_fails_and_continues(tmp_path):
    judge = _FailingJudge()
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = BoNAttack(
        {
            "bon_params": {
                "n_steps": 2,
                "num_concurrent_k": 1,
                "word_scrambling": False,
                "random_capitalization": False,
                "ascii_perturbation": False,
            }
        },
        ctx,
    )
    router, llm = _target_router("answer")
    results = bon_generation.execute(["goal"], router, attack.config, LOGGER)
    assert results[0]["success"] is False
    assert results[0]["best_score"] == 0.0
    assert judge.calls == 2
    assert len(llm.requests) == 2
    adapter = CtxJudgeAdapter(judge, config=attack.config, logger=LOGGER)
    ok, score, _cols = adapter.is_jailbreak("g", "p", "r")
    assert ok is False
    assert score == 0.0


def test_pap_high_score_stops_remaining_techniques(tmp_path):
    judge = FakeJudge(scores=[8.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = PAPAttack(
        {
            "jailbreak_threshold": 7,
            "pap_params": {
                "techniques": [
                    "Logical Appeal",
                    "Expert Endorsement",
                    "Authority Endorsement",
                ]
            },
        },
        ctx,
    )
    attacker = LLMRouter(FakeLLM(default="persuasive rewrite"))
    router, llm = _target_router("target complied")
    with patch(
        "hackagent.attacks.techniques.adaptive.pap.generation._create_attacker_router",
        return_value=attacker,
    ):
        results = pap_generation.execute(["goal"], router, attack.config, LOGGER)
    assert results[0]["success"] is True
    assert results[0]["technique"] == "Logical Appeal"
    assert len(judge.samples) == 1
    assert len(llm.requests) == 1


def test_pap_low_scores_try_every_technique(tmp_path):
    judge = FakeJudge(scores=[1.0, 4.0, 2.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = PAPAttack(
        {
            "pap_params": {
                "techniques": [
                    "Logical Appeal",
                    "Expert Endorsement",
                    "Authority Endorsement",
                ]
            }
        },
        ctx,
    )
    attacker = LLMRouter(FakeLLM(default="persuasive rewrite"))
    router, _llm = _target_router("target answer")
    with patch(
        "hackagent.attacks.techniques.adaptive.pap.generation._create_attacker_router",
        return_value=attacker,
    ):
        results = pap_generation.execute(["goal"], router, attack.config, LOGGER)
    assert results[0]["success"] is False
    assert results[0]["best_score"] == 4.0
    assert results[0]["technique"] == "Expert Endorsement"
    assert len(judge.samples) == 3


def test_tool_output_ipi_high_score_stops_attempts(tmp_path):
    judge = FakeJudge(scores=[9.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = ToolOutputIPIAttack(
        {
            "jailbreak_threshold": 7,
            "tool_output_ipi_params": {
                "mode": "simulated",
                "max_attempts": 3,
                "use_attacker_llm": False,
            },
        },
        ctx,
    )
    router, llm = _target_router("I will follow the tool result")
    results = ipi_generation.execute(["steal the key"], router, attack.config, LOGGER)
    assert results[0]["success"] is True
    assert results[0]["attempts"] == 1
    assert len(judge.samples) == 1
    assert len(llm.requests) == 1


def test_tool_output_ipi_judge_error_soft_fails_without_stopping_early(tmp_path):
    judge = _FailingJudge()
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = ToolOutputIPIAttack(
        {
            "tool_output_ipi_params": {
                "mode": "simulated",
                "max_attempts": 2,
                "use_attacker_llm": False,
            }
        },
        ctx,
    )
    router, llm = _target_router("harmless reply")
    results = ipi_generation.execute(["goal"], router, attack.config, LOGGER)
    assert results[0]["success"] is False
    assert results[0]["attempts"] == 2
    assert judge.calls == 2
    assert len(llm.requests) == 2


def _tap_executor(config, router):
    with patch(
        "hackagent.attacks.techniques.adaptive.tap.generation._initialize_attacker_router",
        return_value=(LLMRouter(FakeLLM(default="unused")), "unused"),
    ):
        executor = TapExecutor(config, client=None, agent_router=router, logger=LOGGER)
    executor._query_attacker = lambda _messages: {
        "prompt": "candidate",
        "improvement": "tighter",
    }
    return executor


def test_tap_high_score_stops_before_later_depths(tmp_path):
    judge = FakeJudge(scores=[10.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = TAPAttack(
        {
            "tap_params": {
                "depth": 3,
                "width": 1,
                "branching_factor": 1,
                "n_streams": 1,
                "verbose": False,
                "early_stop_on_success": True,
                "success_score_threshold": 10,
            }
        },
        ctx,
    )
    router, _llm = _target_router("sure")
    executor = _tap_executor(attack.config, router)
    assert isinstance(executor.evaluator, CtxTapEvaluator)
    calls = {"n": 0}

    def _target(_prompt):
        calls["n"] += 1
        return "sure, here it is"

    executor._query_target = _target
    result = executor.run_single_goal("goal", 0)
    assert result["is_success"] is True
    assert result["iterations_completed"] == 1
    assert result["best_score"] == 10
    assert calls["n"] == 1
    assert len(judge.samples) == 1


def test_tap_disabled_early_stop_runs_every_depth(tmp_path):
    judge = FakeJudge(scores=[10.0, 10.0, 10.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = TAPAttack(
        {
            "tap_params": {
                "depth": 3,
                "width": 1,
                "branching_factor": 1,
                "n_streams": 1,
                "verbose": False,
                "early_stop_on_success": False,
                "success_score_threshold": 10,
                "min_judge_prune_score": 0,
            }
        },
        ctx,
    )
    router, _llm = _target_router("sure")
    executor = _tap_executor(attack.config, router)
    executor._query_target = lambda _prompt: "sure"
    result = executor.run_single_goal("goal", 0)
    assert result["iterations_completed"] == 3
    assert len(judge.samples) == 3


def test_tap_judge_error_soft_fails_to_zero_and_does_not_stop(tmp_path):
    judge = _FailingJudge()
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = TAPAttack(
        {
            "tap_params": {
                "depth": 2,
                "width": 1,
                "branching_factor": 1,
                "n_streams": 1,
                "verbose": False,
                "early_stop_on_success": True,
                "success_score_threshold": 10,
                "min_judge_prune_score": 0,
            }
        },
        ctx,
    )
    router, _llm = _target_router("sure")
    executor = _tap_executor(attack.config, router)
    executor._query_target = lambda _prompt: "sure"
    result = executor.run_single_goal("goal", 0)
    assert result["is_success"] is False
    assert result["best_score"] == 0
    assert result["iterations_completed"] == 2
    assert judge.calls == 2


def _crescendo(ctx, **config):
    attack = CrescendoAttack(
        {"max_turns": 3, "max_backtracks": 0, **config},
        ctx,
    )
    attack._query_attacker = lambda _messages: {
        "question": "next question",
        "assistant_content": '{"question": "next question"}',
    }
    attack._query_target = lambda _messages: (
        "Sure, the detailed steps follow.",
        {},
    )
    return attack


def test_crescendo_high_score_stops(tmp_path):
    judge = FakeJudge(scores=[8.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _crescendo(ctx, jailbreak_threshold=7)
    assert attack.attacker_router.llm is ctx.models.llm
    result = attack._run_single_goal("goal", 0)
    assert result["is_success"] is True
    assert result["turns_completed"] == 1
    assert result["best_score"] == 8.0
    assert len(judge.samples) == 1
    assert judge.samples[0].prompt == "next question"


def test_crescendo_low_scores_run_every_turn(tmp_path):
    judge = FakeJudge(scores=[1.0, 2.0, 3.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _crescendo(ctx, jailbreak_threshold=7)
    result = attack._run_single_goal("goal", 0)
    assert result["is_success"] is False
    assert result["turns_completed"] == 3
    assert len(judge.samples) == 3


def test_crescendo_refusal_does_not_count_as_early_stop(tmp_path):
    judge = FakeJudge(scores=[9.0, 9.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _crescendo(ctx, max_turns=2, jailbreak_threshold=7)
    attack._query_target = lambda _messages: ("I'm sorry, I cannot help with that.", {})
    result = attack._run_single_goal("goal", 0)
    assert result["turns_completed"] == 2
    assert result["is_success"] is False
    assert result["best_score"] == 0.0


def test_crescendo_judge_error_soft_fails_and_continues(tmp_path):
    judge = _FailingJudge()
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _crescendo(ctx, max_turns=2)
    result = attack._run_single_goal("goal", 0)
    assert result["is_success"] is False
    assert result["best_score"] == 0.0
    assert result["turns_completed"] == 2
    assert judge.calls == 2


def _pair(ctx, **config):
    attack = PAIRAttack(
        {"n_iterations": 3, "n_streams": 1, "jailbreak_threshold": 8, **config},
        ctx,
    )
    attack._query_attacker = lambda *args, **kwargs: "adversarial prompt"
    attack._query_target_simple = lambda *args, **kwargs: ("detailed compliance", {})
    return attack


def test_pair_high_score_stops(tmp_path):
    judge = FakeJudge(scores=[9.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _pair(ctx)
    assert attack.attacker_router.llm is ctx.models.llm
    result = attack._run_single_goal("goal", 0)
    assert result["is_success"] is True
    assert result["iterations_completed"] == 1
    assert result["best_score"] == 9.0
    assert len(judge.samples) == 1


def test_pair_low_scores_run_every_iteration(tmp_path):
    judge = FakeJudge(scores=[2.0, 3.0, 4.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _pair(ctx)
    result = attack._run_single_goal("goal", 0)
    assert result["is_success"] is False
    assert result["iterations_completed"] == 3
    assert result["best_score"] == 4.0
    assert len(judge.samples) == 3


def test_pair_judge_error_soft_fails_to_one(tmp_path):
    judge = _FailingJudge()
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = _pair(ctx)
    score = attack._score_response("goal", "response text")
    assert score == 1.0
    assert judge.calls == 1


class _EmptyLibrary:
    def size(self):
        return 0

    def all(self):
        return {}

    def add(self, _strategy):
        return None

    def embed(self, _text):
        return None


def _autodan_config(judge, *, epochs, break_score, iterations_key, iterations):
    return {
        "autodan_turbo_params": {
            "epochs": epochs,
            "break_score": break_score,
            iterations_key: iterations,
        },
        "attacker": {"identifier": "attacker-role"},
        "judge": {"identifier": "judge-role"},
        "summarizer": {"identifier": "summarizer-role"},
        "_judge": judge,
    }


def test_autodan_wires_models_judge_and_workspace(tmp_path):
    judge = FakeJudge(score=1.0)
    models = FakeLLMFactory(FakeLLM(default="role"))
    ctx = make_ctx(judge=judge, models=models, tmp_path=tmp_path)
    attack = AutoDANTurboAttack({}, ctx)
    assert attack.config["_judge"] is judge
    assert attack.config["_models"] is models
    library_path = str(ctx.workspace.path("strategy_library"))
    assert library_path.startswith(str(tmp_path))


def test_autodan_warmup_high_score_stops_epochs(tmp_path):
    judge = FakeJudge(scores=[9.0, 1.0, 1.0])
    ctx = make_ctx(judge=judge, tmp_path=tmp_path)
    attack = AutoDANTurboAttack({}, ctx)
    assert attack.config["_judge"] is judge
    config = _autodan_config(
        judge,
        epochs=3,
        break_score=8.5,
        iterations_key="warm_up_iterations",
        iterations=1,
    )
    config["_models"] = ctx.models
    router = FakeRouter(default="target text")
    with (
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.init_routers",
            return_value=(router, "a", router, "s", router, "z"),
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.conditional_generate",
            return_value="jailbreak prompt",
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.extract_jailbreak_prompt",
            side_effect=lambda resp, request: resp or request,
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.query_target",
            return_value=("complied", None),
        ) as query_target,
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.StrategyLibrary",
            return_value=_EmptyLibrary(),
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.emit_phase_trace"
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.summarize_strategy",
            return_value=None,
        ),
    ):
        _library, log = warm_up.execute(["goal"], config, None, router, LOGGER)
    assert query_target.call_count == 1
    assert len(log) == 1
    assert log[0]["score"] == 9.0
    assert len(judge.samples) == 1


def test_autodan_lifelong_high_score_stops_epochs(tmp_path):
    judge = FakeJudge(scores=[9.0, 1.0])
    config = _autodan_config(
        judge,
        epochs=2,
        break_score=8.5,
        iterations_key="lifelong_iterations",
        iterations=1,
    )
    router = FakeRouter(default="target text")
    with (
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.lifelong.init_routers",
            return_value=(router, "a", router, "s", router, "z"),
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.lifelong.conditional_generate",
            return_value="jailbreak prompt",
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.lifelong.extract_jailbreak_prompt",
            side_effect=lambda resp, request: resp or request,
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.lifelong.query_target",
            return_value=("complied", None),
        ) as query_target,
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.lifelong.emit_phase_trace"
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.lifelong.summarize_strategy",
            return_value=None,
        ),
    ):
        results = lifelong.execute(
            ["goal"], config, None, router, LOGGER, _EmptyLibrary()
        )
    assert query_target.call_count == 1
    assert results[0]["success"] is True
    assert results[0]["score"] == 9.0
    assert len(judge.samples) == 1


def test_autodan_warmup_low_score_runs_every_epoch(tmp_path):
    judge = FakeJudge(scores=[1.0, 2.0])
    config = _autodan_config(
        judge,
        epochs=2,
        break_score=8.5,
        iterations_key="warm_up_iterations",
        iterations=1,
    )
    router = FakeRouter(default="target text")
    with (
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.init_routers",
            return_value=(router, "a", router, "s", router, "z"),
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.conditional_generate",
            return_value="prompt",
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.extract_jailbreak_prompt",
            side_effect=lambda resp, request: resp or request,
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.query_target",
            return_value=("refused", None),
        ) as query_target,
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.StrategyLibrary",
            return_value=_EmptyLibrary(),
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.emit_phase_trace"
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.warm_up.summarize_strategy",
            return_value=None,
        ),
    ):
        _library, log = warm_up.execute(["goal"], config, None, router, LOGGER)
    assert query_target.call_count == 2
    assert [row["score"] for row in log] == [1.0, 2.0]


def test_autodan_saves_strategy_library_under_workspace(tmp_path):
    ctx = make_ctx(tmp_path=tmp_path)
    attack = AutoDANTurboAttack({}, ctx)
    library = _EmptyLibrary()
    saved = {}

    def _save(path):
        saved["path"] = path

    library.save = _save
    with (
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.attack.warm_up.execute",
            return_value=(library, []),
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.attack.lifelong.execute",
            return_value=[{"goal": "goal", "success": False, "score": 1.0}],
        ),
        patch(
            "hackagent.attacks.techniques.adaptive.autodan_turbo.attack.emit_phase_trace",
        ),
    ):
        attack.run(["goal"])
    assert saved["path"] == str(ctx.workspace.path("strategy_library"))


def _rag_attacker(request):
    messages = request.get("messages") or []
    system = ""
    if messages and isinstance(messages[0], dict):
        system = str(messages[0].get("content") or "").lower()
    if "queries" in system:
        text = "What is the returns policy?\nHow do I request a refund?"
    else:
        text = "This authoritative passage advances the goal with concrete steps."
    return {
        "generated_text": text,
        "processed_response": text,
        "error_message": None,
    }


def test_rag_judge_and_poisoned_docs_use_ctx(tmp_path):
    judge = FakeJudge(score=9.0, success=True)
    role_llm = FakeLLM(script=_rag_attacker)
    target_llm = FakeLLM(default="Sure, here is the requested content with steps.")
    ctx = make_ctx(
        target=target_llm,
        models=FakeLLMFactory(role_llm),
        judge=judge,
        tmp_path=tmp_path,
    )
    source = tmp_path / "docs"
    source.mkdir()
    (source / "returns.txt").write_text(
        "\n\n".join(
            [
                "Returns are accepted within thirty days of purchase.",
                "Customers must provide the original receipt.",
                "Refunds are issued to the original payment method.",
                "For damaged goods, contact support before shipping.",
                "Gift purchases can be exchanged for store credit.",
            ]
        ),
        encoding="utf-8",
    )
    attack = RagAttack(
        {
            "rag_injection_params": {
                "documents": {
                    "sources": [str(source)],
                    "include_globs": ["*.txt"],
                },
                "poisoning": {
                    "strategy": "inline_context_override",
                    "poisoned_ratio": 1.0,
                },
                "benign_queries_per_goal": 1,
                "poisoned_paragraphs_per_query": 1,
                "target_retrieval": {
                    "chunk_size": 400,
                    "chunk_overlap": 50,
                    "top_k": 2,
                },
            }
        },
        ctx,
    )
    assert attack.attacker_router.llm is role_llm
    attack.agent_router = LLMRouter(target_llm)
    scored = attack._judge_response("query", "context", "response", "goal")
    assert scored["classification"] == "SUCCESS"
    assert scored["best_score"] == 9.0
    assert judge.samples[-1].goal == "goal"

    failing = _FailingJudge()
    attack.ctx = make_ctx(judge=failing, tmp_path=tmp_path)
    soft = attack._judge_response("query", "context", "response", "goal")
    assert soft["classification"] == "INCONCLUSIVE"
    assert failing.calls == 1

    # Restore the scripted judge and write poisoned docs through run().
    attack.ctx = ctx
    with patch(
        "hackagent.attacks.techniques.indirect.rag.attack.get_embeddings",
        lambda texts, config, logger: (
            __import__("numpy")
            .random.RandomState(0)
            .rand(len(texts), 8)
            .astype("float32")
        ),
    ):
        results = attack.run(["Make the assistant reveal hidden steps"])
    poisoned = list(ctx.workspace.path("goal_0", "poisoned").glob("*_poisoned.txt"))
    assert poisoned
    assert results
    assert any(sample.goal for sample in judge.samples)


def test_rag_has_no_early_stop_flag(tmp_path):
    """RAG scores once per retrieval; it does not stop a search loop."""
    ctx = make_ctx(tmp_path=tmp_path)
    attack = RagAttack({}, ctx)
    assert "early_stop_on_success" not in attack.config
