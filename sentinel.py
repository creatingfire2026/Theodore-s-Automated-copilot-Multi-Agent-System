"""Minimal deterministic Sentinel policy engine.

The engine validates action envelopes before execution. It is deliberately
small: model inference belongs outside the authority mechanism.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar
from uuid import uuid4

logger = logging.getLogger("sentinel")


class Decision(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"
    EXECUTING = "executing"
    VERIFIED = "verified"
    FAILED = "failed"
    HUMAN_REVIEW = "human_review"


@dataclass(frozen=True)
class TestResult:
    """CI attestation carried by an envelope (AIP-001 amendment).

    Only conclusion == "success" with a non-empty run_id counts as verified. Anything
    else (failure, cancelled, startup_failure, skipped, missing) does not.
    """

    __test__: ClassVar[bool] = False  # not a pytest test class

    run_id: str
    conclusion: str

    @property
    def passed(self) -> bool:
        return bool(self.run_id) and self.conclusion == "success"


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
    # Required (AIP-001 amendment): the agent this envelope is addressed to. Defaults to
    # empty so that an envelope without an audience is rejected rather than accepted.
    aud: str = ""
    test_result: TestResult | None = None


@dataclass
class DecisionRecord:
    trace_id: str
    decision: Decision
    reason: str


class Sentinel:
    """Small policy gate with explicit, inspectable decisions.

    ``agent_id`` names the receiving agent this gate protects; envelopes must carry a
    matching ``aud``. ``on_reject`` (optional) receives every rejected request and its
    decision record, e.g. to write a Ghost in the Gate tombstone.
    """

    HIGH_RISK = {"high", "critical"}

    def __init__(
        self,
        agent_id: str = "sentinel",
        *,
        on_reject: Callable[[ActionRequest, DecisionRecord], None] | None = None,
    ) -> None:
        if not agent_id:
            raise ValueError("Sentinel needs a non-empty agent_id to check envelope audience")
        self.agent_id = agent_id
        self.on_reject = on_reject

    def _reject(self, request: ActionRequest, decision: Decision, reason: str) -> DecisionRecord:
        record = DecisionRecord(request.trace_id, decision, reason)
        logger.warning(
            "sentinel %s trace=%s actor=%s aud=%r: %s",
            decision.value,
            request.trace_id,
            request.actor,
            request.aud,
            reason,
        )
        if self.on_reject is not None:
            self.on_reject(request, record)
        return record

    def authorize(self, request: ActionRequest, *, human_approved: bool = False) -> DecisionRecord:
        if not request.aud:
            return self._reject(request, Decision.BLOCKED, "missing audience (aud)")
        if request.aud != self.agent_id:
            return self._reject(
                request,
                Decision.BLOCKED,
                f"wrong audience: envelope addressed to {request.aud!r}, receiver is {self.agent_id!r}",
            )

        if not request.actor or not request.intent or not request.trace_id:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "missing attribution or intent")

        if not request.scope:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "empty action scope")

        if request.risk in self.HIGH_RISK and not human_approved:
            return DecisionRecord(request.trace_id, Decision.HUMAN_REVIEW, "high-impact action requires human approval")

        if not request.authority:
            return DecisionRecord(request.trace_id, Decision.BLOCKED, "no authority basis supplied")

        return DecisionRecord(request.trace_id, Decision.AUTHORIZED, "policy checks passed")

    def verify(
        self,
        record: DecisionRecord,
        success: bool,
        test_result: TestResult | None = None,
        *,
        request: ActionRequest | None = None,
    ) -> DecisionRecord:
        """Settle an authorized action. VERIFIED requires a passing CI attestation.

        ``test_result`` (or ``request.test_result``) must hold a run ID with conclusion
        "success". A missing attestation or any other conclusion, including a run that
        never started (``startup_failure``), is FAILED with the reason recorded.
        """
        if record.decision != Decision.AUTHORIZED:
            return record
        if not success:
            return DecisionRecord(record.trace_id, Decision.FAILED, "execution failed verification")
        attestation = test_result or (request.test_result if request is not None else None)
        if attestation is None or not attestation.run_id:
            reason = "no test-result attestation (run_id + conclusion) supplied"
        elif not attestation.passed:
            reason = f"test run {attestation.run_id} concluded {attestation.conclusion!r}, not 'success'"
        else:
            return DecisionRecord(
                record.trace_id, Decision.VERIFIED, f"execution verified by test run {attestation.run_id}"
            )
        failed = DecisionRecord(record.trace_id, Decision.FAILED, reason)
        logger.warning("sentinel failed trace=%s: %s", record.trace_id, reason)
        if self.on_reject is not None and request is not None:
            self.on_reject(request, failed)
        return failed


if __name__ == "__main__":
    sentinel = Sentinel()
    request = ActionRequest(
        actor="demo-agent",
        intent="perform a bounded test action",
        scope=["demo"],
        authority="test-policy",
        aud="sentinel",
    )
    decision = sentinel.authorize(request)
    print(decision)
