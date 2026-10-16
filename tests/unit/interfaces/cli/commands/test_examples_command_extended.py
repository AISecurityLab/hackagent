# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent examples` command helpers and subcommands."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from hackagent.interfaces.cli.commands import examples as ex
from hackagent.interfaces.cli.commands.examples import (
    _ensure_ollama_models,
    _get_installed_ollama_models,
    _get_repo_root,
    _is_ollama_running,
    _load_ollama_demo_module,
    _preflight_ollama_requirements,
    _resolve_example_dir,
    _run_hackagent_cli_command,
    _run_python_script,
    _start_background_python,
    _stop_background_process,
    _wait_for_tcp_port,
    db_tool,
    examples,
    ollama,
    pc_tool,
    quick_evaluation,
    rag_example,
    web_example,
)


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["cmd"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestRepoLayoutHelpers(unittest.TestCase):
    def test_repo_root_contains_the_package(self):
        root = _get_repo_root()

        self.assertTrue((root / "hackagent").is_dir())

    def test_example_directory_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            example = Path(tmp) / "examples" / "demo"
            example.mkdir(parents=True)
            (example / "demo.py").write_text("")

            with patch.object(ex, "_get_repo_root", return_value=Path(tmp)):
                resolved = _resolve_example_dir("demo", required_files=("demo.py",))

        self.assertEqual(resolved, example)

    def test_missing_required_files_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "examples" / "demo").mkdir(parents=True)

            with patch.object(ex, "_get_repo_root", return_value=Path(tmp)):
                with self.assertRaises(click.ClickException) as ctx:
                    _resolve_example_dir("demo", required_files=("demo.py",))

        self.assertIn("Required files", str(ctx.exception))
        # Compare with POSIX separators so Windows `demo\demo.py` still matches.
        self.assertIn(
            (Path("demo") / "demo.py").as_posix(),
            str(ctx.exception).replace("\\", "/"),
        )

    def test_missing_directory_lists_the_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ex, "_get_repo_root", return_value=Path(tmp)):
                with self.assertRaises(click.ClickException) as ctx:
                    _resolve_example_dir("nowhere")

        self.assertIn("not found", str(ctx.exception))


class TestScriptRunners(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.script = Path(self.tmp.name) / "run.py"
        self.script.write_text("print('hi')")

    def test_script_is_run_from_its_own_directory(self):
        with patch("subprocess.run", return_value=_completed()) as run:
            _run_python_script(self.script, env={"A": "B"})

        self.assertEqual(run.call_args.kwargs["cwd"], str(self.script.parent))
        self.assertEqual(run.call_args.kwargs["env"], {"A": "B"})

    def test_missing_script_is_reported(self):
        with self.assertRaises(click.ClickException):
            _run_python_script(Path(self.tmp.name) / "missing.py")

    def test_failing_script_is_reported(self):
        with patch("subprocess.run", return_value=_completed(returncode=3)):
            with self.assertRaises(click.ClickException) as ctx:
                _run_python_script(self.script)

        self.assertIn("exit code 3", str(ctx.exception))

    def test_cli_command_is_invoked_as_a_module(self):
        with patch("subprocess.run", return_value=_completed()) as run:
            _run_hackagent_cli_command(["scan", "http://x"])

        self.assertEqual(
            run.call_args.args[0][1:3], ["-m", "hackagent.interfaces.cli.main"]
        )

    def test_failing_cli_command_is_reported(self):
        with patch("subprocess.run", return_value=_completed(returncode=1)):
            with self.assertRaises(click.ClickException) as ctx:
                _run_hackagent_cli_command(["scan"])

        self.assertIn("hackagent scan", str(ctx.exception))


class TestBackgroundProcesses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.script = Path(self.tmp.name) / "agent.py"
        self.script.write_text("")

    def test_process_is_started_in_the_script_directory(self):
        process = MagicMock()

        with patch("subprocess.Popen", return_value=process) as popen:
            started = _start_background_python(self.script, "agent")

        self.assertIs(started, process)
        self.assertEqual(popen.call_args.kwargs["cwd"], str(self.script.parent))

    def test_missing_script_is_reported(self):
        with self.assertRaises(click.ClickException):
            _start_background_python(Path(self.tmp.name) / "none.py", "agent")

    def test_spawn_failure_is_reported(self):
        with patch("subprocess.Popen", side_effect=OSError("no exec")):
            with self.assertRaises(click.ClickException) as ctx:
                _start_background_python(self.script, "agent")

        self.assertIn("Failed to start agent", str(ctx.exception))

    def test_already_exited_process_is_not_terminated(self):
        process = MagicMock()
        process.poll.return_value = 0

        _stop_background_process(process, "agent")

        process.terminate.assert_not_called()

    def test_running_process_is_terminated(self):
        process = MagicMock()
        process.poll.return_value = None

        _stop_background_process(process, "agent")

        process.terminate.assert_called_once()
        process.kill.assert_not_called()

    def test_unresponsive_process_is_killed(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]

        _stop_background_process(process, "agent")

        process.kill.assert_called_once()


class TestWaitForTcpPort(unittest.TestCase):
    def _socket(self, connect_error=None):
        sock = MagicMock()
        entered = sock.__enter__.return_value
        if connect_error is not None:
            entered.connect.side_effect = connect_error
        return sock

    def test_returns_as_soon_as_the_port_accepts(self):
        with patch("socket.socket", return_value=self._socket()):
            _wait_for_tcp_port("127.0.0.1", 5001, timeout_seconds=5)

    def test_exited_process_fails_fast(self):
        process = MagicMock()
        process.poll.return_value = 1
        process.returncode = 1

        with self.assertRaises(click.ClickException) as ctx:
            _wait_for_tcp_port(
                "127.0.0.1", 5001, 5, process=process, process_name="agent"
            )

        self.assertIn("exited before becoming ready", str(ctx.exception))

    def test_timeout_is_reported(self):
        with (
            patch("socket.socket", return_value=self._socket(OSError("refused"))),
            patch.object(ex.time, "sleep"),
            patch.object(ex.time, "monotonic", side_effect=[0.0, 0.5, 10.0]),
        ):
            with self.assertRaises(click.ClickException) as ctx:
                _wait_for_tcp_port("127.0.0.1", 5001, 1, process_name="agent")

        self.assertIn("did not become ready", str(ctx.exception))


class TestOllamaProbes(unittest.TestCase):
    def test_running_server_is_detected(self):
        with patch.object(ex, "urlopen") as urlopen:
            self.assertTrue(_is_ollama_running("http://localhost:11434"))

        self.assertEqual(urlopen.call_args.args[0], "http://localhost:11434/api/tags")

    def test_trailing_slash_endpoints_are_handled(self):
        with patch.object(ex, "urlopen") as urlopen:
            _is_ollama_running("http://localhost:11434/")

        self.assertEqual(urlopen.call_args.args[0], "http://localhost:11434/api/tags")

    def test_unreachable_server_is_detected(self):
        with patch.object(ex, "urlopen", side_effect=ex.URLError("refused")):
            self.assertFalse(_is_ollama_running("http://localhost:11434"))

    def test_installed_models_skip_the_header_row(self):
        stdout = "NAME    ID   SIZE\ngemma3:4b  abc  1GB\nllama3:8b  def  2GB\n"

        with patch("subprocess.run", return_value=_completed(stdout=stdout)):
            models = _get_installed_ollama_models()

        self.assertEqual(models, {"gemma3:4b", "llama3:8b"})

    def test_ollama_list_failure_is_reported(self):
        with patch(
            "subprocess.run", return_value=_completed(returncode=1, stderr="no daemon")
        ):
            with self.assertRaises(click.ClickException) as ctx:
                _get_installed_ollama_models()

        self.assertIn("no daemon", str(ctx.exception))


class TestEnsureOllamaModels(unittest.TestCase):
    def test_empty_requirements_are_a_no_op(self):
        with patch.object(ex, "_get_installed_ollama_models") as installed:
            _ensure_ollama_models({})

        installed.assert_not_called()

    def test_present_models_are_not_pulled(self):
        with (
            patch.object(
                ex, "_get_installed_ollama_models", return_value={"gemma3:4b"}
            ),
            patch("subprocess.run") as run,
        ):
            _ensure_ollama_models({"target": "gemma3:4b"})

        run.assert_not_called()

    def test_missing_models_are_pulled(self):
        with (
            patch.object(ex, "_get_installed_ollama_models", return_value=set()),
            patch("subprocess.run", return_value=_completed()) as run,
        ):
            _ensure_ollama_models({"target": "gemma3:4b", "judge": "gemma3:4b"})

        # The second role reuses the freshly pulled model.
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:3], ["ollama", "run", "gemma3:4b"])

    def test_pull_failures_are_reported(self):
        with (
            patch.object(ex, "_get_installed_ollama_models", return_value=set()),
            patch(
                "subprocess.run",
                return_value=_completed(returncode=1, stderr="disk full"),
            ),
        ):
            with self.assertRaises(click.ClickException) as ctx:
                _ensure_ollama_models({"target": "gemma3:4b"})

        self.assertIn("disk full", str(ctx.exception))


class TestPreflightOllamaRequirements(unittest.TestCase):
    def test_missing_binary_is_reported(self):
        with patch("shutil.which", return_value=None):
            with self.assertRaises(click.ClickException) as ctx:
                _preflight_ollama_requirements({})

        self.assertIn("Ollama is not installed", str(ctx.exception))

    def test_unreachable_server_is_reported(self):
        with (
            patch("shutil.which", return_value="/usr/bin/ollama"),
            patch.object(ex, "_is_ollama_running", return_value=False),
        ):
            with self.assertRaises(click.ClickException) as ctx:
                _preflight_ollama_requirements({})

        self.assertIn("not reachable", str(ctx.exception))

    def test_required_models_are_ensured(self):
        demo_cfg = {
            "agent": {
                "endpoint": "http://localhost:11434",
                "adapter_operational_config": {"name": "target-model"},
            },
            "attack_config": {"judge": {"identifier": "judge-model"}},
        }

        with (
            patch("shutil.which", return_value="/usr/bin/ollama"),
            patch.object(ex, "_is_ollama_running", return_value=True) as running,
            patch.object(ex, "_ensure_ollama_models") as ensure,
        ):
            _preflight_ollama_requirements(demo_cfg)

        self.assertEqual(running.call_args.args[0], "http://localhost:11434")
        self.assertEqual(
            ensure.call_args.args[0],
            {"target": "target-model", "judge": "judge-model"},
        )


class TestLoadOllamaDemoModule(unittest.TestCase):
    def test_unloadable_spec_raises(self):
        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/tmp")),
            patch("importlib.util.spec_from_file_location", return_value=None),
        ):
            with self.assertRaises(RuntimeError):
                _load_ollama_demo_module()

    def test_module_is_executed_and_returned(self):
        spec = MagicMock()
        module = SimpleNamespace()

        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/tmp")),
            patch("importlib.util.spec_from_file_location", return_value=spec),
            patch("importlib.util.module_from_spec", return_value=module),
        ):
            loaded = _load_ollama_demo_module()

        spec.loader.exec_module.assert_called_once_with(module)
        self.assertIs(loaded, module)


class TestOllamaCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.config = MagicMock()

    def test_it_preflights_then_runs_the_campaign(self):
        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/ex")),
            patch.object(ex, "_preflight_ollama_campaign") as preflight,
            patch.object(ex, "_run_campaign_file") as run_campaign,
        ):
            result = self.runner.invoke(ollama, [], obj={"config": self.config})

        self.assertEqual(result.exit_code, 0, result.output)
        campaign = Path("/ex/h4rm3l-demo.yaml")
        preflight.assert_called_once_with(campaign)
        run_campaign.assert_called_once_with(campaign)

    def test_the_models_to_pull_are_read_from_the_campaign(self):
        """Not from a second list, which a new role would silently escape."""
        campaign = """
version: 1
campaign: {name: t}
dataset: {source: {type: inline, goals: [g]}}
target:
  name: target-model
  connection: {provider: ollama, type: OLLAMA, endpoint: 'http://localhost:11434'}
attacks:
  - name: tap
    roles:
      attacker:
        name: attacker-model
        connection:
          provider: ollama
          type: OLLAMA
          endpoint: 'http://localhost:11434'
evaluation:
  judges:
    - name: judge-model
      connection:
        provider: ollama
        type: OLLAMA
        endpoint: 'http://localhost:11434'
      scoring: {type: harmbench}
"""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(campaign)
            path = Path(handle.name)
        try:
            found = ex._ollama_models_in(path)
        finally:
            path.unlink()

        self.assertEqual(found["target"], "target-model")
        self.assertEqual(found["evaluation"], "judge-model")
        self.assertEqual(found["attacks"], "attacker-model")

    def test_a_campaign_with_no_ollama_models_needs_nothing_pulled(self):
        campaign = """
version: 1
campaign: {name: t}
dataset: {source: {type: inline, goals: [g]}}
target:
  name: gpt-4o
  connection: {provider: openai, type: OPENAI_SDK, endpoint: 'https://x/v1'}
attacks: [{name: flipattack}]
"""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(campaign)
            path = Path(handle.name)
        try:
            self.assertEqual(ex._ollama_models_in(path), {})
        finally:
            path.unlink()


class TestNamedExampleCommands(unittest.TestCase):
    """The named commands are aliases: each points at one example."""

    def setUp(self):
        self.runner = CliRunner()

    def _alias(self, command) -> str:
        with patch.object(ex, "_run_example") as run_example:
            result = self.runner.invoke(command, [])
        self.assertEqual(result.exit_code, 0, result.output)
        return run_example.call_args.args[0]

    def test_each_alias_names_an_example_that_exists(self):
        aliases = {
            quick_evaluation: "openai_sdk/quick_evaluation/h4rm3l-granite",
            pc_tool: "openai_sdk/pc_tool_sandbox/pair-vaultdesk",
            db_tool: "openai_sdk/db_tool_sandbox/flipattack-sqldesk",
            rag_example: "rag/indirect-injection",
        }
        found = ex._discover_examples()
        for command, expected in aliases.items():
            with self.subTest(command=command.name):
                self.assertEqual(self._alias(command), expected)
                self.assertIn(expected, found)


class TestWebExample(unittest.TestCase):
    def test_scan_is_invoked_with_a_temporary_config(self):
        captured = {}

        def _capture(args):
            captured["args"] = args
            captured["exists"] = Path(args[-1]).exists()

        with patch.object(ex, "_run_hackagent_cli_command", side_effect=_capture):
            result = CliRunner().invoke(web_example, [])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(captured["args"][:2], ["scan", "https://deepai.org/chat"])
        self.assertIn("--headed", captured["args"])
        self.assertTrue(captured["exists"])
        # The temp config is removed once the scan finishes.
        self.assertFalse(Path(captured["args"][-1]).exists())

    def test_temporary_config_is_removed_on_failure(self):
        captured = {}

        def _fail(args):
            captured["path"] = Path(args[-1])
            raise click.ClickException("scan failed")

        with patch.object(ex, "_run_hackagent_cli_command", side_effect=_fail):
            result = CliRunner().invoke(web_example, [])

        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(captured["path"].exists())


class TestExamplesGroup(unittest.TestCase):
    def test_group_exposes_every_example(self):
        result = CliRunner().invoke(examples, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for name in ("ollama", "quick-evaluation", "pc-tool", "db-tool", "rag", "web"):
            self.assertIn(name, result.output)


if __name__ == "__main__":
    unittest.main()


class TestExampleDiscovery(unittest.TestCase):
    """Examples are found by looking, so a new one needs no registration."""

    def setUp(self):
        self.runner = CliRunner()

    def test_every_campaign_in_the_tree_is_listed(self):
        found = ex._discover_examples()
        on_disk = sorted(
            path.relative_to(ex._examples_root()).with_suffix("").as_posix()
            for path in ex._examples_root().rglob("*.yaml")
        )

        self.assertEqual(sorted(found), on_disk)
        self.assertTrue(on_disk, "no example campaigns found")

    def test_listing_shows_each_example_and_its_description(self):
        result = self.runner.invoke(ex.list_examples, [])

        self.assertEqual(result.exit_code, 0, result.output)
        for name in ex._discover_examples():
            self.assertIn(name, result.output)

    def test_a_unique_last_part_is_enough_to_name_an_example(self):
        key, path = ex._resolve_example_name("h4rm3l-demo")

        self.assertEqual(key, "ollama/h4rm3l-demo")
        self.assertTrue(path.is_file())

    def test_an_ambiguous_name_says_which_ones_it_matched(self):
        # Two folders each hold a `risk-evaluation`.
        with self.assertRaises(click.ClickException) as caught:
            ex._resolve_example_name("risk-evaluation")

        self.assertIn("ollama/risk-evaluation", str(caught.exception))
        self.assertIn("vllm/risk-evaluation", str(caught.exception))

    def test_an_unknown_name_points_at_the_listing(self):
        with self.assertRaises(click.ClickException) as caught:
            ex._resolve_example_name("no-such-example")

        self.assertIn("examples list", str(caught.exception))

    def test_an_example_with_a_server_starts_and_stops_it(self):
        process = MagicMock()
        with (
            patch.object(ex, "_start_background_python", return_value=process) as start,
            patch.object(ex, "_wait_for_tcp_port") as wait,
            patch.object(ex, "_run_campaign_file") as run_campaign,
            patch.object(ex, "_stop_background_process") as stop,
        ):
            ex._run_example("openai_sdk/pc_tool_sandbox/pair-vaultdesk")

        self.assertEqual(start.call_args.args[0].name, "agent.py")
        self.assertEqual(wait.call_args.kwargs["port"], 5001)
        run_campaign.assert_called_once()
        stop.assert_called_once_with(process, "PC Tool agent")

    def test_an_example_without_a_server_just_runs(self):
        with (
            patch.object(ex, "_start_background_python") as start,
            patch.object(ex, "_run_campaign_file") as run_campaign,
        ):
            ex._run_example("claude/flipattack-ollama")

        start.assert_not_called()
        run_campaign.assert_called_once()

    def test_every_target_in_the_table_exists(self):
        """A folder renamed out from under the table would start nothing."""
        for folder, target in ex._TARGETS.items():
            script = ex._examples_root() / folder / target.script
            self.assertTrue(script.is_file(), f"{folder}: no {target.script}")
        for folder in ex._MANUAL_TARGETS:
            self.assertTrue((ex._examples_root() / folder).is_dir(), folder)
