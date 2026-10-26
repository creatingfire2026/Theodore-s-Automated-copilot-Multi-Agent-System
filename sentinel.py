"""Minimal deterministic Sentinel policy engine.

This is a local policy gate, not a complete production authorization service.
In particular, callers must authenticate human approvals before passing
human_approved=True; durable grants, audit persistence, and runtime mediation
remain separate integration requirements.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class Decision(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"
    EXECUTING = "executing"
    VERIFIED = "verified"
    FAILED = "failed"
    HUMAN_REVIEW = "human_review"


@dataclass
class ActionRequest:
    actor: str
    intent: str
    scope: list[str]
    authority: str
    risk: str = "low"
    preconditions: list[str] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class DecisionRecord:
    trace_id: str
    decision: Decision
    reason: str


class Sentinel:
    """Small policy gate with explicit, inspectable decisions."""

    ALLOWED_RISKS = {"low", "medium", "high", "critical"}
    HIGH_RISK = {"high", "critical"}

    def authorize(self, request: ActionRequest, *, human_approved: bool = False) -> DecisionRecord:
        # Reject malformed or whitespace-only attribution rather than allowing
        # truthy-but-invalid values through the authorization boundary.
        if not all(
            isinstance(value, str) and value.strip()
            for value in (request.actor, request.intent, request.trace_id)
        ):
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "missing attribution or intent")

        if not isinstance(request.scope, list) or not request.scope or any(
            not isinstance(item, str) or not item.strip() for item in request.scope
        ):
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "empty or invalid action scope")

        if not isinstance(request.risk, str) or request.risk not in self.ALLOWED_RISKS:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "unknown or invalid risk classification")

        if not isinstance(request.authority, str) or not request.authority.strip():
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "no authority basis supplied")

        if request.risk in self.HIGH_RISK and human_approved is not True:
            return DecisionRecord(request.trace_id, Decision.HUMAN_REVIEW, "high-impact action requires human approval")

        return DecisionRecord(request.trace_id, Decision.AUTHORIZED, "policy checks passed")

    def verify(self, record: DecisionRecord, success: bool) -> DecisionRecord:
        if record.decision != Decision.AUTHORIZED:
            return record
        if success is True:
            return DecisionRecord(record.trace_id, Decision.VERIFIED, "execution verified")
        return DecisionRecord(record.trace_id, Decision.FAILED, "execution failed verification")


if __name__ == "__main__":
    sentinel = Sentinel()
    request = ActionRequest(
        actor="demo-agent",
        intent="perform a bounded test action",
        scope=["demo"],
        authority="test-policy",
    )
    decision = sentinel.authorize(request)
    print(decision)
