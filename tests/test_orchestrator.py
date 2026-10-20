from datetime import datetime, timedelta, timezone

import pytest

from orchestrator import ExecutionOutcome, MasterOrchestrator, TaskSpec, TaskStatus
from sentinel import AuthorityGrant


def grant(actor="worker"):
    return AuthorityGrant("g1", actor, ("read", "write"), ("repo",), "medium",
                          datetime.now(timezone.utc) + timedelta(hours=1))


def task(task_id="t1", **kw):
    values = dict(task_id=task_id, actor_id="worker", intent="inspect bounded resource",
                  action="read", scope=("repo",), risk="low", grant=grant(),
                  idempotency_key=f"key-{task_id}", acceptance_criteria=("report findings",))
    values.update(kw)
    return TaskSpec(**values)


def test_dry_run_authorizes_without_invoking_executor():
    calls = []
    result = MasterOrchestrator().run([task()], executor=lambda t: calls.append(t), dry_run=True)
    assert result[0].status is TaskStatus.AUTHORIZED
    assert calls == []


def test_non_dry_run_requires_executor():
    with pytest.raises(ValueError, match="executor"):
        MasterOrchestrator().run([task()], dry_run=False)


def test_executor_runs_only_after_authorization():
    calls = []
    result = MasterOrchestrator().run(
        [task()], executor=lambda t: (calls.append(t) or ExecutionOutcome(True, ("artifact://e1",))),
        dry_run=False)
    assert len(calls) == 1
    assert result[0].status is TaskStatus.VERIFIED


def test_invalid_grant_blocks_and_executor_never_runs():
    calls = []
    bad = task(grant=grant(actor="someone-else"))
    result = MasterOrchestrator().run([bad], executor=lambda t: calls.append(t), dry_run=False)
    assert result[0].status is TaskStatus.BLOCKED
    assert calls == []


def test_high_risk_without_human_approval_stops():
    high = task(risk="high", grant=AuthorityGrant(
        "g2", "worker", ("read",), ("repo",), "high",
        datetime.now(timezone.utc) + timedelta(hours=1)))
    result = MasterOrchestrator().run([high], executor=lambda t: None, dry_run=False)
    assert result[0].status is TaskStatus.HUMAN_REVIEW


def test_failed_dependency_skips_downstream_task():
    first = task("first", acceptance_criteria=("verify output",))
    second = task("second", dependencies=("first",))
    result = MasterOrchestrator().run(
        [first, second], executor=lambda t: ExecutionOutcome(False, summary="failed"),
        dry_run=False)
    assert result[0].status is TaskStatus.FAILED
    assert result[1].status is TaskStatus.SKIPPED


def test_uncertain_outcome_is_not_success_and_blocks_dependency():
    first = task("first")
    second = task("second", dependencies=("first",))
    result = MasterOrchestrator().run(
        [first, second], executor=lambda t: ExecutionOutcome(False, uncertain=True),
        dry_run=False)
    assert result[0].status is TaskStatus.UNCERTAIN
    assert result[1].status is TaskStatus.SKIPPED


def test_missing_evidence_or_acceptance_criteria_fails():
    result = MasterOrchestrator().run(
        [task(acceptance_criteria=())],
        executor=lambda t: ExecutionOutcome(True, ("artifact://e1",)), dry_run=False)
    assert result[0].status is TaskStatus.FAILED


def test_duplicate_ids_and_dependency_cycles_rejected():
    orch = MasterOrchestrator()
    with pytest.raises(ValueError, match="duplicate"):
        orch.run([task("same"), task("same")])
    with pytest.raises(ValueError, match="cycle"):
        orch.run([task("a", dependencies=("b",)), task("b", dependencies=("a",))])


def test_plan_size_is_bounded():
    with pytest.raises(ValueError, match="max_tasks"):
        MasterOrchestrator(max_tasks=1).run([task("a"), task("b")])


def test_event_ledger_returns_defensive_copies():
    orch = MasterOrchestrator()
    orch.run([task()])
    event = orch.events[0]
    event["detail"] = "tampered"
    assert orch.events[0]["detail"] != "tampered"


def test_executor_exception_is_uncertain_and_no_implicit_retry():
    calls = []
    def executor(t):
        calls.append(t)
        raise RuntimeError("network lost after request")
    result = MasterOrchestrator().run([task()], executor=executor, dry_run=False)
    assert result[0].status is TaskStatus.UNCERTAIN
    assert len(calls) == 1
