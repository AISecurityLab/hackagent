# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the TAP search loop (generation module)."""

import json
import logging
import string
import unittest
from concurrent.futures import Future
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.tap import generation
from hackagent.attacks.techniques.tap.generation import (
    TapExecutor,
    _build_init_message,
    _initialize_attacker_router,
    _log_colored,
    _process_target_response,
    _prune_by_score,
    _random_id,
    _resolve_judges_config,
    execute,
)

LOGGER = logging.getLogger("test.tap.generation")
LOGGER.addHandler(logging.NullHandler())


class _SerialPool:
    """ThreadPoolExecutor stand-in that runs work inline, so the TAP search
    loop expands branches in a deterministic order."""

    def __init__(self, max_workers=None):
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - mirrors executor semantics
            future.set_exception(exc)
        return future

    def map(self, fn, iterable):
        return [fn(item) for item in iterable]


def _target_router():
    router = MagicMock()
    router._agent_registry = {"victim-key": object()}
    return router


def _evaluator(on_topic_scores=None, judge_scores=None):
    """Evaluator stub returning canned on-topic and judge scores."""
    evaluator = MagicMock()
    evaluator.evaluate_on_topic.side_effect = lambda rows, cfg: [dict(r) for r in rows]
    evaluator.extract_scores.side_effect = lambda rows, key, default=0: (
        list(on_topic_scores)[: len(rows)]
        if on_topic_scores is not None
        else [1] * len(rows)
    )
    evaluator.score_candidates.side_effect = (
        lambda goal, prompts, responses, cfg, default=0: (
            list(judge_scores)[: len(prompts)]
            if judge_scores is not None
            else [1] * len(prompts)
        )
    )
    return evaluator


def _make_executor(config=None, agent_router=None, evaluator=None):
    """Build a TapExecutor with the attacker router and evaluator stubbed out."""
    attacker_router = MagicMock()
    with (
        patch.object(
            generation,
            "_initialize_attacker_router",
            return_value=(attacker_router, "attacker-key"),
        ),
        patch.object(
            generation, "TapEvaluation", return_value=evaluator or _evaluator()
        ),
    ):
        executor = TapExecutor(
            config=config if config is not None else {},
            client=MagicMock(),
            agent_router=agent_router or _target_router(),
            logger=LOGGER,
        )
    return executor


class TestRandomId(unittest.TestCase):
    def test_default_length_and_alphabet(self):
        node_id = _random_id()

        self.assertEqual(len(node_id), 16)
        self.assertTrue(set(node_id) <= set(string.ascii_letters + string.digits))

    def test_custom_length(self):
        self.assertEqual(len(_random_id(4)), 4)

    def test_ids_are_not_repeated(self):
        self.assertEqual(len({_random_id() for _ in range(50)}), 50)


class TestResolveJudgesConfig(unittest.TestCase):
    def test_list_form_wins(self):
        judges = [{"type": "a"}, {"type": "b"}]

        self.assertEqual(_resolve_judges_config(judges, {"type": "legacy"}), judges)

    def test_legacy_single_judge_is_wrapped(self):
        self.assertEqual(
            _resolve_judges_config(None, {"type": "legacy"}), [{"type": "legacy"}]
        )

    def test_empty_list_falls_back_to_single_judge(self):
        self.assertEqual(
            _resolve_judges_config([], {"type": "legacy"}), [{"type": "legacy"}]
        )

    def test_nothing_configured_returns_empty_list(self):
        self.assertEqual(_resolve_judges_config(None, None), [])
        self.assertEqual(_resolve_judges_config([], None), [])


class TestResolveOnTopicJudgesConfigExtra(unittest.TestCase):
    def test_conflicting_type_is_overridden_with_a_warning(self):
        warn_logger = MagicMock()

        with patch.object(generation.logging, "getLogger", return_value=warn_logger):
            resolved = generation._resolve_on_topic_judges_config(
                {"type": "harmfulness", "identifier": "m"}, None
            )

        self.assertEqual(resolved[0]["type"], "on_topic")
        warn_logger.warning.assert_called_once()
        self.assertIn("overridden", warn_logger.warning.call_args.args[0])

    def test_evaluator_type_key_is_removed(self):
        resolved = generation._resolve_on_topic_judges_config(
            {"evaluator_type": "on_topic", "identifier": "m"}, None
        )

        self.assertNotIn("evaluator_type", resolved[0])
        self.assertEqual(resolved[0]["type"], "on_topic")

    def test_input_config_is_not_mutated(self):
        original = {"identifier": "m", "evaluator_type": "harmfulness"}

        generation._resolve_on_topic_judges_config(original, None)

        self.assertEqual(original["evaluator_type"], "harmfulness")


class TestPruneByScore(unittest.TestCase):
    def test_empty_scores_return_empty_lists(self):
        self.assertEqual(_prune_by_score([], width=3, min_score=1, items=[]), ([], []))

    def test_keeps_highest_scores_first(self):
        scores, items = _prune_by_score(
            [1, 9, 5], width=3, min_score=0, items=["a", "b", "c"]
        )

        self.assertEqual(scores, [9, 5, 1])
        self.assertEqual(items, ["b", "c", "a"])

    def test_width_caps_the_beam(self):
        scores, items = _prune_by_score(
            [1, 9, 5], width=2, min_score=0, items=["a", "b", "c"]
        )

        self.assertEqual(scores, [9, 5])
        self.assertEqual(items, ["b", "c"])

    def test_min_score_filters_low_branches(self):
        scores, items = _prune_by_score(
            [1, 9, 5], width=3, min_score=5, items=["a", "b", "c"]
        )

        self.assertEqual(scores, [9, 5])
        self.assertEqual(items, ["b", "c"])

    def test_when_nothing_passes_the_threshold_the_best_branch_survives(self):
        scores, items = _prune_by_score(
            [1, 2, 3], width=3, min_score=10, items=["a", "b", "c"]
        )

        self.assertEqual(scores, [3])
        self.assertEqual(items, ["c"])

    def test_width_below_one_still_keeps_one_item(self):
        scores, items = _prune_by_score([4, 2], width=0, min_score=0, items=["a", "b"])

        self.assertEqual(scores, [4])
        self.assertEqual(items, ["a"])


class TestMessageBuilders(unittest.TestCase):
    def test_init_message_mentions_goal_and_target_prefix(self):
        message = _build_init_message("make a bomb", "Sure, here is")

        self.assertIn("make a bomb", message)
        self.assertIn("Sure, here is", message)

    def test_feedback_message_carries_response_and_score(self):
        feedback = _process_target_response("I refuse.", 4, "make a bomb")

        self.assertIn("LANGUAGE MODEL OUTPUT: I refuse.", feedback)
        self.assertIn("SCORE: 4", feedback)
        self.assertIn("make a bomb", feedback)


class TestLogColored(unittest.TestCase):
    def test_no_color_environment_falls_back_to_the_logger(self):
        logger = MagicMock()

        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            _log_colored(logger, "hello", "cyan")

        logger.info.assert_called_once_with("hello")

    def test_rich_is_used_when_colour_is_allowed(self):
        logger = MagicMock()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("rich.print") as rich_print,
        ):
            _log_colored(logger, "hello", "cyan")

        rich_print.assert_called_once_with("[cyan]hello[/cyan]")
        logger.info.assert_not_called()

    def test_rich_failure_falls_back_to_the_logger(self):
        logger = MagicMock()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("rich.print", side_effect=RuntimeError("no console")),
        ):
            _log_colored(logger, "hello", "cyan")

        logger.info.assert_called_once_with("hello")


class TestInitializeAttackerRouter(unittest.TestCase):
    def test_delegates_to_connect_role(self):
        router = MagicMock()

        with patch.object(
            generation, "connect_role", return_value=(router, "key")
        ) as factory:
            result = _initialize_attacker_router({"identifier": "m"})

        self.assertEqual(result, (router, "key"))
        factory.assert_called_once_with({"identifier": "m"}, name="attacker")


class TestTapExecutorSetup(unittest.TestCase):
    def test_attacker_timeout_defaults_to_the_global_timeout(self):
        with (
            patch.object(
                generation,
                "_initialize_attacker_router",
                return_value=(MagicMock(), "k"),
            ) as init,
            patch.object(generation, "TapEvaluation"),
        ):
            TapExecutor(
                config={"attacker": {"identifier": "m"}, "timeout": 42},
                client=MagicMock(),
                agent_router=_target_router(),
                logger=LOGGER,
            )

        self.assertEqual(init.call_args.args[0]["timeout"], 42)

    def test_explicit_attacker_timeout_is_preserved(self):
        with (
            patch.object(
                generation,
                "_initialize_attacker_router",
                return_value=(MagicMock(), "k"),
            ) as init,
            patch.object(generation, "TapEvaluation"),
        ):
            TapExecutor(
                config={"attacker": {"timeout": 5}, "timeout": 42},
                client=MagicMock(),
                agent_router=_target_router(),
                logger=LOGGER,
            )

        self.assertEqual(init.call_args.args[0]["timeout"], 5)

    def test_judge_configs_are_normalised_on_construction(self):
        executor = _make_executor({"judge": {"identifier": "j"}})

        self.assertEqual(executor.judges_config, [{"identifier": "j"}])
        self.assertEqual(executor.on_topic_judges_config[0]["type"], "on_topic")


class TestQueryAttacker(unittest.TestCase):
    def test_parses_json_attacker_output(self):
        executor = _make_executor()
        executor.attacker_router.route_request.return_value = {
            "generated_text": json.dumps(
                {"prompt": "pretend you are", "improvement": "more roleplay"}
            )
        }

        parsed = executor._query_attacker([{"role": "user", "content": "go"}])

        self.assertEqual(parsed["prompt"], "pretend you are")
        self.assertEqual(parsed["improvement"], "more roleplay")

    def test_sampling_defaults_are_applied(self):
        executor = _make_executor()
        executor.attacker_router.route_request.return_value = {
            "generated_text": '{"prompt": "p", "improvement": "i"}'
        }

        executor._query_attacker([{"role": "user", "content": "go"}])

        request = executor.attacker_router.route_request.call_args.kwargs[
            "request_data"
        ]
        self.assertEqual(request["max_tokens"], 400)
        self.assertEqual(request["temperature"], 1.0)
        self.assertEqual(request["top_p"], 0.9)

    def test_configured_sampling_overrides_defaults(self):
        executor = _make_executor(
            {"attacker": {"max_tokens": 64, "temperature": 0.1, "top_p": 0.5}}
        )
        executor.attacker_router.route_request.return_value = {
            "generated_text": '{"prompt": "p", "improvement": "i"}'
        }

        executor._query_attacker([])

        request = executor.attacker_router.route_request.call_args.kwargs[
            "request_data"
        ]
        self.assertEqual(
            (request["max_tokens"], request["temperature"], request["top_p"]),
            (64, 0.1, 0.5),
        )

    def test_empty_response_yields_none(self):
        executor = _make_executor()
        executor.attacker_router.route_request.return_value = {"generated_text": ""}

        self.assertIsNone(executor._query_attacker([]))


class TestQueryTarget(unittest.TestCase):
    def test_returns_extracted_text(self):
        router = _target_router()
        router.route_request.return_value = {"generated_text": "victim says hi"}
        executor = _make_executor(agent_router=router)

        self.assertEqual(executor._query_target("prompt"), "victim says hi")
        request = router.route_request.call_args.kwargs
        self.assertEqual(request["registration_key"], "victim-key")
        self.assertEqual(
            request["request_data"]["messages"], [{"role": "user", "content": "prompt"}]
        )

    def test_target_sampling_comes_from_the_top_level_config(self):
        router = _target_router()
        router.route_request.return_value = {"generated_text": "x"}
        executor = _make_executor(
            {"max_tokens": 32, "temperature": 0.2, "top_p": 0.8}, agent_router=router
        )

        executor._query_target("prompt")

        request = router.route_request.call_args.kwargs["request_data"]
        self.assertEqual(
            (request["max_tokens"], request["temperature"], request["top_p"]),
            (32, 0.2, 0.8),
        )

    def test_guardrail_block_returns_the_raw_response(self):
        router = _target_router()
        blocked = {
            "adapter_type": "guardrail",
            "agent_specific_data": {"side": "input"},
        }
        router.route_request.return_value = blocked
        executor = _make_executor(agent_router=router)

        self.assertIs(executor._query_target("prompt"), blocked)


class TestExpandOneBranch(unittest.TestCase):
    def _conv(self):
        return {
            "messages": [{"role": "system", "content": "sys"}],
            "self_id": "parent-id",
            "parent_id": None,
        }

    def test_successful_expansion_records_lineage_and_assistant_turn(self):
        executor = _make_executor()
        executor._query_attacker = MagicMock(
            return_value={"prompt": "p", "improvement": "i"}
        )
        conv = self._conv()

        result = executor._expand_one_branch(2, 3, conv, "next turn", max_attempts=3)

        self.assertEqual(result["branch_index"], 2)
        self.assertEqual(result["stream_index"], 3)
        self.assertEqual(result["conv_copy"]["parent_id"], "parent-id")
        self.assertNotEqual(result["conv_copy"]["self_id"], "parent-id")
        messages = result["conv_copy"]["messages"]
        self.assertEqual(messages[1], {"role": "user", "content": "next turn"})
        self.assertEqual(
            json.loads(messages[2]["content"]), {"prompt": "p", "improvement": "i"}
        )
        # The caller's conversation must not be mutated.
        self.assertEqual(len(conv["messages"]), 1)

    def test_retries_until_the_attacker_output_parses(self):
        executor = _make_executor()
        executor._query_attacker = MagicMock(
            side_effect=[None, None, {"prompt": "p", "improvement": ""}]
        )

        result = executor._expand_one_branch(0, 0, self._conv(), "msg", max_attempts=3)

        self.assertIsNotNone(result)
        self.assertEqual(executor._query_attacker.call_count, 3)

    def test_returns_none_when_every_attempt_fails(self):
        executor = _make_executor()
        executor._query_attacker = MagicMock(return_value=None)

        result = executor._expand_one_branch(0, 0, self._conv(), "msg", max_attempts=2)

        self.assertIsNone(result)
        self.assertEqual(executor._query_attacker.call_count, 2)


class TestRunSingleGoal(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(generation, "ThreadPoolExecutor", _SerialPool)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _executor(self, tap_params, on_topic_scores=None, judge_scores=None):
        evaluator = _evaluator(on_topic_scores, judge_scores)
        config = {"tap_params": tap_params, "target_str": "Sure, here is"}
        executor = _make_executor(config, evaluator=evaluator)
        executor.evaluator = evaluator
        return executor

    def test_single_depth_run_reports_the_best_candidate(self):
        executor = self._executor(
            {
                "depth": 1,
                "width": 2,
                "branching_factor": 1,
                "n_streams": 2,
                "verbose": False,
            },
            # Distinct on-topic scores keep the pruning order deterministic.
            on_topic_scores=[2, 1],
            judge_scores=[3, 8],
        )
        executor._query_attacker = MagicMock(
            side_effect=[
                {"prompt": "weak prompt", "improvement": "a"},
                {"prompt": "strong prompt", "improvement": "b"},
            ]
        )
        executor._query_target = MagicMock(side_effect=["meh", "here you go"])

        result = executor.run_single_goal("goal text", 7)

        self.assertEqual(result["goal"], "goal text")
        self.assertEqual(result["goal_index"], 7)
        self.assertEqual(result["best_score"], 8)
        self.assertEqual(result["best_prompt"], "strong prompt")
        self.assertEqual(result["best_response"], "here you go")
        self.assertEqual(result["iterations_completed"], 1)
        self.assertEqual(result["depth"], 1)

    def test_success_threshold_marks_the_run_successful(self):
        executor = self._executor(
            {"depth": 1, "branching_factor": 1, "n_streams": 1, "verbose": False},
            on_topic_scores=[1],
            judge_scores=[10],
        )
        executor._query_attacker = MagicMock(
            return_value={"prompt": "p", "improvement": "i"}
        )
        executor._query_target = MagicMock(return_value="sure")

        result = executor.run_single_goal("goal", 0)

        self.assertTrue(result["is_success"])

    def test_early_stop_halts_before_the_configured_depth(self):
        executor = self._executor(
            {
                "depth": 5,
                "branching_factor": 1,
                "n_streams": 1,
                "verbose": False,
                "early_stop_on_success": True,
                "success_score_threshold": 5,
            },
            on_topic_scores=[1],
            judge_scores=[7],
        )
        executor._query_attacker = MagicMock(
            return_value={"prompt": "p", "improvement": "i"}
        )
        executor._query_target = MagicMock(return_value="sure")

        result = executor.run_single_goal("goal", 0)

        self.assertEqual(result["iterations_completed"], 1)
        self.assertEqual(executor._query_target.call_count, 1)

    def test_disabled_early_stop_runs_every_depth(self):
        executor = self._executor(
            {
                "depth": 3,
                "branching_factor": 1,
                "n_streams": 1,
                "verbose": False,
                "early_stop_on_success": False,
                "min_judge_prune_score": 0,
            },
            on_topic_scores=[1],
            judge_scores=[10],
        )
        executor._query_attacker = MagicMock(
            return_value={"prompt": "p", "improvement": "i"}
        )
        executor._query_target = MagicMock(return_value="sure")

        result = executor.run_single_goal("goal", 0)

        self.assertEqual(result["iterations_completed"], 3)

    def test_unparseable_attacker_output_stops_the_search(self):
        executor = self._executor(
            {"depth": 3, "branching_factor": 1, "n_streams": 1, "verbose": False}
        )
        executor._query_attacker = MagicMock(return_value=None)
        executor._query_target = MagicMock()

        result = executor.run_single_goal("goal", 0)

        self.assertEqual(result["best_score"], 0)
        self.assertEqual(result["best_prompt"], "")
        executor._query_target.assert_not_called()

    def test_guardrail_dicts_are_not_passed_to_the_judges(self):
        executor = self._executor(
            {"depth": 1, "branching_factor": 1, "n_streams": 1, "verbose": False},
            on_topic_scores=[1],
            judge_scores=[0],
        )
        executor._query_attacker = MagicMock(
            return_value={"prompt": "p", "improvement": "i"}
        )
        executor._query_target = MagicMock(
            return_value={"adapter_type": "guardrail", "generated_text": "blocked"}
        )

        executor.run_single_goal("goal", 0)

        judged_responses = executor.evaluator.score_candidates.call_args.args[2]
        self.assertEqual(judged_responses, [""])

    def test_tracker_receives_candidate_and_summary_traces(self):
        executor = self._executor(
            {"depth": 1, "branching_factor": 1, "n_streams": 2, "verbose": False},
            on_topic_scores=[2, 2],
            judge_scores=[4, 6],
        )
        executor._query_attacker = MagicMock(
            side_effect=[
                {"prompt": "p1", "improvement": "i1"},
                {"prompt": "p2", "improvement": "i2"},
            ]
        )
        executor._query_target = MagicMock(side_effect=["r1", "r2"])
        tracker = MagicMock()
        ctx = MagicMock()

        executor.run_single_goal("goal", 0, goal_tracker=tracker, goal_ctx=ctx)

        self.assertEqual(tracker.add_interaction_trace.call_count, 2)
        trace = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(trace["step_name"], "Depth 1 Candidate")
        self.assertIn("on_topic_score", trace["metadata"])
        summary = tracker.add_custom_trace.call_args.kwargs
        self.assertEqual(summary["step_name"], "Depth 1 Summary")
        self.assertEqual(len(summary["content"]["branches"]), 2)

    def test_progress_bar_is_advanced_per_candidate(self):
        executor = self._executor(
            {"depth": 1, "branching_factor": 1, "n_streams": 2, "verbose": False},
            on_topic_scores=[2, 2],
            judge_scores=[1, 2],
        )
        executor._query_attacker = MagicMock(
            side_effect=[
                {"prompt": "p1", "improvement": ""},
                {"prompt": "p2", "improvement": ""},
            ]
        )
        executor._query_target = MagicMock(side_effect=["r1", "r2"])
        bar = MagicMock()

        executor.run_single_goal("goal", 0, progress_bar=bar, task="t")

        bar.update.assert_called_once()
        self.assertEqual(bar.update.call_args.kwargs["advance"], 2)

    def test_conversation_history_is_trimmed_between_depths(self):
        executor = self._executor(
            {
                "depth": 2,
                "branching_factor": 1,
                "n_streams": 1,
                "keep_last_n": 1,
                "verbose": False,
                "early_stop_on_success": False,
                "min_judge_prune_score": 0,
            },
            on_topic_scores=[1],
            judge_scores=[1],
        )
        seen_lengths = []

        def _attacker(messages):
            seen_lengths.append(len(messages))
            return {"prompt": "p", "improvement": "i"}

        executor._query_attacker = MagicMock(side_effect=_attacker)
        executor._query_target = MagicMock(return_value="r")

        executor.run_single_goal("goal", 0)

        # Depth 1 starts from [system, user]; depth 2 sees the conversation
        # trimmed to 2 * keep_last_n messages plus the new user turn.
        self.assertEqual(seen_lengths, [2, 3])

    def test_verbose_mode_logs_without_failing(self):
        executor = self._executor(
            {"depth": 1, "branching_factor": 1, "n_streams": 1, "verbose": True},
            on_topic_scores=[1],
            judge_scores=[2],
        )
        executor._query_attacker = MagicMock(
            return_value={"prompt": "p", "improvement": "i"}
        )
        executor._query_target = MagicMock(return_value="r")

        with patch.object(generation, "_log_colored") as log_colored:
            result = executor.run_single_goal("goal", 0)

        self.assertEqual(result["best_score"], 2)
        self.assertTrue(log_colored.called)


@contextmanager
def _fake_progress(description, total):
    yield MagicMock(), "task-id"


class TestExecute(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(
            generation, "create_progress_bar", side_effect=_fake_progress
        )
        self.progress = patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, goals, config, executor=None):
        executor = executor or MagicMock()
        executor.run_single_goal.side_effect = lambda **kwargs: {
            "goal": kwargs["goal"],
            "goal_index": kwargs["goal_index"],
            "best_score": 1,
        }
        with patch.object(generation, "TapExecutor", return_value=executor) as cls:
            results = execute(goals, _target_router(), config, LOGGER, MagicMock())
        return results, executor, cls

    def test_no_goals_short_circuits(self):
        with patch.object(generation, "TapExecutor") as cls:
            self.assertEqual(execute([], _target_router(), {}, LOGGER, MagicMock()), [])
        cls.assert_not_called()

    def test_serial_execution_preserves_goal_order(self):
        results, executor, _ = self._run(["g0", "g1", "g2"], {})

        self.assertEqual([r["goal"] for r in results], ["g0", "g1", "g2"])
        self.assertEqual(executor.run_single_goal.call_count, 3)

    def test_goal_index_offset_is_applied(self):
        results, _, _ = self._run(["g0", "g1"], {"_goal_index_offset": 100})

        self.assertEqual([r["goal_index"] for r in results], [100, 101])

    def test_tracker_context_is_looked_up_per_goal(self):
        tracker = MagicMock()
        tracker.get_goal_context.side_effect = lambda idx: f"ctx-{idx}"

        _, executor, _ = self._run(["g0", "g1"], {"_tracker": tracker})

        contexts = [
            call.kwargs["goal_ctx"] for call in executor.run_single_goal.call_args_list
        ]
        self.assertEqual(contexts, ["ctx-0", "ctx-1"])

    def test_parallel_goals_still_return_in_order(self):
        results, executor, _ = self._run(
            ["g0", "g1", "g2"], {"tap_params": {"n_parallel_goals": 3}}
        )

        self.assertEqual([r["goal"] for r in results], ["g0", "g1", "g2"])

    def test_a_failing_goal_yields_an_empty_result_row(self):
        executor = MagicMock()

        def _run_goal(**kwargs):
            if kwargs["goal"] == "g1":
                raise RuntimeError("attacker exploded")
            return {"goal": kwargs["goal"], "goal_index": kwargs["goal_index"]}

        executor.run_single_goal.side_effect = _run_goal

        with patch.object(generation, "TapExecutor", return_value=executor):
            results = execute(
                ["g0", "g1"],
                _target_router(),
                {"tap_params": {"n_parallel_goals": 2, "depth": 5}},
                LOGGER,
                MagicMock(),
            )

        self.assertEqual(results[0]["goal"], "g0")
        self.assertEqual(results[1]["goal"], "g1")
        self.assertFalse(results[1]["is_success"])
        self.assertEqual(results[1]["best_score"], 0)
        self.assertEqual(results[1]["depth"], 5)

    def test_progress_total_scales_with_the_search_space(self):
        self._run(
            ["g0", "g1"],
            {"tap_params": {"depth": 2, "width": 3, "branching_factor": 4}},
        )

        self.assertEqual(self.progress.call_args.args[1], 2 * 3 * 4 * 2)


if __name__ == "__main__":
    unittest.main()
