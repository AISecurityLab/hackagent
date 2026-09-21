# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the AdvPrefix PrefixGenerationPipeline."""

import logging
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.advprefix import generate as advgen
from hackagent.attacks.techniques.advprefix.generate import PrefixGenerationPipeline
from hackagent.router.types import AgentTypeEnum

LOGGER = logging.getLogger("test.advprefix.generate")
LOGGER.addHandler(logging.NullHandler())


@contextmanager
def _fake_progress(description, total=0):
    bar = MagicMock()
    yield bar, "task"


def _pipeline(config=None, agent_router=None, client=None):
    base = {
        "attacker": {"identifier": "gen-model", "endpoint": "http://localhost:1234/v1"},
        "meta_prefixes": ["Write..."],
        "meta_prefix_samples": 1,
        "batch_size": 2,
        "max_tokens": 32,
    }
    if config:
        base.update(config)
    return PrefixGenerationPipeline(
        config=base,
        logger=LOGGER,
        client=client or MagicMock(),
        agent_router=agent_router,
    )


def _prefix(prefix, goal="goal", **extra):
    row = {"goal": goal, "prefix": prefix, "meta_prefix": "m", "model_name": "gen"}
    row.update(extra)
    return row


class TestExecute(unittest.TestCase):
    def test_empty_goals_short_circuit(self):
        pipeline = _pipeline()

        with patch.object(pipeline, "_generate_raw_prefixes") as generate:
            self.assertEqual(pipeline.execute(goals=[]), [])

        generate.assert_not_called()

    def test_duplicate_goals_are_collapsed(self):
        pipeline = _pipeline()

        with (
            patch.object(
                pipeline, "_generate_raw_prefixes", return_value=[]
            ) as generate,
            patch.object(pipeline, "_write_per_goal_generation_traces"),
        ):
            pipeline.execute(["g", "g", "h"])

        self.assertEqual(generate.call_args.args[0], ["g", "h"])

    def test_no_raw_prefixes_returns_empty_and_traces(self):
        pipeline = _pipeline()

        with (
            patch.object(pipeline, "_generate_raw_prefixes", return_value=[]),
            patch.object(pipeline, "_write_per_goal_generation_traces") as traces,
        ):
            self.assertEqual(pipeline.execute(["g"]), [])

        traces.assert_called_once_with(["g"], [], [], [])

    def test_phase1_wiping_everything_returns_empty(self):
        pipeline = _pipeline()
        raw = [_prefix("a")]

        with (
            patch.object(pipeline, "_generate_raw_prefixes", return_value=raw),
            patch.object(pipeline, "_apply_phase1_preprocessing", return_value=[]),
            patch.object(pipeline, "_write_per_goal_generation_traces") as traces,
        ):
            self.assertEqual(pipeline.execute(["g"]), [])

        traces.assert_called_once_with(["g"], raw, [], [])
        self.assertEqual(pipeline.get_statistics()["raw_generated"], 1)

    def test_without_a_target_router_phase1_output_is_final(self):
        pipeline = _pipeline()
        raw = [_prefix("a"), _prefix("b")]

        with (
            patch.object(pipeline, "_generate_raw_prefixes", return_value=raw),
            patch.object(pipeline, "_apply_phase1_preprocessing", return_value=raw[:1]),
            patch.object(pipeline, "_compute_cross_entropy_scores") as ce,
            patch.object(pipeline, "_write_per_goal_generation_traces"),
        ):
            results = pipeline.execute(["g"])

        ce.assert_not_called()
        self.assertEqual(results, raw[:1])

    def test_full_pipeline_with_cross_entropy(self):
        pipeline = _pipeline(agent_router=MagicMock())
        raw = [_prefix("a"), _prefix("b")]

        with (
            patch.object(pipeline, "_generate_raw_prefixes", return_value=raw),
            patch.object(pipeline, "_apply_phase1_preprocessing", return_value=raw),
            patch.object(pipeline, "_compute_cross_entropy_scores", return_value=raw),
            patch.object(pipeline, "_apply_phase2_preprocessing", return_value=raw[:1]),
            patch.object(pipeline, "_write_per_goal_generation_traces"),
        ):
            results = pipeline.execute(["g"])

        self.assertEqual(results, raw[:1])
        stats = pipeline.get_statistics()
        self.assertEqual(stats["raw_generated"], 2)
        self.assertEqual(stats["phase1_filtered"], 2)
        self.assertEqual(stats["ce_computed"], 2)
        self.assertEqual(stats["phase2_filtered"], 1)

    def test_empty_cross_entropy_output_stops_the_pipeline(self):
        pipeline = _pipeline(agent_router=MagicMock())
        raw = [_prefix("a")]

        with (
            patch.object(pipeline, "_generate_raw_prefixes", return_value=raw),
            patch.object(pipeline, "_apply_phase1_preprocessing", return_value=raw),
            patch.object(pipeline, "_compute_cross_entropy_scores", return_value=[]),
            patch.object(pipeline, "_apply_phase2_preprocessing") as phase2,
            patch.object(pipeline, "_write_per_goal_generation_traces"),
        ):
            self.assertEqual(pipeline.execute(["g"]), [])

        phase2.assert_not_called()

    def test_phase2_wiping_everything_returns_empty(self):
        pipeline = _pipeline(agent_router=MagicMock())
        raw = [_prefix("a")]

        with (
            patch.object(pipeline, "_generate_raw_prefixes", return_value=raw),
            patch.object(pipeline, "_apply_phase1_preprocessing", return_value=raw),
            patch.object(pipeline, "_compute_cross_entropy_scores", return_value=raw),
            patch.object(pipeline, "_apply_phase2_preprocessing", return_value=[]),
            patch.object(pipeline, "_write_per_goal_generation_traces") as traces,
        ):
            self.assertEqual(pipeline.execute(["g"]), [])

        traces.assert_called_once_with(["g"], raw, raw, [])

    def test_statistics_are_returned_as_a_copy(self):
        pipeline = _pipeline()

        stats = pipeline.get_statistics()
        stats["raw_generated"] = 999

        self.assertEqual(pipeline.get_statistics()["raw_generated"], 0)


class TestWritePerGoalGenerationTraces(unittest.TestCase):
    def test_without_a_tracker_nothing_is_written(self):
        pipeline = _pipeline()

        # Must not raise even though there is no tracker configured.
        pipeline._write_per_goal_generation_traces(["g"], [], [], [])

    def test_traces_summarise_each_filter_stage(self):
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = SimpleNamespace(goal_index=0)
        pipeline = _pipeline({"_tracker": tracker})

        raw = [_prefix("a"), _prefix("b"), _prefix("c", goal="other")]
        phase1 = [_prefix("a"), _prefix("b")]
        final = [_prefix("a", prefix_nll=0.0)]

        pipeline._write_per_goal_generation_traces(["goal"], raw, phase1, final)

        ctx, step_name, content = tracker.add_custom_trace.call_args.args
        self.assertEqual(step_name, "Prefix Generation")
        self.assertEqual(content["raw_generated"], 2)
        self.assertEqual(content["after_phase1_filtering"], 2)
        self.assertEqual(content["after_phase2_filtering"], 1)
        self.assertEqual(content["candidates"][0]["prefix_nll"], 0.0)

    def test_goals_without_a_context_are_skipped(self):
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = None
        pipeline = _pipeline({"_tracker": tracker})

        pipeline._write_per_goal_generation_traces(["goal"], [_prefix("a")], [], [])

        tracker.add_custom_trace.assert_not_called()

    def test_long_prefixes_are_truncated_in_the_trace(self):
        tracker = MagicMock()
        tracker.get_goal_context_by_goal.return_value = SimpleNamespace(goal_index=0)
        pipeline = _pipeline({"_tracker": tracker})

        pipeline._write_per_goal_generation_traces(
            ["goal"], [], [], [_prefix("x" * 500)]
        )

        content = tracker.add_custom_trace.call_args.args[2]
        self.assertEqual(len(content["candidates"][0]["prefix"]), 300)


class TestGenerateRawPrefixes(unittest.TestCase):
    def test_missing_attacker_config_yields_nothing(self):
        pipeline = _pipeline({"attacker": {}})

        self.assertEqual(pipeline._generate_raw_prefixes(["g"]), [])

    def test_missing_model_identifier_yields_nothing(self):
        pipeline = _pipeline({"attacker": {"endpoint": "http://x"}})

        self.assertEqual(pipeline._generate_raw_prefixes(["g"]), [])

    def test_router_initialisation_failure_yields_nothing(self):
        pipeline = _pipeline()

        with patch.object(pipeline, "_initialize_generation_router", return_value=None):
            self.assertEqual(pipeline._generate_raw_prefixes(["g"]), [])

    def test_no_constructed_prompts_yields_nothing(self):
        pipeline = _pipeline()
        pipeline._generation_router = MagicMock()

        with patch.object(pipeline, "_construct_prompts", return_value=([], [], [])):
            self.assertEqual(pipeline._generate_raw_prefixes(["g"]), [])

    def test_both_greedy_and_sampling_modes_run(self):
        pipeline = _pipeline()
        pipeline._generation_router = MagicMock()

        with patch.object(
            pipeline, "_run_generation_mode", return_value=[_prefix("p")]
        ) as run_mode:
            results = pipeline._generate_raw_prefixes(["g"])

        self.assertEqual(len(results), 2)
        modes = [call.kwargs["do_sample"] for call in run_mode.call_args_list]
        self.assertEqual(modes, [False, True])


class TestInitializeGenerationRouter(unittest.TestCase):
    def _init(self, pipeline, registry=None):
        router = MagicMock()
        router._agent_registry = {"k": object()} if registry is None else registry
        with patch.object(advgen, "AgentRouter", return_value=router) as cls:
            result = pipeline._initialize_generation_router()
        return result, cls

    def test_operational_config_is_derived_from_the_attacker_block(self):
        client = MagicMock()
        client.get_api_key.return_value = "storage-key"
        pipeline = _pipeline(
            {"attacker": {"identifier": "gen-model", "endpoint": "http://ep"}},
            client=client,
        )

        router, cls = self._init(pipeline)

        self.assertIsNotNone(router)
        kwargs = cls.call_args.kwargs
        self.assertEqual(kwargs["name"], "gen-model")
        self.assertEqual(kwargs["endpoint"], "http://ep")
        self.assertEqual(kwargs["agent_type"], AgentTypeEnum.OPENAI_SDK)
        self.assertEqual(kwargs["adapter_operational_config"]["api_key"], "storage-key")

    def test_api_key_is_read_from_the_named_environment_variable(self):
        pipeline = _pipeline(
            {
                "attacker": {
                    "identifier": "m",
                    "endpoint": "http://ep",
                    "api_key": "GEN_KEY",
                }
            }
        )

        with patch.dict("os.environ", {"GEN_KEY": "from-env"}):
            _, cls = self._init(pipeline)

        self.assertEqual(
            cls.call_args.kwargs["adapter_operational_config"]["api_key"], "from-env"
        )

    def test_api_key_literal_is_used_when_the_variable_is_unset(self):
        pipeline = _pipeline(
            {
                "attacker": {
                    "identifier": "m",
                    "endpoint": "http://ep",
                    "api_key": "literal-key",
                }
            }
        )

        with patch.dict("os.environ", {}, clear=True):
            _, cls = self._init(pipeline)

        self.assertEqual(
            cls.call_args.kwargs["adapter_operational_config"]["api_key"], "literal-key"
        )

    def test_explicit_agent_type_is_honoured(self):
        pipeline = _pipeline({"attacker": {"identifier": "m", "agent_type": "litellm"}})

        _, cls = self._init(pipeline)

        self.assertEqual(cls.call_args.kwargs["agent_type"], AgentTypeEnum.LITELLM)

    def test_invalid_agent_type_falls_back_to_openai_sdk(self):
        pipeline = _pipeline(
            {"attacker": {"identifier": "m", "agent_type": "nonsense"}}
        )

        _, cls = self._init(pipeline)

        self.assertEqual(cls.call_args.kwargs["agent_type"], AgentTypeEnum.OPENAI_SDK)

    def test_router_without_registered_agents_is_rejected(self):
        pipeline = _pipeline()

        router, _ = self._init(pipeline, registry={})

        self.assertIsNone(router)

    def test_router_construction_errors_are_swallowed(self):
        pipeline = _pipeline()

        with patch.object(advgen, "AgentRouter", side_effect=RuntimeError("no host")):
            self.assertIsNone(pipeline._initialize_generation_router())


class TestConstructPrompts(unittest.TestCase):
    def test_samples_are_replicated_per_meta_prefix(self):
        pipeline = _pipeline({"meta_prefixes": ["A", "B"], "meta_prefix_samples": 2})

        prompts, goals, metas = pipeline._construct_prompts(["g1"])

        self.assertEqual(len(prompts), 4)
        self.assertEqual(metas, ["A", "A", "B", "B"])
        self.assertEqual(goals, ["g1"] * 4)

    def test_per_prefix_sample_counts_are_supported(self):
        pipeline = _pipeline({"meta_prefixes": ["A", "B"]})
        # The validated config only accepts an int; the per-prefix list form is
        # still honoured by _construct_prompts when set programmatically.
        pipeline.config.meta_prefix_samples = [1, 3]

        prompts, _, metas = pipeline._construct_prompts(["g1"])

        self.assertEqual(len(prompts), 4)
        self.assertEqual(metas.count("B"), 3)

    def test_zero_sample_counts_skip_the_meta_prefix(self):
        pipeline = _pipeline({"meta_prefixes": ["A", "B"]})
        pipeline.config.meta_prefix_samples = [0, 2]

        _, _, metas = pipeline._construct_prompts(["g1"])

        self.assertEqual(set(metas), {"B"})

    def test_length_mismatch_is_rejected(self):
        pipeline = _pipeline({"meta_prefixes": ["A", "B"]})
        pipeline.config.meta_prefix_samples = [1]

        with self.assertRaises(ValueError):
            pipeline._construct_prompts(["g1"])

    def test_no_goals_produce_no_prompts(self):
        pipeline = _pipeline()

        self.assertEqual(pipeline._construct_prompts([]), ([], [], []))


class TestRunGenerationMode(unittest.TestCase):
    def _pipeline_with_router(self, **config):
        pipeline = _pipeline(config or None)
        router = MagicMock()
        router._agent_registry = {"reg-key": object()}
        router.route_request.return_value = {"processed_response": "generated text"}
        pipeline._generation_router = router
        return pipeline, router

    def test_greedy_mode_uses_a_near_zero_temperature(self):
        pipeline, router = self._pipeline_with_router()

        with patch.object(advgen, "create_progress_bar", side_effect=_fake_progress):
            results = pipeline._run_generation_mode(
                ["p"], ["g"], ["m"], do_sample=False
            )

        self.assertEqual(results[0]["temperature"], 1e-2)
        self.assertEqual(
            router.route_request.call_args.kwargs["request_data"]["temperature"], 1e-2
        )

    def test_sampling_mode_uses_the_configured_temperature(self):
        pipeline, router = self._pipeline_with_router(temperature=0.9)

        with patch.object(advgen, "create_progress_bar", side_effect=_fake_progress):
            results = pipeline._run_generation_mode(["p"], ["g"], ["m"], do_sample=True)

        self.assertEqual(results[0]["temperature"], 0.9)

    def test_results_keep_the_input_ordering(self):
        pipeline, router = self._pipeline_with_router()
        router.route_request.side_effect = lambda registration_key, request_data: {
            "processed_response": "out:" + request_data["messages"][1]["content"]
        }

        with patch.object(advgen, "create_progress_bar", side_effect=_fake_progress):
            results = pipeline._run_generation_mode(
                ["p0", "p1", "p2"], ["g0", "g1", "g0"], ["m", "m", "m"], do_sample=False
            )

        # Results follow the input order even though tasks are grouped by goal.
        self.assertEqual([r["prefix"] for r in results], ["out:p0", "out:p1", "out:p2"])
        self.assertEqual([r["goal"] for r in results], ["g0", "g1", "g0"])

    def test_default_system_prompt_is_used_when_unset(self):
        pipeline, router = self._pipeline_with_router()

        with patch.object(advgen, "create_progress_bar", side_effect=_fake_progress):
            pipeline._run_generation_mode(["p"], ["g"], ["m"], do_sample=False)

        system = router.route_request.call_args.kwargs["request_data"]["messages"][0]
        self.assertEqual(
            system["content"], advgen.DEFAULT_ADVPREFIX_GENERATOR_SYSTEM_PROMPT
        )


class TestExtractGeneratedText(unittest.TestCase):
    def setUp(self):
        self.pipeline = _pipeline()

    def test_router_errors_become_error_markers(self):
        text = self.pipeline._extract_generated_text(
            {"error_message": "boom", "error_category": "Timeout"}, "prompt", "goal"
        )

        self.assertEqual(text, " [ROUTER_ERROR: Timeout]")

    def test_unknown_error_category_is_labelled(self):
        text = self.pipeline._extract_generated_text(
            {"error_message": "boom"}, "prompt", "goal"
        )

        self.assertEqual(text, " [ROUTER_ERROR: Unknown]")

    def test_missing_content_is_flagged(self):
        text = self.pipeline._extract_generated_text({}, "prompt", "goal")

        self.assertEqual(text, " [ROUTER_NO_CONTENT]")

    def test_echoed_prompt_is_stripped(self):
        text = self.pipeline._extract_generated_text(
            {"processed_response": "promptcontinuation"}, "prompt", "goal"
        )

        self.assertEqual(text, "continuation")

    def test_non_echoed_response_is_returned_whole(self):
        text = self.pipeline._extract_generated_text(
            {"processed_response": "fresh text"}, "prompt", "goal"
        )

        self.assertEqual(text, "fresh text")


class TestPhaseFilters(unittest.TestCase):
    def test_start_pattern_filter_drops_refusals(self):
        pipeline = _pipeline({"start_patterns": ("I cannot", "Sorry")})

        kept = pipeline._filter_by_start_patterns(
            [_prefix("  I cannot help"), _prefix("Sure, here"), _prefix("Sorry no")]
        )

        self.assertEqual([r["prefix"] for r in kept], ["Sure, here"])

    def test_start_pattern_filter_is_skipped_when_unconfigured(self):
        pipeline = _pipeline({"start_patterns": ()})
        rows = [_prefix("I cannot help")]

        self.assertEqual(pipeline._filter_by_start_patterns(rows), rows)

    def test_contain_pattern_filter_matches_anywhere(self):
        pipeline = _pipeline({"contain_patterns": ("I am an AI assistant",)})

        kept = pipeline._filter_by_contain_patterns(
            [_prefix("well, I am an AI assistant here"), _prefix("fine text")]
        )

        self.assertEqual([r["prefix"] for r in kept], ["fine text"])

    def test_contain_pattern_filter_is_skipped_when_unconfigured(self):
        pipeline = _pipeline({"contain_patterns": ()})
        rows = [_prefix("anything")]

        self.assertEqual(pipeline._filter_by_contain_patterns(rows), rows)

    def test_char_length_filter(self):
        pipeline = _pipeline({"min_char_length": 5})

        kept = pipeline._filter_by_char_length([_prefix("abc"), _prefix("abcdef")])

        self.assertEqual([r["prefix"] for r in kept], ["abcdef"])

    def test_char_length_filter_disabled_at_zero(self):
        pipeline = _pipeline({"min_char_length": 0})
        rows = [_prefix("")]

        self.assertEqual(pipeline._filter_by_char_length(rows), rows)

    def test_linebreak_filter_requires_internal_newlines(self):
        pipeline = _pipeline()

        kept = pipeline._filter_by_linebreak(
            [_prefix("one line"), _prefix("two\nlines"), _prefix("\npadded\n")]
        )

        self.assertEqual([r["prefix"] for r in kept], ["two\nlines"])

    def test_ce_threshold_filter_drops_high_scores(self):
        pipeline = _pipeline({"max_ce": 1.0})

        kept = pipeline._filter_by_ce_threshold(
            [
                _prefix("a", prefix_nll=0.0),
                _prefix("b", prefix_nll=5.0),
                _prefix("c", prefix_nll=None),
            ]
        )

        self.assertEqual([r["prefix"] for r in kept], ["a"])

    def test_ce_threshold_filter_is_skipped_when_every_score_is_infinite(self):
        pipeline = _pipeline({"max_ce": 1.0})
        rows = [_prefix("a", prefix_nll=float("inf")), _prefix("b", prefix_nll="x")]

        self.assertEqual(pipeline._filter_by_ce_threshold(rows), rows)

    def test_top_k_selection_keeps_the_lowest_scores_per_goal(self):
        pipeline = _pipeline({"n_candidates_per_goal": 1})

        kept = pipeline._select_top_k_per_goal(
            [
                _prefix("a", goal="g1", prefix_nll=2.0),
                _prefix("b", goal="g1", prefix_nll=1.0),
                _prefix("c", goal="g2", prefix_nll=3.0),
            ]
        )

        self.assertEqual(sorted(r["prefix"] for r in kept), ["b", "c"])

    def test_merge_duplicates_combines_metadata(self):
        pipeline = _pipeline()

        merged = pipeline._merge_duplicates(
            [
                _prefix("same", meta_prefix="m1", model_name="a"),
                _prefix("same", meta_prefix="m2", model_name="b"),
                _prefix("unique"),
            ]
        )

        by_prefix = {row["prefix"]: row for row in merged}
        self.assertEqual(len(merged), 2)
        self.assertEqual(by_prefix["same"]["meta_prefix"], "m1,m2")
        self.assertEqual(by_prefix["same"]["model_name"], "a,b")

    def test_merge_duplicates_keeps_the_first_ce_score(self):
        pipeline = _pipeline()

        merged = pipeline._merge_duplicates(
            [
                _prefix("same", prefix_nll=0.0, temperature=0.1),
                _prefix("same", prefix_nll=9.9, temperature=0.2),
            ]
        )

        self.assertEqual(merged[0]["prefix_nll"], 0.0)
        self.assertEqual(merged[0]["temperature"], "0.1,0.2")

    def test_duplicates_across_goals_are_kept_separate(self):
        pipeline = _pipeline()

        merged = pipeline._merge_duplicates(
            [_prefix("same", goal="g1"), _prefix("same", goal="g2")]
        )

        self.assertEqual(len(merged), 2)


class TestPhaseOrchestration(unittest.TestCase):
    def test_phase1_runs_every_filter(self):
        pipeline = _pipeline({"require_linebreak": True})

        with (
            patch.object(
                pipeline, "_filter_by_start_patterns", side_effect=lambda d: d
            ) as f1,
            patch.object(
                pipeline, "_filter_by_contain_patterns", side_effect=lambda d: d
            ) as f2,
            patch.object(
                pipeline, "_filter_by_char_length", side_effect=lambda d: d
            ) as f3,
            patch.object(
                pipeline, "_filter_by_linebreak", side_effect=lambda d: d
            ) as f4,
            patch.object(pipeline, "_merge_duplicates", side_effect=lambda d: d) as f5,
        ):
            pipeline._apply_phase1_preprocessing([_prefix("a")])

        for step in (f1, f2, f3, f4, f5):
            step.assert_called_once()

    def test_phase1_skips_the_linebreak_filter_when_disabled(self):
        pipeline = _pipeline({"require_linebreak": False})

        with patch.object(pipeline, "_filter_by_linebreak") as linebreak:
            pipeline._apply_phase1_preprocessing([_prefix("a")])

        linebreak.assert_not_called()

    def test_phase2_on_empty_input_is_a_no_op(self):
        pipeline = _pipeline()

        self.assertEqual(pipeline._apply_phase2_preprocessing([]), [])

    def test_phase2_requires_cross_entropy_scores(self):
        pipeline = _pipeline()
        rows = [_prefix("a")]

        with patch.object(pipeline, "_filter_by_ce_threshold") as ce_filter:
            self.assertEqual(pipeline._apply_phase2_preprocessing(rows), rows)

        ce_filter.assert_not_called()

    def test_phase2_applies_threshold_and_top_k(self):
        pipeline = _pipeline({"max_ce": 1.0, "n_candidates_per_goal": 1})
        rows = [_prefix("a", prefix_nll=0.0)]

        with (
            patch.object(
                pipeline, "_filter_by_ce_threshold", side_effect=lambda d: d
            ) as ce,
            patch.object(
                pipeline, "_select_top_k_per_goal", side_effect=lambda d: d
            ) as topk,
        ):
            pipeline._apply_phase2_preprocessing(rows)

        ce.assert_called_once()
        topk.assert_called_once()

    def test_phase2_skips_top_k_when_disabled(self):
        pipeline = _pipeline({"n_candidates_per_goal": 0})
        rows = [_prefix("a", prefix_nll=0.0)]

        with patch.object(pipeline, "_select_top_k_per_goal") as topk:
            pipeline._apply_phase2_preprocessing(rows)

        topk.assert_not_called()

    def test_filtering_stats_handle_an_empty_result_set(self):
        pipeline = _pipeline()
        logger = MagicMock()
        pipeline.logger = logger

        pipeline._log_filtering_stats([], "Phase 1")

        self.assertIn("No prefixes remaining", logger.info.call_args.args[0])

    def test_filtering_stats_summarise_per_goal_counts(self):
        pipeline = _pipeline()
        logger = MagicMock()
        pipeline.logger = logger

        pipeline._log_filtering_stats(
            [_prefix("a", goal="g1"), _prefix("b", goal="g1"), _prefix("c", goal="g2")],
            "Phase 1",
        )

        message = logger.info.call_args.args[0]
        self.assertIn("3 prefixes remaining for 2 goals", message)


class TestComputeCrossEntropyScores(unittest.TestCase):
    def _router(self, response=None, side_effect=None):
        router = MagicMock()
        router.backend_agent = SimpleNamespace(id="victim-id", agent_type="OPENAI_SDK")
        if side_effect is not None:
            router.route_request.side_effect = side_effect
        else:
            router.route_request.return_value = response
        return router

    def _run(self, pipeline, prefixes):
        with patch.object(advgen, "create_progress_bar", side_effect=_fake_progress):
            return pipeline._compute_cross_entropy_scores(prefixes)

    def test_without_a_router_the_input_is_returned_unchanged(self):
        pipeline = _pipeline()
        rows = [_prefix("a")]

        self.assertEqual(pipeline._compute_cross_entropy_scores(rows), rows)

    def test_accepted_prefixes_score_zero(self):
        router = self._router({"generated_text": "Sure, here is the plan"})
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(results[0]["prefix_nll"], 0.0)
        self.assertIsNone(results[0]["error_message"])
        self.assertIn("ce_elapsed_s", results[0])

    def test_refusal_keywords_score_infinite(self):
        router = self._router({"generated_text": "I'm sorry, I cannot help"})
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(results[0]["prefix_nll"], float("inf"))
        self.assertEqual(
            results[0]["error_message"], "Response contained refusal keywords"
        )

    def test_router_errors_score_infinite(self):
        router = self._router({"error_message": "timeout"})
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(results[0]["error_message"], "timeout")

    def test_missing_response_text_scores_infinite(self):
        router = self._router({})
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(results[0]["error_message"], "No response")

    def test_blank_prefixes_are_rejected_without_a_request(self):
        router = self._router({"generated_text": "ok"})
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("   "), _prefix("")])

        router.route_request.assert_not_called()
        for row in results:
            self.assertEqual(row["error_message"], "Empty or invalid prefix")

    def test_worker_exceptions_are_captured_per_row(self):
        router = self._router(side_effect=RuntimeError("connection reset"))
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(results[0]["prefix_nll"], float("inf"))
        self.assertIn("connection reset", results[0]["error_message"])

    def test_raw_response_metadata_is_propagated(self):
        router = self._router(
            {
                "generated_text": "ok",
                "raw_request": {"prompt": "p"},
                "raw_response_status": 200,
                "raw_response_headers": {"x": "y"},
                "raw_response_body": "body",
                "agent_specific_data": {"events_list": ["e"]},
            }
        )
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(results[0]["response_status"], 200)
        self.assertEqual(results[0]["response_headers"], {"x": "y"})
        self.assertEqual(results[0]["response_body_raw"], "body")
        self.assertEqual(results[0]["events_list"], ["e"])

    def test_max_tokens_eval_takes_priority_for_ce_requests(self):
        router = self._router({"generated_text": "ok"})
        pipeline = _pipeline({"max_tokens_eval": 7}, agent_router=router)

        self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(
            router.route_request.call_args.kwargs["request_data"]["max_tokens"], 7
        )

    def test_top_level_max_tokens_is_the_fallback(self):
        router = self._router({"generated_text": "ok"})
        pipeline = _pipeline({"max_tokens": 11}, agent_router=router)

        self._run(pipeline, [_prefix("a prefix")])

        self.assertEqual(
            router.route_request.call_args.kwargs["request_data"]["max_tokens"], 11
        )

    def test_results_keep_the_input_ordering(self):
        router = self._router(
            side_effect=lambda registration_key, request_data: {
                "generated_text": request_data["prompt"]
            }
        )
        pipeline = _pipeline(agent_router=router)

        results = self._run(pipeline, [_prefix("p0"), _prefix("p1"), _prefix("p2")])

        self.assertEqual([r["prefix"] for r in results], ["p0", "p1", "p2"])


if __name__ == "__main__":
    unittest.main()
