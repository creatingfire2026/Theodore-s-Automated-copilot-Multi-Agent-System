"""Minimal deterministic Sentinel policy engine.

The engine validates action envelopes before execution. It is deliberately
small: model inference belongs outside the authority mechanism.
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

    HIGH_RISK = {"high", "critical"}

    def authorize(self, request: ActionRequest, *, human_approved: bool = False) -> DecisionRecord:
        if not request.actor or not request.intent or not request.trace_id:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "missing attribution or intent")

        if not request.scope:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "empty action scope")

        if request.risk in self.HIGH_RISK and not human_approved:
            return DecisionRecord(request.trace_id, Decision.HUMAN_REVIEW, "high-impact action requires human approval")

        if not request.authority:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "no authority basis supplied")

        return DecisionRecord(request.trace_id, Decision.AUTHORIZED, "policy checks passed")

    def verify(self, record: DecisionRecord, success: bool) -> DecisionRecord:
        if record.decision != Decision.AUTHORIZED:
            return record
        if success:
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
