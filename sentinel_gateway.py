"""B4 core: the three Sentinel MCP tools, independent of the MCP SDK (so it is unit-testable).

* ``read_status``    - low risk, no approval: Sentinel/verifier/dissent-store/audit health.
* ``propose_action`` - records a proposal in the hash-chained audit log and returns the
                       canonical approval payload (base64) for the human to sign offline.
* ``execute_action`` - high risk: rebuilds the ActionRequest from the logged proposal plus the
                       caller's args, sends it through ``Sentinel.authorize`` (risk labels,
                       dissent store, Ed25519 approval verifier), logs the decision, and in
                       dry-run mode (the default, and the only mode implemented) only records
                       what it *would* have done.
"""
from __future__ import annotations

import base64
import os
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from approval_verifier import (
    ApprovalError, Ed25519ApprovalVerifier, approval_payload, args_sha256, format_expiry, parse_approval_payload,
)
from audit_log import ENV_AUDIT_DB, AuditLog, AuditLogError
from dissent_store import DissentStoreError
from sentinel import ActionRequest, Decision, HumanApproval, Sentinel

ENV_DRY_RUN = "SENTINEL_MCP_DRY_RUN"
ENV_APPROVAL_TTL = "SENTINEL_APPROVAL_TTL_SECONDS"
MAX_TEXT = 512
MAX_SCOPE = 32


def _text(value: Any, label: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be a non-empty string of at most {limit} chars")
    return value


class SentinelGateway:
    def __init__(self, sentinel: Sentinel, audit: AuditLog, *, human_id: str = "theodore",
                 approval_ttl: timedelta = timedelta(minutes=15), dry_run: bool = True,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.sentinel = sentinel
        self.audit = audit
        self.human_id = human_id
        self.approval_ttl = approval_ttl
        self.dry_run = dry_run
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def audience(self) -> str:
        return self.sentinel.agent_id

    @classmethod
    def from_env(cls) -> "SentinelGateway":
        audience = os.environ.get("SENTINEL_MCP_AUDIENCE", "sentinel-mcp")
        verifier = Ed25519ApprovalVerifier.from_env(audience=audience)  # None => every execute fails closed
        sentinel = Sentinel(audience, human_approval_verifier=verifier)
        audit = AuditLog(os.environ.get(ENV_AUDIT_DB, str(Path("~/.sentinel/mcp_audit.db").expanduser())))
        ttl = timedelta(seconds=int(os.environ.get(ENV_APPROVAL_TTL, "900")))
        return cls(sentinel, audit, human_id=os.environ.get("SENTINEL_HUMAN_ID", "theodore"),
                   approval_ttl=ttl, dry_run=os.environ.get(ENV_DRY_RUN, "1") != "0")

    # --- read_status -------------------------------------------------------------------
    def read_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "audience": self.audience,
            "dry_run": self.dry_run,
            "approval_verifier": type(self.sentinel.human_approval_verifier).__name__
            if self.sentinel.human_approval_verifier is not None else None,
            "require_dissent_store": self.sentinel.require_dissent_store,
        }
        store = self.sentinel.dissent_store
        if store is None:
            status["dissent_store"] = {"configured": False}
        else:
            try:
                status["dissent_store"] = {"configured": True, "ok": True,
                                           "open_dissents": [d.dissent_id for d in store.open_dissents()]}
            except (DissentStoreError, Exception) as exc:  # noqa: BLE001 - report, never raise
                status["dissent_store"] = {"configured": True, "ok": False, "error": exc.__class__.__name__}
        try:
            count, head = self.audit.head()
            status["audit_log"] = {"ok": True, "entries": count, "head": head}
        except AuditLogError as exc:
            status["audit_log"] = {"ok": False, "error": str(exc)}
        return status

    # --- propose_action ----------------------------------------------------------------
    def propose_action(self, *, tool: str, args: dict[str, Any], intent: str, scope: list[str],
                       risk: str = "high", actor: str = "mcp-client") -> dict[str, Any]:
        tool = _text(tool, "tool", 128)
        intent = _text(intent, "intent")
        actor = _text(actor, "actor", 128)
        if not isinstance(scope, list) or not scope or len(scope) > MAX_SCOPE:
            raise ValueError(f"scope must be a list of 1-{MAX_SCOPE} strings")
        scope = [_text(s, "scope entry", 128) for s in scope]
        label = risk.strip().lower() if isinstance(risk, str) else ""
        if label not in Sentinel.KNOWN_RISK:
            raise ValueError(f"unknown risk label {risk!r}")
        effective_risk = "critical" if label == "critical" else "high"  # execute_action is always high risk
        digest = args_sha256(args)
        action_id = f"act-{uuid4()}"
        trace_id = str(uuid4())
        expires_at = format_expiry(self.clock() + self.approval_ttl)
        payload = approval_payload(
            action_id=action_id, trace_id=trace_id, human_id=self.human_id, aud=self.audience, tool=tool,
            args_sha256=digest, intent=intent, scope=scope, risk=effective_risk,
            nonce=secrets.token_hex(16), expires_at=expires_at,
        )
        payload_b64 = base64.b64encode(payload).decode("ascii")
        self.audit.append("proposal", {"action_id": action_id, "actor": actor, "payload_b64": payload_b64,
                                       "requested_risk": label})
        return {
            "action_id": action_id,
            "payload_b64": payload_b64,
            "payload": parse_approval_payload(payload),
            "expires_at": expires_at,
            "sign_with": "printf '%s' '<payload_b64>' | ~/.sentinel/magic_sign_receipt.sh",
        }

    def _proposal(self, action_id: str) -> dict[str, Any] | None:
        for entry in self.audit.entries("proposal"):
            if entry["body"].get("action_id") == action_id:
                return entry["body"]
        return None

    # --- execute_action ----------------------------------------------------------------
    def execute_action(self, *, action_id: str, args: dict[str, Any], signature_b64: str) -> dict[str, Any]:
        try:
            return self._execute(action_id=action_id, args=args, signature_b64=signature_b64)
        except AuditLogError as exc:
            return {"status": "rejected", "action_id": action_id, "reason": f"audit log unavailable: {exc}"}
        except Exception as exc:  # noqa: BLE001 - any failure fails closed
            reason = f"rejected before authorization: {exc.__class__.__name__}: {exc}"
            try:
                self.audit.append("rejected", {"action_id": str(action_id)[:128], "reason": reason})
            except AuditLogError:
                pass
            return {"status": "rejected", "action_id": action_id, "reason": reason}

    def _execute(self, *, action_id: str, args: dict[str, Any], signature_b64: str) -> dict[str, Any]:
        action_id = _text(action_id, "action_id", 128)
        signature_b64 = _text(signature_b64, "signature_b64", 1024)
        proposal = self._proposal(action_id)
        if proposal is None:
            raise ApprovalError(f"no logged proposal {action_id!r}")
        payload = parse_approval_payload(base64.b64decode(proposal["payload_b64"], validate=True))
        request = ActionRequest(
            actor=proposal["actor"], intent=payload["intent"], scope=list(payload["scope"]),
            authority=f"mcp-proposal:{action_id}", risk=payload["risk"], trace_id=payload["trace_id"],
            aud=self.audience, tool=payload["tool"], args_sha256=args_sha256(args),
        )
        approval = HumanApproval(
            approval_id=action_id, human_id=payload["human_id"], trace_id=payload["trace_id"],
            action=payload["intent"], scope=tuple(payload["scope"]), expires_at=payload["expires_at"],
            signature=signature_b64, payload_b64=proposal["payload_b64"],
        )
        verifier = self.sentinel.human_approval_verifier
        if hasattr(verifier, "last_reason"):
            verifier.last_reason = ""
        record = self.sentinel.authorize(request, human_approval=approval)
        detail = getattr(verifier, "last_reason", "") or ""
        self.audit.append("decision", {"action_id": action_id, "trace_id": record.trace_id,
                                       "decision": record.decision.value, "reason": record.reason,
                                       "verifier_detail": detail, "args_sha256": request.args_sha256})
        result = {"action_id": action_id, "decision": record.decision.value, "reason": record.reason,
                  "verifier_detail": detail}
        if record.decision is not Decision.AUTHORIZED:
            return {"status": "rejected", **result}
        if not self.dry_run:
            # Fail closed: no live executor is wired up yet.
            self.audit.append("execution_refused", {"action_id": action_id,
                                                    "reason": "live execution not implemented"})
            return {"status": "refused", **result, "reason": "live execution not implemented; dry-run only"}
        would = {"action_id": action_id, "tool": request.tool, "args_sha256": request.args_sha256,
                 "intent": request.intent, "scope": request.scope, "would_execute": True}
        self.audit.append("dry_run_execution", would)
        return {"status": "dry_run", **result, "would": would}
