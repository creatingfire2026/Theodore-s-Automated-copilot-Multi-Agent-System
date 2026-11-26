"""Minimal deterministic Sentinel policy engine."""
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar
from uuid import uuid4

from dissent_store import DissentStore, DissentStoreError, dissent_matches

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
    """Untrusted CI run reference; fields are claims, not proof."""
    __test__: ClassVar[bool] = False
    run_id: str
    conclusion: str


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
    aud: str = ""
    test_result: TestResult | None = None
    protected_dissent_node: str | None = None
    protected_dissent_id: str | None = None


@dataclass(frozen=True)
class HumanApproval:
    """Untrusted approval envelope; signature authenticity is delegated to verifier."""
    approval_id: str
    human_id: str
    trace_id: str
    action: str
    scope: tuple[str, ...]
    expires_at: str
    signature: str
    dissent_override_id: str | None = None
    justification: str = ""


@dataclass
class DecisionRecord:
    trace_id: str
    decision: Decision
    reason: str


RunEvidenceVerifier = Callable[[TestResult, ActionRequest | None], bool]
HumanApprovalVerifier = Callable[[HumanApproval, ActionRequest], bool]


class Sentinel:
    """Policy gate. VERIFIED requires an independently configured CI verifier."""
    HIGH_RISK = {"high", "critical"}
    KNOWN_RISK = {"low", "medium", "high", "critical"}

    def __init__(
        self,
        agent_id: str = "sentinel",
        *,
        on_reject: Callable[[ActionRequest, DecisionRecord], None] | None = None,
        run_evidence_verifier: RunEvidenceVerifier | None = None,
        human_approval_verifier: HumanApprovalVerifier | None = None,
        dissent_store: DissentStore | None = None,
        require_dissent_store: bool | None = None,
    ) -> None:
        if not agent_id:
            raise ValueError("Sentinel needs a non-empty agent_id")
        self.agent_id = agent_id
        self.on_reject = on_reject
        self.run_evidence_verifier = run_evidence_verifier
        self.human_approval_verifier = human_approval_verifier
        # F34: Sentinel looks protected A7 dissents up itself instead of trusting the caller.
        self.dissent_store = dissent_store if dissent_store is not None else DissentStore.from_env()
        if require_dissent_store is None:
            require_dissent_store = os.environ.get("SENTINEL_REQUIRE_DISSENT_STORE", "") == "1"
        self.require_dissent_store = require_dissent_store

    def _check_dissent_store(self, request: ActionRequest) -> tuple[DecisionRecord | None, bool]:
        """Return (rejection or None, hinted_dissent_cleared). Any store failure fails closed."""
        if self.dissent_store is None:
            if self.require_dissent_store:
                return self._reject(request, Decision.HUMAN_REVIEW, "dissent store required but not configured"), False
            return None, False  # legacy mode: only the caller-supplied hint is honored
        try:
            open_dissents = self.dissent_store.open_dissents()
            known = self.dissent_store.known_dissent_ids() if request.protected_dissent_id else set()
        except DissentStoreError as exc:
            return self._reject(request, Decision.HUMAN_REVIEW, f"dissent store failed integrity check: {exc}"), False
        except Exception as exc:  # noqa: BLE001 - unexpected failure must not authorize
            logger.exception("dissent store raised for trace=%s", request.trace_id)
            return self._reject(request, Decision.HUMAN_REVIEW, f"dissent store error: {exc.__class__.__name__}"), False
        for dissent in open_dissents:
            if dissent.dissent_id == request.protected_dissent_id or dissent_matches(
                dissent, trace_id=request.trace_id, intent=request.intent, scope=list(request.scope),
            ):
                return self._reject(
                    request, Decision.HUMAN_REVIEW,
                    f"open protected A7 dissent {dissent.dissent_id!r} on {dissent.target!r} requires a signed human receipt",
                ), False
        if request.protected_dissent_id:
            if request.protected_dissent_id not in known:
                return self._reject(request, Decision.HUMAN_REVIEW,
                                    f"claimed dissent {request.protected_dissent_id!r} is not in the dissent store"), False
            return None, True  # hinted dissent exists and has a valid human receipt
        return None, False

    def _reject(self, request: ActionRequest, decision: Decision, reason: str) -> DecisionRecord:
        record = DecisionRecord(request.trace_id, decision, reason)
        logger.warning(
            "sentinel %s trace=%s actor=%s aud=%r: %s",
            decision.value, request.trace_id, request.actor, request.aud, reason,
        )
        if self.on_reject is not None:
            self.on_reject(request, record)
        return record

    def authorize(self, request: ActionRequest, *, human_approval: HumanApproval | None = None) -> DecisionRecord:
        if not request.aud:
            return self._reject(request, Decision.BLOCKED, "missing audience (aud)")
        if request.aud != self.agent_id:
            return self._reject(
                request, Decision.BLOCKED,
                f"wrong audience: envelope addressed to {request.aud!r}, receiver is {self.agent_id!r}",
            )
        if not request.actor or not request.intent or not request.trace_id:
            return self._reject(request, Decision.BLOCKED, "missing attribution or intent")
        if not request.scope:
            return self._reject(request, Decision.BLOCKED, "empty action scope")
        risk = request.risk.strip().lower() if isinstance(request.risk, str) else ""
        if risk not in self.KNOWN_RISK:
            # Fail closed: an unknown or miscased label must never be treated as low risk.
            return self._reject(request, Decision.BLOCKED, f"unknown risk label {request.risk!r}")
        dissent_rejection, hint_cleared = self._check_dissent_store(request)
        if dissent_rejection is not None:
            return dissent_rejection
        requires_human = risk in self.HIGH_RISK
        legacy_hint = bool(request.protected_dissent_id) and not hint_cleared
        if requires_human or legacy_hint:
            approval = human_approval
            if approval is None:
                reason = "protected A7 dissent requires an authenticated human override" if legacy_hint else "high-impact action requires authenticated human approval"
                return self._reject(request, Decision.HUMAN_REVIEW, reason)
            if not (
                approval.approval_id
                and approval.human_id
                and approval.signature
                and approval.expires_at
                and approval.trace_id == request.trace_id
                and approval.action == request.intent
                and approval.scope == tuple(request.scope)
            ):
                return self._reject(request, Decision.HUMAN_REVIEW, "human approval is incomplete or not bound to this action")
            if legacy_hint:
                if request.protected_dissent_node != "A7":
                    return self._reject(request, Decision.BLOCKED, "protected dissent source must be council node A7")
                if approval.dissent_override_id != request.protected_dissent_id or not approval.justification.strip():
                    return self._reject(request, Decision.HUMAN_REVIEW, "human override must reference the exact protected dissent and include justification")
            if self.human_approval_verifier is None:
                return self._reject(request, Decision.HUMAN_REVIEW, "no independent human-approval verifier configured")
            try:
                approved = self.human_approval_verifier(approval, request)
            except Exception:
                logger.exception("human approval verifier raised for trace=%s", request.trace_id)
                approved = False
            if not approved:
                return self._reject(request, Decision.HUMAN_REVIEW, "human approval signature, identity, scope, or expiry verification failed")
        if not request.authority:
            return self._reject(request, Decision.BLOCKED, "no authority basis supplied")
        return DecisionRecord(request.trace_id, Decision.AUTHORIZED, "policy checks passed")

    def verify(
        self,
        record: DecisionRecord,
        success: bool,
        test_result: TestResult | None = None,
        *,
        request: ActionRequest | None = None,
    ) -> DecisionRecord:
        """Settle an authorized action; fail closed without independent CI proof."""
        if record.decision != Decision.AUTHORIZED:
            return record
        if not success:
            return DecisionRecord(record.trace_id, Decision.FAILED, "execution failed verification")

        attestation = test_result or (request.test_result if request is not None else None)
        if attestation is None or not attestation.run_id:
            reason = "no test-result run reference supplied"
        elif self.run_evidence_verifier is None:
            reason = "no independent CI evidence verifier configured"
        else:
            try:
                trusted = self.run_evidence_verifier(attestation, request)
            except Exception:
                logger.exception("CI evidence verifier raised for trace=%s", record.trace_id)
                trusted = False
            if trusted:
                return DecisionRecord(
                    record.trace_id, Decision.VERIFIED,
                    f"execution independently verified by CI run {attestation.run_id}",
                )
            reason = f"independent CI evidence verification rejected run {attestation.run_id}"

        failed = DecisionRecord(record.trace_id, Decision.FAILED, reason)
        logger.warning("sentinel failed trace=%s: %s", record.trace_id, reason)
        if self.on_reject is not None and request is not None:
            self.on_reject(request, failed)
        return failed


if __name__ == "__main__":
    sentinel = Sentinel()
    request = ActionRequest(
        actor="demo-agent", intent="perform a bounded test action",
        scope=["demo"], authority="test-policy", aud="sentinel",
    )
    print(sentinel.authorize(request))
