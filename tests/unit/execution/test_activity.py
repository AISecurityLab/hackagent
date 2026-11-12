# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The run activity relay: conversion, redaction, batching and delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from uuid import uuid4

import pytest

from hackagent.core.logging import REPORTED_AS_EVENT
from hackagent.orchestrator.execution.activity import (
    Activity,
    ActivityRelay,
    Redactor,
    activity_for_outcome,
    activity_from_event,
    activity_from_record,
)
from hackagent.storage.remote import (
    ExecutorRejected,
    RunAlreadyFinished,
    RunEventsUnsupported,
)

RUN = str(uuid4())
SECRET = "secret-value-for-test-0123"


class FakeSender:
    """Records every batch; ``failures`` are raised by the next sends, in order."""

    def __init__(self, *failures: Exception) -> None:
        self.failures = list(failures)
        self.batches: list[list[dict]] = []
        self.attempts = 0
        self.sent = threading.Event()

    def __call__(self, batch):
        self.attempts += 1
        if self.failures:
            raise self.failures.pop(0)
        self.batches.append([dict(event) for event in batch])
        self.sent.set()
        return {"accepted": len(batch), "duplicates": 0, "dropped": 0}

    @property
    def events(self) -> list[dict]:
        return [event for batch in self.batches for event in batch]


def relay(sender, **options) -> ActivityRelay:
    return ActivityRelay(sender, secrets=[SECRET], **options)


def info(message: str = "line") -> Activity:
    return Activity("info", "log", message)


def record(name, level, message, *args, **extra):
    made = logging.LogRecord(name, level, __file__, 1, message, args, None)
    made.__dict__.update(extra)
    return made


# --- runner events ----------------------------------------------------------


def test_a_goal_reads_as_the_executor_logs_it():
    activity = activity_from_event(
        "goal_finished",
        {
            "attack": "pair",
            "run_id": RUN,
            "goal_index": 15,
            "goals": 1017,
            "success": True,
            "attempts": 5,
            "successful": 4,
            "errors": [],
            "elapsed_s": 12.345,
        },
    )

    assert activity.message == "pair · goal 16/1017 · 5 attempts · 4 successful"
    assert activity.level == "info"
    assert activity.kind == "goal"
    assert activity.attack == "pair"
    assert activity.attack_run == RUN
    assert activity.goal_index == 15
    assert activity.data == {
        "attempts": 5,
        "successful": 4,
        "elapsed_s": 12.3,
        "errors": [],
    }


def test_a_goal_with_errors_is_a_warning_with_its_first_reason():
    errors = [f"target call failed: timeout {n}" for n in range(5)]
    activity = activity_from_event(
        "goal_finished",
        {
            "attack": "pair",
            "goal_index": 0,
            "goals": 2,
            "attempts": 1,
            "errors": errors,
        },
    )

    assert activity.level == "warning"
    assert activity.message.endswith("5 errors: target call failed: timeout 0")
    assert activity.data["errors"] == errors[:3]


@pytest.mark.parametrize(
    ("event", "payload", "level", "kind", "message"),
    [
        (
            "campaign_started",
            {"campaign": "Test 4"},
            "info",
            "campaign",
            "campaign Test 4 · started · loading goals and models",
        ),
        (
            "goals_loaded",
            {"goals": 1017},
            "info",
            "dataset",
            "dataset · 1017 goals loaded",
        ),
        (
            "models_resolved",
            {"models": 3, "attacks": 1, "judges": 1},
            "info",
            "campaign",
            "campaign · 3 models ready · 1 attack · 1 judge",
        ),
        (
            "preflight_started",
            {"models": 3},
            "info",
            "preflight",
            "preflight · checking 3 models",
        ),
        (
            "preflight_finished",
            {"models": 3},
            "info",
            "preflight",
            "preflight · 3 models reachable",
        ),
        (
            "preflight_failed",
            {"models": 3, "failures": ["judge (evaluation.judges[0]): refused"]},
            "error",
            "preflight",
            "preflight · 1 of 3 models unreachable: judge (evaluation.judges[0]): refused",
        ),
        (
            "audit_started",
            {"judges": 2},
            "info",
            "judge",
            "judge audit · started · 2 judges",
        ),
        (
            "audit_finished",
            {"audit": {"passed": False, "samples": 40}},
            "warning",
            "judge",
            "judge audit · failed · 40 samples",
        ),
        (
            "attack_started",
            {"attack": "pair", "run_id": RUN, "expected_goals": 1017},
            "info",
            "attack",
            "pair · started · 1017 goals",
        ),
        (
            "preparation_started",
            {"attack": "autodan_turbo", "run_id": RUN, "goals": 10},
            "info",
            "attack",
            "autodan_turbo · preparing · 10 goals",
        ),
        (
            "preparation_finished",
            {"attack": "autodan_turbo", "run_id": RUN, "elapsed_s": 312.44},
            "info",
            "attack",
            "autodan_turbo · prepared in 312.4s",
        ),
        (
            "attack_finished",
            {
                "attack": "pair",
                "run_id": RUN,
                "error": None,
                "attempts": 5085,
                "successful": 1200,
                "elapsed_s": 3600.04,
            },
            "info",
            "attack",
            "pair · finished · 5085 attempts · 1200 successful · 3600.0s",
        ),
        (
            "attack_finished",
            {"attack": "pair", "run_id": RUN, "error": "TimeoutError: per-attack"},
            "error",
            "attack",
            "pair · failed · TimeoutError: per-attack",
        ),
    ],
)
def test_runner_events_become_activity(event, payload, level, kind, message):
    activity = activity_from_event(event, payload)

    assert (activity.level, activity.kind, activity.message) == (level, kind, message)


def test_an_unknown_event_is_not_relayed():
    assert activity_from_event("attempt_recorded", {"prompt": "x"}) is None


def test_no_prompt_or_reply_a_payload_carries_ever_leaves():
    sender = FakeSender()
    activity = relay(sender)
    payload = {
        "attack": "pair",
        "run_id": RUN,
        "goal_index": 0,
        "goals": 1,
        "attempts": 1,
        "successful": 0,
        "errors": [],
        "elapsed_s": 1.0,
        "goal": "the goal text",
        "prompt": "the attack prompt",
        "response": "the target reply",
        "messages": [{"role": "user", "content": "the attack prompt"}],
    }
    for event in ("attack_started", "goal_finished", "attack_finished"):
        activity.on_event(event, **payload)
    activity.flush()

    sent = json.dumps(sender.events)
    assert len(sender.events) == 3
    for text in ("the goal text", "the attack prompt", "the target reply"):
        assert text not in sent


def test_the_outcome_is_the_last_line():
    assert activity_for_outcome("COMPLETED", "").message == "campaign · completed"
    failed = activity_for_outcome("FAILED", "PreflightError: judge down")
    assert (failed.level, failed.message) == (
        "error",
        "campaign · failed · PreflightError: judge down",
    )
    assert activity_for_outcome("CANCELLED", "Campaign cancelled").level == "warning"


# --- log records ------------------------------------------------------------


def test_hackagent_lines_are_relayed_from_info():
    line = activity_from_record(
        record("hackagent.datasets.labelling", logging.INFO, "labelled %d goals", 7)
    )

    assert (line.level, line.kind, line.message) == ("info", "log", "labelled 7 goals")
    assert activity_from_record(record("hackagent.x", logging.DEBUG, "detail")) is None


def test_a_line_a_progress_event_reports_is_not_relayed_twice():
    reported = record(
        "hackagent.orchestrator.campaign.runner",
        logging.INFO,
        "pair | goal 1/2 | 1 attempts | 0 successful",
        **REPORTED_AS_EVENT,
    )

    assert activity_from_record(reported) is None


def test_a_client_retry_is_a_retry_warning():
    line = activity_from_record(
        record(
            "openai._base_client",
            logging.INFO,
            "Retrying request to %s in %f seconds",
            "/chat/completions",
            0.47,
        )
    )

    assert line.kind == "retry"
    assert line.level == "warning"
    assert line.message == (
        "openai · Retrying request to /chat/completions in 0.470000 seconds"
    )


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("httpx", 'HTTP Request: POST https://x/v1 "HTTP/1.1 504 Gateway Timeout"'),
        ("httpx", 'HTTP Request: POST https://x/v1 "HTTP/1.1 200 OK"'),
        ("LiteLLM", "\nLiteLLM completion() model= judge; provider = openai"),
        ("openai._base_client", "Sending HTTP Request: POST /chat/completions"),
        ("urllib3.connectionpool", "Retrying (Retry(total=2)) after timeout"),
    ],
)
def test_per_request_noise_is_left_out(name, message):
    assert activity_from_record(record(name, logging.INFO, message)) is None


def test_library_warnings_and_errors_are_relayed():
    line = activity_from_record(
        record("LiteLLM", logging.ERROR, "litellm.APIError: upstream closed")
    )

    assert (line.level, line.kind) == ("error", "log")
    assert line.message == "litellm · litellm.APIError: upstream closed"


def test_an_exception_on_a_record_is_named_not_traced():
    try:
        raise TimeoutError("120s")
    except TimeoutError:
        import sys

        failed = logging.LogRecord(
            "hackagent.x", logging.ERROR, __file__, 1, "call failed", (), sys.exc_info()
        )

    assert activity_from_record(failed).message == "call failed (TimeoutError: 120s)"


# --- redaction --------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "leaked"),
    [
        (f"refused key {SECRET} for the gateway", SECRET),
        ("401: Incorrect API key provided: sk-abcdefghijklmnopqrstuvwx", "sk-abcdef"),
        ("headers {'Authorization': 'Bearer tok_abcdefghijkl'}", "tok_abcdefghijkl"),
        ("calling with api_key=plainvalue123 and model=x", "plainvalue123"),
        ('{"x-api-key": "plainvalue456"}', "plainvalue456"),
        ("GET https://user:pa55word@host/v1?token=abc123", "pa55word"),
        ("GET https://host/v1?token=abc123&page=2", "abc123"),
    ],
)
def test_secrets_never_leave(message, leaked):
    sender = FakeSender()
    activity = relay(sender)
    activity.add(Activity("error", "log", message))
    activity.flush()

    [event] = sender.events
    assert leaked not in event["message"]
    assert "[REDACTED]" in event["message"]


@pytest.mark.parametrize("padding", [190, 199])
def test_goal_errors_are_redacted_before_they_are_shortened(padding):
    sender = FakeSender()
    activity = relay(sender)
    activity.on_event(
        "goal_finished",
        attack="pair",
        goal_index=0,
        errors=["x" * padding + SECRET + " refused"],
    )
    activity.close()

    [event] = sender.events
    assert SECRET[:5] not in json.dumps(event)
    assert event["data"]["errors"] == [
        ("x" * padding + "[REDACTED] refused")[:199] + "…"
    ]


def test_operational_text_is_kept():
    text = "pair · goal 3/10 · 2 errors: target call failed: KeyError: 'choices'"

    assert Redactor([SECRET]).text(text) == text


def test_data_is_redacted_and_bounded():
    redactor = Redactor([SECRET])

    assert redactor.data({"note": f"key {SECRET}", "api_key": "x", "n": 1}) == {
        "note": "key [REDACTED]",
        "n": 1,
    }
    big = redactor.data({"count": 3, "errors": ["e" * 1000] * 10})
    assert big == {"count": 3}


def test_messages_are_one_line_without_nul_and_cut_to_the_limit():
    redactor = Redactor()
    cut = redactor.activity(Activity("info", "log", "a\nb\x00c " + "x" * 2000))

    assert cut.message.startswith("a bc x")
    assert len(cut.message) == 1000
    assert cut.message.endswith("…")
    assert redactor.activity(Activity("info", "log", " \n ")) is None


def test_fields_the_platform_refuses_are_left_empty():
    cleaned = Redactor().activity(
        Activity("info", "goal", "m", attack="", attack_run="run-1", goal_index=-1)
    )

    assert (cleaned.attack, cleaned.attack_run, cleaned.goal_index) == (
        None,
        None,
        None,
    )


def test_the_wire_shape():
    event = info("hello").wire(7)

    assert set(event) == {
        "seq",
        "time",
        "level",
        "kind",
        "attack",
        "attack_run",
        "goal_index",
        "message",
        "data",
    }
    assert event["seq"] == 7
    assert event["time"].endswith("+00:00")
    assert event["data"] == {}


# --- sequencing, batching, overflow -------------------------------------------


def test_events_are_numbered_from_one_in_batches():
    sender = FakeSender()
    activity = relay(sender, batch_size=3)
    for n in range(7):
        activity.add(info(f"line {n}"))

    assert activity.flush()

    assert [len(batch) for batch in sender.batches] == [3, 3, 1]
    assert [event["seq"] for event in sender.events] == list(range(1, 8))
    assert [event["message"] for event in sender.events] == [
        f"line {n}" for n in range(7)
    ]


def test_enough_queued_events_are_sent_without_waiting_for_the_interval():
    sender = FakeSender()
    activity = relay(sender, interval_s=60, threshold=3)
    activity.start()
    for n in range(3):
        activity.add(info(f"line {n}"))

    assert sender.sent.wait(5)
    assert len(sender.events) == 3
    activity.close()


def test_a_few_events_are_sent_when_the_interval_passes():
    sender = FakeSender()
    activity = relay(sender, interval_s=0.01, threshold=1000)
    activity.start()
    activity.add(info())

    assert sender.sent.wait(5)
    activity.close()


def test_a_full_queue_drops_the_oldest_info_first_and_says_so():
    sender = FakeSender()
    activity = relay(sender, limit=3)
    activity.add(Activity("warning", "log", "w1"))
    activity.add(info("i1"))
    activity.add(info("i2"))
    activity.add(info("i3"))
    activity.add(Activity("error", "log", "e1"))

    activity.flush()

    messages = [event["message"] for event in sender.events]
    assert messages[0] == (
        "activity · 2 events dropped: they came faster than they could be sent"
    )
    assert sender.events[0]["level"] == "warning"
    assert sender.events[0]["data"] == {"dropped": 2}
    assert messages[1:] == ["w1", "i3", "e1"]
    assert [event["seq"] for event in sender.events] == [1, 2, 3, 4]


def test_a_full_queue_of_warnings_drops_the_oldest():
    sender = FakeSender()
    activity = relay(sender, limit=2)
    for n in range(3):
        activity.add(Activity("warning", "log", f"w{n}"))

    activity.flush()

    assert [event["message"] for event in sender.events][1:] == ["w1", "w2"]


# --- delivery -----------------------------------------------------------------


def test_a_failed_send_is_retried_with_the_same_numbers():
    sender = FakeSender(ConnectionError("down"))
    activity = relay(sender)
    activity.add(info("a"))

    assert not activity.flush()
    activity.add(info("b"))
    assert activity.flush()

    assert [[e["seq"] for e in batch] for batch in sender.batches] == [[1], [2]]
    assert sender.attempts == 3


def test_a_failing_sender_logs_once_until_it_recovers(caplog):
    sender = FakeSender(ConnectionError("down"), ConnectionError("down"))
    activity = relay(sender)
    activity.add(info())

    with caplog.at_level(logging.INFO, logger="hackagent.orchestrator.execution"):
        activity.flush()
        activity.flush()
        activity.flush()

    messages = [r.getMessage() for r in caplog.records]
    assert sum("could not send" in m for m in messages) == 1
    assert sum("sending again" in m for m in messages) == 1


def test_a_refused_batch_is_dropped_and_the_next_one_follows(caplog):
    sender = FakeSender(ValueError("400: invalid level"))
    activity = relay(sender, batch_size=1)
    activity.add(info("bad"))
    activity.add(info("good"))

    with caplog.at_level(logging.WARNING):
        assert activity.flush()

    assert [event["message"] for event in sender.events] == ["good"]
    assert sender.events[0]["seq"] == 2
    assert "refused and dropped" in caplog.text


@pytest.mark.parametrize(
    "over",
    [RunAlreadyFinished("409"), ExecutorRejected("401"), ExecutorRejected("403")],
)
def test_a_run_that_is_over_stops_the_sending_quietly(over, caplog):
    sender = FakeSender(over)
    activity = relay(sender)
    activity.add(info())

    with caplog.at_level(logging.INFO, logger="hackagent.orchestrator.execution"):
        assert not activity.flush()
        activity.add(info())
        activity.flush()

    assert activity.stopped
    assert sender.attempts == 1
    assert caplog.records == []


def test_a_server_without_the_endpoint_is_told_once(caplog):
    sender = FakeSender(RunEventsUnsupported("404"))
    activity = relay(sender, batch_size=1)
    activity.add(info())
    activity.add(info())

    with caplog.at_level(logging.INFO, logger="hackagent.orchestrator.execution"):
        activity.flush()
        activity.on_event("goals_loaded", goals=1)
        activity.flush()

    assert sender.attempts == 1
    assert len(caplog.records) == 1
    assert "does not record" in caplog.records[0].getMessage()


def test_close_sends_what_is_left_and_drops_what_comes_after():
    sender = FakeSender()
    activity = relay(sender, interval_s=60, threshold=1000)
    activity.start()
    activity.add(info("before"))
    activity.finished("COMPLETED", "")

    activity.close()
    activity.add(info("after"))

    assert [event["message"] for event in sender.events] == [
        "before",
        "campaign · completed",
    ]


def test_close_without_start_flushes_inline():
    sender = FakeSender()
    activity = relay(sender)
    activity.add(info())

    activity.close()

    assert len(sender.events) == 1


def test_a_hung_sender_does_not_hold_close_past_its_timeout():
    release = threading.Event()

    def hung(batch):
        release.wait(5)

    activity = ActivityRelay(hung, close_timeout_s=0.05)
    activity.start()
    activity.add(info())

    activity.close()  # returns although the send has not

    release.set()


# --- log capture ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def logging_enabled():
    """Some test modules silence logging when collected; these tests log."""
    disabled = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    yield
    logging.disable(disabled)


class Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def test_the_run_s_own_log_records_are_captured_in_its_context():
    sender = FakeSender()
    activity = relay(sender)
    log = logging.getLogger("hackagent.tests.activity")
    log.setLevel(logging.INFO)
    try:

        def other_thread():
            log.warning("not this run")

        with activity.capture():
            log.info("in the run")
            log.debug("too detailed")
            asyncio.run(asyncio.to_thread(log.warning, "in its thread"))
            thread = threading.Thread(target=other_thread)
            thread.start()
            thread.join()
        log.warning("after the run")
        activity.close()
    finally:
        log.setLevel(logging.NOTSET)

    assert [event["message"] for event in sender.events] == [
        "in the run",
        "in its thread",
    ]


def test_client_retries_are_captured_without_printing_more():
    sender = FakeSender()
    activity = relay(sender)
    client = logging.getLogger("openai._base_client")
    level = client.level
    shown = Collect()
    logging.getLogger("openai").addHandler(shown)
    client.setLevel(logging.WARNING)
    try:
        with activity.capture():
            assert client.isEnabledFor(logging.INFO)
            client.info("Retrying request to %s in %f seconds", "/chat", 0.5)
            client.warning("shown as before")
        assert client.level == logging.WARNING
        assert not [f for f in client.filters if type(f).__name__ == "_TapFilter"]
        activity.close()
    finally:
        logging.getLogger("openai").removeHandler(shown)
        client.setLevel(level)

    assert [record.getMessage() for record in shown.records] == ["shown as before"]
    assert [event["kind"] for event in sender.events] == ["retry", "log"]


def test_a_logger_created_during_the_run_is_captured():
    sender = FakeSender()
    activity = relay(sender)
    name = f"hackagent.tests.late_{uuid4().hex}"
    with activity.capture():
        late = logging.getLogger(name)
        activity.on_event("goals_loaded", goals=1)  # any event looks again
        late.warning("from a late logger")
    activity.close()

    assert [event["message"] for event in sender.events] == [
        "dataset · 1 goal loaded",
        "from a late logger",
    ]
