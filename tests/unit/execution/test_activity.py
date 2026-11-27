# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The run activity relay: conversion, redaction, batching and delivery."""

from __future__ import annotations

import asyncio
import logging
import threading
from uuid import uuid4

import pytest

from hackagent.core.logging import TRACE_LOGGER
from hackagent.orchestrator.execution.activity import (
    MESSAGE_LIMIT,
    Activity,
    ActivityRelay,
    Redactor,
    activity_for_outcome,
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


# --- the run's lines --------------------------------------------------------


def test_a_line_is_relayed_as_written_with_what_it_is_about():
    line = activity_from_record(
        record(
            "hackagent.campaign.goals",
            logging.INFO,
            "pair · goal 0016 · result: mitigated · 5 attempts · 12.3s",
            subject={"attack": "pair", "goal": 16, "goals": 1017},
        )
    )

    assert (line.level, line.kind, line.attack, line.goal_index) == (
        "info",
        "log",
        "pair",
        15,
    )
    assert line.message == "pair · goal 0016 · result: mitigated · 5 attempts · 12.3s"
    assert line.data == {}


@pytest.mark.parametrize(
    ("level", "expected"),
    [(logging.INFO, "info"), (logging.WARNING, "warning"), (logging.ERROR, "error")],
)
def test_a_line_keeps_its_level(level, expected):
    line = activity_from_record(record("hackagent.campaign", level, "the line"))

    assert (line.level, line.message, line.attack) == (expected, "the line", None)


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


def _step(level: int, what: str) -> logging.LogRecord:
    return record(
        TRACE_LOGGER,
        level,
        f"pair · goal 2 · round 1/3 › {what}",
        trace_step={
            "attack": "pair",
            "goal": 2,
            "source": "pair · goal 2",
            "within": ["round 1/3"],
            "what": what,
        },
    )


def test_the_attack_trace_is_relayed_as_the_log_writes_it():
    line = activity_from_record(_step(logging.INFO, "panel: jailbroken (score 9)"))

    assert (line.level, line.kind, line.attack, line.goal_index) == (
        "info",
        "trace",
        "pair",
        1,
    )
    assert line.message == "pair · goal 2 · round 1/3 · panel: jailbroken (score 9)"


def test_nothing_below_info_leaves():
    """The calls that quote prompts and replies are DEBUG: they stay here."""
    assert activity_from_record(_step(logging.DEBUG, 'target: "the reply"')) is None


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

    # By its type: an exception's message can quote what a model wrote.
    assert activity_from_record(failed).message == "call failed (TimeoutError)"


def test_what_a_model_wrote_never_leaves_in_a_step():
    """A decision says what was decided and its numbers, not why: h4rm3l's
    reason quotes the compiler's error on a program a model wrote. A failed
    call says it failed, not the provider's text. The log keeps both."""
    from hackagent.attacks.techniques.trace import TraceNode
    from hackagent.attacks.techniques.trace_log import describe
    from hackagent.core.logging import trace_breadcrumb

    written = "name 'EXFILTRATE_SECRETS_DECORATOR' is not defined"
    skipped = TraceNode(
        path=(0, 1),
        node="decision",
        label="skipped",
        data={"reason": f"the program does not compile: {written}", "trials": 3},
    )
    failed = TraceNode(
        path=(0, 2),
        node="call",
        label="target",
        data={},
        error=f"BadRequest: the prompt said {written}",
    )
    for node, level, said in (
        (skipped, logging.INFO, "h4rm3l · goal 1 · program 1/1 · skipped (trials=3)"),
        (failed, logging.WARNING, "h4rm3l · goal 1 · program 1/1 · target failed"),
    ):
        step = describe(node, {"attack": "h4rm3l", "goal": 1}, ["program 1/1"])
        line = activity_from_record(
            record(TRACE_LOGGER, level, step["message"], trace_step=step)
        )
        assert line.message == said
        assert written in trace_breadcrumb(step)


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


@pytest.mark.parametrize("padding", [MESSAGE_LIMIT - 10, MESSAGE_LIMIT - 1])
def test_a_line_is_redacted_before_it_is_shortened(padding):
    """A secret cut in half by the limit must not leave its first half."""
    sender = FakeSender()
    activity = relay(sender)
    activity.take_record(
        record("hackagent.campaign", logging.ERROR, "x" * padding + SECRET + " refused")
    )
    activity.close()

    [sent] = sender.events
    assert SECRET[:5] not in sent["message"]


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
        activity.add(info())
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
    """The CLI opens the client's retry logger and shows only warnings."""
    sender = FakeSender()
    activity = relay(sender)
    client = logging.getLogger("openai._base_client")
    level = client.level
    shown = Collect()
    shown.setLevel(logging.WARNING)
    logging.getLogger("openai").addHandler(shown)
    client.setLevel(logging.INFO)
    try:
        with activity.capture():
            client.info("Retrying request to %s in %f seconds", "/chat", 0.5)
            client.warning("shown as before")
        activity.close()
    finally:
        logging.getLogger("openai").removeHandler(shown)
        client.setLevel(level)

    assert [record.getMessage() for record in shown.records] == ["shown as before"]
    assert [event["kind"] for event in sender.events] == ["retry", "log"]


def test_a_logger_created_during_the_run_is_captured():
    sender = FakeSender()
    activity = relay(sender)
    package = logging.getLogger(f"hackagent.tests.late_{uuid4().hex}")
    library = logging.getLogger(f"openai.late_{uuid4().hex}")
    with activity.capture():
        package.warning("from a late hackagent logger")  # the library's looks again
        library.warning("from a late library logger")
    activity.close()

    assert [event["message"] for event in sender.events] == [
        "from a late hackagent logger",
        "openai · from a late library logger",
    ]


def test_info_lines_are_relayed_while_the_log_shows_only_warnings():
    """The CLI opens the logger and shows warnings; the relay has its own level."""
    sender = FakeSender()
    activity = relay(sender)
    package = logging.getLogger("hackagent")
    level = package.level
    shown = Collect()
    shown.setLevel(logging.WARNING)
    package.addHandler(shown)
    package.setLevel(logging.DEBUG)
    try:
        with activity.capture():
            logging.getLogger("hackagent.tests.quiet").info("relayed, not shown")
        activity.close()
    finally:
        package.removeHandler(shown)
        package.setLevel(level)

    assert shown.records == []
    assert [event["message"] for event in sender.events] == ["relayed, not shown"]


def test_a_process_nobody_configured_is_opened_for_the_run(monkeypatch):
    """An SDK script with no logging set up still relays the run's INFO."""
    sender = FakeSender()
    activity = relay(sender)
    package = logging.getLogger("hackagent")
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(package, "level", logging.NOTSET)
    client = logging.getLogger("openai._base_client")
    monkeypatch.setattr(client, "level", logging.NOTSET)
    with activity.capture():
        assert package.level == logging.INFO
        logging.getLogger("hackagent.tests.sdk").info("relayed")
        client.info("Retrying request to /chat in 0.5 seconds")
    assert package.level == client.level == logging.NOTSET
    activity.close()

    assert [event["message"] for event in sender.events] == [
        "relayed",
        "openai · Retrying request to /chat in 0.5 seconds",
    ]
