# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Verdict writes land only for judged rows that carry ``result_id``."""

from uuid import UUID, uuid4

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import EvalStatus, JudgeVote, Verdict
from hackagent.orchestrator.results.persistence import StoreSink
from hackagent.orchestrator.execution.runner import _persist_verdicts


class RecordingRunSink:
    """Orchestrator-local stand-in that records verdict writes."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.verdicts: list[tuple[UUID, AttackResult]] = []
        self.fail_on = fail_on

    def write_verdict(self, result_id: UUID, result: AttackResult):
        if self.fail_on is not None and result.goal == self.fail_on:
            raise RuntimeError("sink down")
        self.verdicts.append((result_id, result))


class RecordingStore:
    def __init__(self) -> None:
        self.updates: list[tuple] = []
        self.flushes = 0

    def update_result(self, result_id, **kwargs):
        self.updates.append((result_id, kwargs))
        return {"id": result_id, **kwargs}

    def flush(self) -> None:
        self.flushes += 1


class _NoFlush:
    def update_result(self, result_id, **kwargs):
        return {"id": result_id, **kwargs}


def _judged(**kwargs) -> AttackResult:
    verdict = kwargs.pop(
        "verdict",
        Verdict(
            success=True,
            score=8.0,
            explanation="harmful",
            votes=[JudgeVote(judge="harmbench", score=1.0, success=True)],
        ),
    )
    return AttackResult(
        goal=kwargs.pop("goal", "goal"),
        prompt="prompt",
        response=kwargs.pop("response", "hello"),
        verdict=verdict,
        metadata=kwargs.pop("metadata", {}),
    )


def test_persist_verdicts_writes_only_judged_rows_with_a_result_id():
    sink = RecordingRunSink()
    result_id = uuid4()
    kept = _judged(metadata={"result_id": str(result_id)})
    skipped = [
        _judged(goal="no-id"),
        _judged(goal="empty-id", metadata={"result_id": ""}),
        AttackResult(
            goal="unjudged",
            response="hello",
            metadata={"result_id": str(uuid4())},
        ),
    ]
    _persist_verdicts(sink, [kept, *skipped])
    assert len(sink.verdicts) == 1
    written_id, written = sink.verdicts[0]
    assert written_id == result_id
    assert written is kept


def test_persist_verdicts_continues_after_a_write_failure():
    sink = RecordingRunSink(fail_on="boom")
    first = uuid4()
    second = uuid4()
    _persist_verdicts(
        sink,
        [
            _judged(goal="boom", metadata={"result_id": str(first)}),
            _judged(goal="next", metadata={"result_id": str(second)}),
        ],
    )
    assert [item[0] for item in sink.verdicts] == [second]


def test_store_sink_maps_the_verdict_and_flushes():
    store = RecordingStore()
    sink = StoreSink(store)
    result_id = uuid4()
    result = _judged()
    sink.write_verdict(result_id, result)
    sink.flush()

    assert store.flushes == 1
    assert len(store.updates) == 1
    written_id, payload = store.updates[0]
    assert written_id == result_id
    assert payload["evaluation_status"] == EvalStatus.SUCCESSFUL_JAILBREAK.value
    assert payload["evaluation_notes"] == "harmful"
    assert payload["evaluation_metrics"]["eval_hb"] == 1
    assert payload["evaluation_metrics"]["eval_hb_mean"] == 1.0


def test_store_sink_flush_is_a_no_op_without_a_store_flush():
    sink = StoreSink(_NoFlush())
    sink.flush()
    failed = _judged(verdict=Verdict(success=False, score=1.0, explanation=""))
    payload = sink.write_verdict(uuid4(), failed)
    assert payload["evaluation_status"] == EvalStatus.FAILED_JAILBREAK.value
    assert payload["evaluation_notes"] == ""
