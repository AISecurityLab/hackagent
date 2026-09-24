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

        self.assertEqual(run.call_args.args[0][1:3], ["-m", "hackagent.interfaces.cli.main"])

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

    def _invoke(self, module):
        with (
            patch.object(ex, "_load_ollama_demo_module", return_value=module),
            patch.object(ex, "_preflight_ollama_requirements") as preflight,
        ):
            result = self.runner.invoke(ollama, [], obj={"config": self.config})
        return result, preflight

    def test_demo_results_are_summarised(self):
        module = SimpleNamespace(
            build_ollama_demo_config=lambda: {"agent": {}},
            run_ollama_demo=lambda: [{"success": True}, {"success": False}],
        )

        result, preflight = self._invoke(module)

        self.assertEqual(result.exit_code, 0, result.output)
        preflight.assert_called_once()
        self.assertIn("Goals tested: 2", result.output)
        self.assertIn("Successful goals: 1/2", result.output)

    def test_non_list_results_are_tolerated(self):
        module = SimpleNamespace(
            build_ollama_demo_config=lambda: {},
            run_ollama_demo=lambda: None,
        )

        result, _ = self._invoke(module)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("ollama example completed", result.output)

    def test_demo_without_a_config_builder_is_rejected(self):
        result, preflight = self._invoke(SimpleNamespace())

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("build_ollama_demo_config", result.output)
        preflight.assert_not_called()

    def test_demo_without_a_runner_is_rejected(self):
        module = SimpleNamespace(build_ollama_demo_config=lambda: {})

        result, _ = self._invoke(module)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("run_ollama_demo", result.output)


class TestScriptBackedCommands(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_quick_evaluation_runs_the_h4rm3l_script(self):
        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/ex")),
            patch.object(ex, "_run_python_script") as run_script,
        ):
            result = self.runner.invoke(quick_evaluation, [])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(run_script.call_args.args[0], Path("/ex/run_h4rm3l.py"))

    def test_rag_example_runs_its_script(self):
        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/ex")),
            patch.object(ex, "_run_python_script") as run_script,
        ):
            result = self.runner.invoke(rag_example, [])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            run_script.call_args.args[0], Path("/ex/test_indirect_injection.py")
        )

    def _sandbox_example(self, command, env_flag, default_port):
        process = MagicMock()
        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/ex")),
            patch.object(ex, "_start_background_python", return_value=process),
            patch.object(ex, "_wait_for_tcp_port") as wait,
            patch.object(ex, "_run_python_script") as run_script,
            patch.object(ex, "_stop_background_process") as stop,
            patch.dict("os.environ", {}, clear=True),
        ):
            result = self.runner.invoke(command, [])
        return result, wait, run_script, stop, process

    def test_pc_tool_starts_the_agent_and_runs_the_attack(self):
        result, wait, run_script, stop, process = self._sandbox_example(
            pc_tool, "HACKAGENT_PC_TOOL_EXTERNAL_AGENT", 5001
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(wait.call_args.kwargs["port"], 5001)
        self.assertEqual(
            run_script.call_args.kwargs["env"]["HACKAGENT_PC_TOOL_EXTERNAL_AGENT"], "1"
        )
        stop.assert_called_once_with(process, "PC Tool agent")

    def test_db_tool_starts_the_agent_and_runs_the_attack(self):
        result, wait, run_script, stop, process = self._sandbox_example(
            db_tool, "HACKAGENT_DB_TOOL_EXTERNAL_AGENT", 5002
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(wait.call_args.kwargs["port"], 5002)
        self.assertEqual(
            run_script.call_args.kwargs["env"]["HACKAGENT_DB_TOOL_EXTERNAL_AGENT"], "1"
        )
        stop.assert_called_once_with(process, "DB Tool agent")

    def test_sandbox_agent_is_stopped_even_when_the_attack_fails(self):
        process = MagicMock()

        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/ex")),
            patch.object(ex, "_start_background_python", return_value=process),
            patch.object(ex, "_wait_for_tcp_port"),
            patch.object(
                ex, "_run_python_script", side_effect=click.ClickException("boom")
            ),
            patch.object(ex, "_stop_background_process") as stop,
        ):
            result = self.runner.invoke(pc_tool, [])

        self.assertNotEqual(result.exit_code, 0)
        stop.assert_called_once()

    def test_port_can_be_overridden_by_the_environment(self):
        with (
            patch.object(ex, "_resolve_example_dir", return_value=Path("/ex")),
            patch.object(ex, "_start_background_python", return_value=MagicMock()),
            patch.object(ex, "_wait_for_tcp_port") as wait,
            patch.object(ex, "_run_python_script"),
            patch.object(ex, "_stop_background_process"),
            patch.dict("os.environ", {"PORT": "6001"}),
        ):
            self.runner.invoke(pc_tool, [])

        self.assertEqual(wait.call_args.kwargs["port"], 6001)


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
