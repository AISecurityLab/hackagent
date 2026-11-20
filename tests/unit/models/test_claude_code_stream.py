# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Claude Code backend: tool log, per-call cwd, subprocess env, stream log.

A repo-injection attack judges a coding agent from what it *did*, not only
what it said, so the adapter must surface the tool calls of a headless run.
These tests drive a fake ``claude`` binary that replays a recorded
``--output-format stream-json`` run, so no real agent or network is involved.
"""

import asyncio
import json
import logging
import os
import stat
import sys
from pathlib import Path

import pytest

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions.claude import ClaudeCodeModel

logging.disable(logging.CRITICAL)

FIXTURES = Path(__file__).parent / "fixtures"
MESSAGES = [{"role": "user", "content": "fix the failing test"}]

_FAKE_SCRIPT = """#!{python}
import json, os, sys
sys.stdin.read()
with open({side!r}, "a") as f:
    f.write(json.dumps({{"cwd": os.getcwd(), "proxy": os.environ.get("HTTP_PROXY"),
                         "argv": sys.argv[1:]}}) + "\\n")
sys.stdout.write(open({stdout!r}).read())
sys.exit({code})
"""


class FakeClaude:
    """A ``ClaudeCodeModel`` wired to a fake binary, plus what the binary saw."""

    def __init__(self, model: ClaudeCodeModel, side: Path):
        self.model = model
        self.side = side

    def runs(self):
        return [json.loads(line) for line in self.side.read_text().splitlines()]

    def complete(self, **overrides):
        return self.model.complete(MESSAGES, **overrides)


@pytest.fixture
def fake_claude(tmp_path):
    counter = iter(range(1000))

    def build(fixture=None, *, stdout=None, code=0, **config):
        n = next(counter)
        out = tmp_path / f"stdout-{n}.jsonl"
        out.write_text(
            stdout if stdout is not None else (FIXTURES / fixture).read_text()
        )
        side = tmp_path / f"side-{n}.jsonl"
        side.touch()
        binary = tmp_path / f"claude-{n}"
        binary.write_text(
            _FAKE_SCRIPT.format(
                python=sys.executable, side=str(side), stdout=str(out), code=code
            )
        )
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        spec = ModelSpec(
            identifier="sonnet",
            agent_type=AgentType.CLAUDE_CODE,
            extra={"binary": str(binary), **config},
        )
        return FakeClaude(ClaudeCodeModel(spec), side)

    return build


def _stream(*events):
    return "".join(json.dumps(e) + "\n" for e in events)


def test_tool_calls_in_order_with_results(fake_claude):
    r = fake_claude("claude_stream_leak.jsonl").complete()
    assert r.ok
    assert [c["name"] for c in r.tool_calls] == ["Bash", "Bash", "Edit"]
    assert "curl" in json.loads(r.tool_calls[0]["arguments"])["command"]
    assert set(r.tool_calls[0]) == {"name", "arguments", "result", "is_error"}
    assert r.tool_calls[0]["is_error"] is True
    assert r.tool_calls[0]["result"] == "This command requires approval"
    assert r.text.startswith("Fixed")


def test_long_result_truncated(fake_claude):
    big = "x" * 10_000
    stdout = _stream(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Bash",
                        "input": {"command": "cat big"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": big}
                ],
            },
        },
        {"type": "result", "subtype": "success", "is_error": False, "result": "done"},
    )
    r = fake_claude(stdout=stdout).complete()
    result = r.tool_calls[0]["result"]
    assert len(result) <= 2000 and result.endswith("…[truncated]")
    assert r.tool_calls[0]["is_error"] is False


def test_structured_result_content_is_flattened(fake_claude):
    stdout = _stream(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {}}
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": [
                            {"type": "text", "text": "a"},
                            {"type": "text", "text": "b"},
                        ],
                    }
                ],
            },
        },
        {"type": "result", "subtype": "success", "is_error": False, "result": "ok"},
    )
    assert fake_claude(stdout=stdout).complete().tool_calls[0]["result"] == "a\nb"


def test_cwd_override_per_call(fake_claude, tmp_path):
    configured = tmp_path / "configured"
    override = tmp_path / "override"
    configured.mkdir()
    override.mkdir()
    fc = fake_claude("claude_stream_leak.jsonl", cwd=str(configured))
    assert fc.complete(cwd=str(override)).ok
    assert fc.complete().ok
    seen = [Path(run["cwd"]).resolve() for run in fc.runs()]
    assert seen == [override.resolve(), configured.resolve()]


def test_cwd_override_via_acomplete(fake_claude, tmp_path):
    override = tmp_path / "override"
    override.mkdir()
    fc = fake_claude("claude_stream_leak.jsonl")
    r = asyncio.run(fc.model.acomplete(MESSAGES, cwd=str(override)))
    assert r.ok and r.tool_calls
    assert Path(fc.runs()[0]["cwd"]).resolve() == override.resolve()


def test_env_reaches_subprocess_only(fake_claude, monkeypatch):
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    fc = fake_claude(
        "claude_stream_leak.jsonl", env={"HTTP_PROXY": "http://127.0.0.1:9"}
    )
    assert fc.complete().ok
    assert fc.runs()[0]["proxy"] == "http://127.0.0.1:9"
    assert "HTTP_PROXY" not in os.environ


def test_env_is_merged_over_environ(fake_claude, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://parent")
    fc = fake_claude("claude_stream_leak.jsonl")
    fc.complete()
    assert fc.runs()[0]["proxy"] == "http://parent"


def test_stream_log_written(fake_claude, tmp_path):
    log_dir = tmp_path / "logs" / "nested"
    fc = fake_claude("claude_stream_leak.jsonl", stream_log_dir=str(log_dir))
    fc.complete()
    fc.complete()
    files = sorted(log_dir.glob("*.jsonl"))
    assert len(files) == 2
    expected = (FIXTURES / "claude_stream_leak.jsonl").read_text()
    assert all(f.read_text() == expected for f in files)
    assert files[0].name.endswith("-1.jsonl") and files[1].name.endswith("-2.jsonl")


def test_stream_log_off_by_default(fake_claude, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_claude("claude_stream_leak.jsonl").complete()
    assert list(tmp_path.glob("**/*-1.jsonl")) == []


def test_argv_uses_stream_json(fake_claude):
    fc = fake_claude("claude_stream_leak.jsonl")
    fc.complete()
    argv = fc.runs()[0]["argv"]
    assert argv[:4] == ["-p", "--output-format", "stream-json", "--verbose"]


def test_max_turns_keeps_tool_calls(fake_claude):
    r = fake_claude("claude_stream_max_turns.jsonl").complete()
    assert r.ok and r.tool_calls and "max turns" in r.text.lower()
    assert r.text.startswith("I'll help you")  # prior assistant text is kept


def test_refusal_still_captured(fake_claude):
    r = fake_claude("claude_stream_refusal.jsonl", code=1).complete()
    assert r.ok and "Usage Policy" in r.text and r.tool_calls == []


def test_error_during_execution_still_fails(fake_claude):
    stdout = _stream(
        {
            "type": "result",
            "subtype": "error_during_execution",
            "is_error": True,
            "result": "boom",
        }
    )
    r = fake_claude(stdout=stdout).complete()
    assert not r.ok
    assert "boom" in r.error.message


_PARTIAL = _stream(
    {"type": "system", "subtype": "init", "session_id": "s"},
    {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "working"}],
        },
    },
)


@pytest.mark.parametrize("code", [0, 1])
def test_stream_without_result_event_fails(fake_claude, code):
    r = fake_claude(stdout=_PARTIAL, code=code).complete()
    assert not r.ok
    assert r.text == ""
