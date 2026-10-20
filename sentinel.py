"""Deterministic Sentinel authorization gate (v1).

This module validates a bounded action request before any executor performs side
effects. It intentionally contains no model inference, network access, or executor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    UNCERTAIN = "uncertain"


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class AuthorityGrant:
    """Explicit, time-limited authority for one actor and bounded resources."""

    grant_id: str
    actor_id: str
    allowed_actions: tuple[str, ...]
    allowed_scope: tuple[str, ...]
    risk_ceiling: str
    expires_at: datetime


@dataclass
class ActionRequest:
    actor: str
    intent: str
    scope: list[str]
    authority: str = ""
    risk: str = "low"
    preconditions: list[str] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    action: str = "execute"
    grant: AuthorityGrant | None = None
    idempotency_key: str = ""
    preconditions_valid: bool = True


@dataclass(frozen=True)
class DecisionRecord:
    trace_id: str
    decision: Decision
    reason: str
    idempotency_key: str = ""


class Sentinel:
    """Small deterministic policy gate with in-process duplicate protection.

    The decision/idempotency ledger is process-local in v1. It is not durable
    across restarts or shared across workers; persistent event storage is a
    later phase and must not be implied by this implementation.
    """

    def __init__(self) -> None:
        self._decisions_by_key: dict[str, DecisionRecord] = {}

    def authorize(
        self,
        request: ActionRequest,
        *,
        human_approved: bool = False,
        approval_ref: str = "",
    ) -> DecisionRecord:
        key = request.idempotency_key

        # Once a key has a decision, retries cannot change that decision.
        if key and key in self._decisions_by_key:
            prior = self._decisions_by_key[key]
            return DecisionRecord(
                request.trace_id,
                Decision.BLOCKED,
                f"idempotency key already used; prior decision was {prior.decision.value}",
                key,
            )

        def decide(decision: Decision, reason: str) -> DecisionRecord:
            record = DecisionRecord(request.trace_id, decision, reason, key)
            if key:
                self._decisions_by_key[key] = record
            return record

        if not isinstance(request.actor, str) or not request.actor.strip():
            return decide(Decision.BLOCKED, "missing actor identity")
        if not isinstance(request.intent, str) or not request.intent.strip():
            return decide(Decision.BLOCKED, "missing intent")
        if not isinstance(request.trace_id, str) or not request.trace_id.strip():
            return decide(Decision.BLOCKED, "missing trace ID")
        if not isinstance(request.scope, list) or not request.scope or any(
            not isinstance(item, str) or not item.strip() for item in request.scope
        ):
            return decide(Decision.BLOCKED, "empty or invalid action scope")
        if not isinstance(request.action, str) or not request.action.strip():
            return decide(Decision.BLOCKED, "missing action type")
        if request.risk not in RISK_ORDER:
            return decide(Decision.BLOCKED, "invalid risk label")
        if not key or not key.strip():
            return decide(Decision.BLOCKED, "missing idempotency key")
        if not request.preconditions_valid:
            return decide(Decision.BLOCKED, "preconditions are stale or failed")

        grant = request.grant
        if grant is None:
            return decide(Decision.BLOCKED, "no explicit authority grant supplied")
        if not grant.grant_id or not grant.actor_id:
            return decide(Decision.BLOCKED, "grant identity is incomplete")
        if grant.actor_id != request.actor:
            return decide(Decision.BLOCKED, "grant actor does not match request actor")
        if request.action not in grant.allowed_actions:
            return decide(Decision.BLOCKED, "action is outside grant")
        if not set(request.scope).issubset(set(grant.allowed_scope)):
            return decide(Decision.BLOCKED, "requested scope exceeds grant")
        if grant.risk_ceiling not in RISK_ORDER:
            return decide(Decision.BLOCKED, "grant has invalid risk ceiling")
        if RISK_ORDER[request.risk] > RISK_ORDER[grant.risk_ceiling]:
            return decide(Decision.BLOCKED, "requested risk exceeds grant ceiling")
        if not isinstance(grant.expires_at, datetime) or grant.expires_at.tzinfo is None:
            return decide(Decision.BLOCKED, "grant expiry must be timezone-aware")
        if grant.expires_at <= datetime.now(timezone.utc):
            return decide(Decision.BLOCKED, "authority grant has expired")

        if request.risk in {"high", "critical"}:
            if not human_approved or not approval_ref.strip():
                return decide(
                    Decision.HUMAN_REVIEW,
                    "high-impact action requires explicit human approval reference",
                )

        return decide(Decision.AUTHORIZED, "policy checks passed")

    def verify(self, record: DecisionRecord, success: bool) -> DecisionRecord:
        if record.decision is not Decision.AUTHORIZED:
            return record
        if success:
            return DecisionRecord(
                record.trace_id, Decision.VERIFIED, "execution verified",
                record.idempotency_key,
            )
        return DecisionRecord(
            record.trace_id, Decision.FAILED, "execution failed verification",
            record.idempotency_key,
        )


if __name__ == "__main__":
    sentinel = Sentinel()
    grant = AuthorityGrant(
        grant_id="demo-grant",
        actor_id="demo-agent",
        allowed_actions=("execute",),
        allowed_scope=("demo",),
        risk_ceiling="low",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    request = ActionRequest(
        actor="demo-agent",
        intent="perform a bounded test action",
        scope=["demo"],
        authority="demo-policy",
        grant=grant,
        idempotency_key="demo-action-001",
    )
    print(sentinel.authorize(request))
