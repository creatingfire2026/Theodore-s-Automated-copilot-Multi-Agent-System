"""Bounded, Sentinel-gated Master Orchestrator.

This module plans and coordinates tasks. It does not grant authority, perform
implicit retries, or run side effects in dry-run mode. An injected executor is
called only after Sentinel returns AUTHORIZED. Persistence and authenticated
identity/approval integrations are intentionally outside this in-memory module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable
from uuid import uuid4

from sentinel import ActionRequest, AuthorityGrant, Decision, DecisionRecord, Sentinel


class TaskStatus(str, Enum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    HUMAN_REVIEW = "human_review"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    VERIFIED = "verified"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    actor_id: str
    intent: str
    action: str
    scope: tuple[str, ...]
    risk: str
    grant: AuthorityGrant
    idempotency_key: str
    dependencies: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    preconditions_valid: bool = True
    human_approved: bool = False
    approval_ref: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ExecutionOutcome:
    """Executor-reported outcome. Evidence references must be independently reviewable."""

    success: bool
    evidence_refs: tuple[str, ...] = ()
    uncertain: bool = False
    summary: str = ""


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: TaskStatus
    reason: str
    trace_id: str
    decision: Decision | None = None
    evidence_refs: tuple[str, ...] = ()


Executor = Callable[[TaskSpec], ExecutionOutcome]


class MasterOrchestrator:
    """Validate plan topology, authorize every task, then coordinate bounded work."""

    def __init__(self, sentinel: Sentinel | None = None, *, max_tasks: int = 100) -> None:
        if not isinstance(max_tasks, int) or isinstance(max_tasks, bool) or max_tasks < 1:
            raise ValueError("max_tasks must be a positive integer")
        self.sentinel = sentinel or Sentinel()
        self.max_tasks = max_tasks
        self._records: dict[str, TaskRecord] = {}
        self._events: list[dict[str, str]] = []

    @property
    def records(self) -> tuple[TaskRecord, ...]:
        return tuple(self._records.values())

    @property
    def events(self) -> tuple[dict[str, str], ...]:
        # Return copies so callers cannot mutate the internal event ledger.
        return tuple(dict(event) for event in self._events)

    def _event(self, event: str, task: TaskSpec, status: TaskStatus, detail: str) -> None:
        self._events.append({
            "event": event,
            "task_id": task.task_id,
            "trace_id": task.trace_id,
            "actor_id": task.actor_id,
            "status": status.value,
            "detail": detail,
        })

    def _record(self, task: TaskSpec, status: TaskStatus, reason: str,
                decision: Decision | None = None,
                evidence_refs: tuple[str, ...] = ()) -> TaskRecord:
        record = TaskRecord(task.task_id, status, reason, task.trace_id, decision, evidence_refs)
        self._records[task.task_id] = record
        self._event("TASK_STATE", task, status, reason)
        return record

    @staticmethod
    def _topological_order(tasks: tuple[TaskSpec, ...]) -> tuple[list[TaskSpec], str | None]:
        by_id: dict[str, TaskSpec] = {}
        for task in tasks:
            if not isinstance(task, TaskSpec) or not isinstance(task.task_id, str) or not task.task_id.strip():
                return [], "every task must have a non-empty task ID and be a TaskSpec"
            if task.task_id in by_id:
                return [], f"duplicate task ID: {task.task_id}"
            by_id[task.task_id] = task
        for task in tasks:
            if any(dep not in by_id for dep in task.dependencies):
                return [], f"task {task.task_id} references an unknown dependency"
            if task.task_id in task.dependencies:
                return [], f"task {task.task_id} depends on itself"

        remaining = dict(by_id)
        ordered: list[TaskSpec] = []
        completed: set[str] = set()
        while remaining:
            ready = [task for task in remaining.values()
                     if set(task.dependencies).issubset(completed)]
            if not ready:
                return [], "dependency cycle detected"
            for task in ready:
                ordered.append(task)
                completed.add(task.task_id)
                del remaining[task.task_id]
        return ordered, None

    def run(self, tasks: Iterable[TaskSpec], *, executor: Executor | None = None,
            dry_run: bool = True) -> tuple[TaskRecord, ...]:
        """Run a plan sequentially. Dry-run is default; no executor means no side effects."""
        task_list = tuple(tasks)
        if len(task_list) > self.max_tasks:
            raise ValueError(f"plan exceeds max_tasks={self.max_tasks}")
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be bool")
        if not dry_run and executor is None:
            raise ValueError("executor is required when dry_run=False")

        ordered, topology_error = self._topological_order(task_list)
        if topology_error:
            raise ValueError(topology_error)

        run_records: dict[str, TaskRecord] = {}
        for task in ordered:
            failed_deps = [dep for dep in task.dependencies
                           if dep not in run_records or run_records[dep].status is not TaskStatus.VERIFIED]
            if failed_deps:
                run_records[task.task_id] = self._record(
                    task, TaskStatus.SKIPPED,
                    "dependency not verified: " + ", ".join(failed_deps))
                continue

            request = ActionRequest(
                actor=task.actor_id,
                intent=task.intent,
                scope=list(task.scope),
                trace_id=task.trace_id,
                action=task.action,
                risk=task.risk,
                grant=task.grant,
                idempotency_key=task.idempotency_key,
                preconditions_valid=task.preconditions_valid,
            )
            decision_record: DecisionRecord = self.sentinel.authorize(
                request,
                human_approved=task.human_approved,
                approval_ref=task.approval_ref,
            )
            self._event("POLICY_DECISION", task, TaskStatus.AUTHORIZED
                        if decision_record.decision is Decision.AUTHORIZED
                        else TaskStatus.BLOCKED, decision_record.reason)

            if decision_record.decision is Decision.HUMAN_REVIEW:
                run_records[task.task_id] = self._record(
                    task, TaskStatus.HUMAN_REVIEW, decision_record.reason,
                    decision_record.decision)
                continue
            if decision_record.decision is not Decision.AUTHORIZED:
                run_records[task.task_id] = self._record(
                    task, TaskStatus.BLOCKED, decision_record.reason,
                    decision_record.decision)
                continue

            if dry_run:
                run_records[task.task_id] = self._record(
                    task, TaskStatus.AUTHORIZED,
                    "authorization passed; dry-run prevented execution",
                    decision_record.decision)
                continue

            try:
                self._record(task, TaskStatus.EXECUTING, "executor invoked after authorization",
                             decision_record.decision)
                outcome = executor(task)  # type: ignore[misc]
                if not isinstance(outcome, ExecutionOutcome):
                    run_records[task.task_id] = self._record(
                        task, TaskStatus.UNCERTAIN,
                        "executor returned an invalid outcome; side effects frozen",
                        Decision.UNCERTAIN)
                elif outcome.uncertain:
                    run_records[task.task_id] = self._record(
                        task, TaskStatus.UNCERTAIN,
                        outcome.summary or "outcome uncertain; side effects frozen",
                        Decision.UNCERTAIN, outcome.evidence_refs)
                elif outcome.success is True and outcome.evidence_refs and task.acceptance_criteria:
                    verified = self.sentinel.verify(decision_record, success=True)
                    run_records[task.task_id] = self._record(
                        task, TaskStatus.VERIFIED,
                        "executor reported success with evidence references; acceptance criteria recorded",
                        verified.decision, outcome.evidence_refs)
                else:
                    failed = self.sentinel.verify(decision_record, success=False)
                    run_records[task.task_id] = self._record(
                        task, TaskStatus.FAILED,
                        outcome.summary or "success, evidence, or acceptance criteria missing",
                        failed.decision, outcome.evidence_refs)
            except Exception as exc:  # Fail closed; never retry implicitly.
                run_records[task.task_id] = self._record(
                    task, TaskStatus.UNCERTAIN,
                    f"executor raised {type(exc).__name__}; outcome requires reconciliation",
                    Decision.UNCERTAIN)

        return tuple(run_records[task.task_id] for task in ordered)
