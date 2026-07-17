# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib
from types import SimpleNamespace

import pytest


class _FakeToolFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str):
        self.id = call_id
        self.function = _FakeToolFunction(name, arguments)


class _FakeAssistantMessage:
    def __init__(self, content: str | None, tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self, exclude_none: bool = True):
        payload = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = self.tool_calls
        if exclude_none:
            payload = {k: v for k, v in payload.items() if v is not None}
        return payload


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeResponse:
    def __init__(self, message, payload: dict):
        self.choices = [_FakeChoice(message)]
        self._payload = payload

    def model_dump(self):
        return self._payload


@pytest.fixture
def sandbox_agent(monkeypatch, tmp_path):
    mod = importlib.import_module("hackagent.examples.openai_sdk.db_tool_sandbox.agent")
    monkeypatch.setattr(mod, "DB_PATH", tmp_path / "sandbox.db")
    monkeypatch.setattr(mod, "MAX_ROWS", 2)
    monkeypatch.setattr(mod, "MAX_SQL_CHARS", 200)
    mod.ensure_seed_database()
    return mod


def test_list_tables_includes_sensitive_when_enabled(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "EXPOSE_SENSITIVE_TABLES", True)
    tables = sandbox_agent.list_tables()["tables"]
    assert "db_credentials" in tables


def test_list_tables_hides_sensitive_when_disabled(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "EXPOSE_SENSITIVE_TABLES", False)
    tables = sandbox_agent.list_tables()["tables"]
    assert "db_credentials" not in tables


def test_describe_table_success_and_disallowed(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "EXPOSE_SENSITIVE_TABLES", True)

    ok = sandbox_agent.describe_table("customers")
    assert ok["status"] == "success"
    assert any(col["name"] == "id" for col in ok["columns"])

    bad = sandbox_agent.describe_table("not_allowed")
    assert bad["status"] == "error"


def test_validate_readonly_sql_guards(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "EXPOSE_SENSITIVE_TABLES", False)

    assert sandbox_agent._validate_readonly_sql("select * from customers")

    with pytest.raises(ValueError, match="single-statement"):
        sandbox_agent._validate_readonly_sql("select * from customers;")

    with pytest.raises(ValueError, match="SELECT/WITH"):
        sandbox_agent._validate_readonly_sql("delete from customers")

    with pytest.raises(ValueError, match="too long"):
        sandbox_agent._validate_readonly_sql("x" * 10000)


def test_run_sql_query_success_and_error(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "EXPOSE_SENSITIVE_TABLES", True)

    ok = sandbox_agent.run_sql_query("select * from customers", [])
    assert ok["status"] == "success"
    assert ok["row_count"] <= 2
    assert isinstance(ok["rows"], list)

    err = sandbox_agent.run_sql_query("drop table customers", [])
    assert err["status"] == "error"


def test_execute_tool_call_paths(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "EXPOSE_SENSITIVE_TABLES", True)

    bad_json = sandbox_agent._execute_tool_call("list_tables", "{broken")
    assert bad_json["status"] == "error"

    unknown = sandbox_agent._execute_tool_call("not_a_tool", "{}")
    assert unknown["status"] == "error"

    missing_table = sandbox_agent._execute_tool_call("describe_table", "{}")
    assert missing_table["status"] == "error"

    run_ok = sandbox_agent._execute_tool_call(
        "run_sql_query",
        '{"sql":"select * from customers", "params": []}',
    )
    assert run_ok["status"] == "success"


def test_parse_pseudo_tool_calls_returns_valid_json_candidates(sandbox_agent):
    content = (
        '{"name":"list_tables","parameters":{}}\n'
        '{"name":describe_table,"parameters":not_an_object}'
    )
    parsed = sandbox_agent._parse_pseudo_tool_calls_from_content(content)

    assert len(parsed) == 1
    assert parsed[0]["name"] == "list_tables"


def test_normalize_messages_includes_system_prompt(sandbox_agent):
    out = sandbox_agent._normalize_messages([{"role": "user", "content": "hi"}])
    assert out[0]["role"] == "system"
    assert out[1]["role"] == "user"


def test_chat_completions_rejects_empty_messages(sandbox_agent):
    client = sandbox_agent.app.test_client()
    resp = client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 400


def test_chat_completions_returns_final_response_without_tools(
    sandbox_agent, monkeypatch
):
    fake_msg = _FakeAssistantMessage("final answer", [])
    fake_resp = _FakeResponse(fake_msg, {"id": "resp_1", "answer": "final answer"})

    calls = []

    def _create(**kwargs):
        calls.append(kwargs)
        return fake_resp

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(sandbox_agent, "client", fake_client)

    client = sandbox_agent.app.test_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"id": "resp_1", "answer": "final answer"}
    assert len(calls) == 1


def test_chat_completions_tool_call_then_final_response(sandbox_agent, monkeypatch):
    tool_msg = _FakeAssistantMessage(
        content=None,
        tool_calls=[_FakeToolCall("tc_1", "list_tables", "{}")],
    )
    final_msg = _FakeAssistantMessage("done", [])

    responses = iter(
        [
            _FakeResponse(tool_msg, {"id": "resp_tool"}),
            _FakeResponse(final_msg, {"id": "resp_final", "answer": "done"}),
        ]
    )

    def _create(**kwargs):
        return next(responses)

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(sandbox_agent, "client", fake_client)

    client = sandbox_agent.app.test_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "list tables"}]},
    )

    assert resp.status_code == 200
    assert resp.get_json()["id"] == "resp_final"


def test_chat_completions_pseudo_tool_call_then_final_response(
    sandbox_agent, monkeypatch
):
    pseudo_msg = _FakeAssistantMessage(
        '{"name":"list_tables","parameters":{}}',
        [],
    )
    final_msg = _FakeAssistantMessage("completed", [])

    responses = iter(
        [
            _FakeResponse(pseudo_msg, {"id": "resp_pseudo"}),
            _FakeResponse(final_msg, {"id": "resp_final", "answer": "completed"}),
        ]
    )

    def _create(**kwargs):
        return next(responses)

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(sandbox_agent, "client", fake_client)

    client = sandbox_agent.app.test_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "do it"}]},
    )

    assert resp.status_code == 200
    assert resp.get_json()["id"] == "resp_final"


def test_chat_completions_errors_when_max_steps_reached(sandbox_agent, monkeypatch):
    monkeypatch.setattr(sandbox_agent, "MAX_TOOL_STEPS", 1)

    tool_msg = _FakeAssistantMessage(
        content=None,
        tool_calls=[_FakeToolCall("tc_1", "list_tables", "{}")],
    )

    fake_resp = _FakeResponse(tool_msg, {"id": "resp_tool"})

    def _create(**kwargs):
        return fake_resp

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )
    monkeypatch.setattr(sandbox_agent, "client", fake_client)

    client = sandbox_agent.app.test_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "loop"}]},
    )

    assert resp.status_code == 500
    assert "MAX_TOOL_STEPS" in resp.get_json()["error"]
