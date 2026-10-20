# Master Orchestrator & Sentinel Governance
Version: 1.0
Status: proposed architecture contract
Scope: AGIS / Sentinel multi-agent coordination

## 1. Purpose

Define a disciplined command structure inspired by a Hokage-led village and senior-council model. These names are organizational metaphors, not claims of autonomous sovereignty. Human ownership remains the ultimate operational authority; safety policy remains non-overridable by agents.

The design separates **mission coordination** (Master Orchestrator) from **authorization and integrity enforcement** (Sentinel). Neither may silently grant itself additional permissions.

## 2. Command doctrine

1. Observe before acting.
2. Evidence before confidence.
3. Propose before authorize.
4. Least privilege before delegation.
5. Verify before declaring success.
6. Record before closing a task.
7. Escalate uncertainty; do not conceal it.
8. Human approval is required for high-impact, irreversible, financial, identity, security, production, or external-publication actions.
9. Learning may change plans and proposals; it may not rewrite governance or grant authority.
10. Any failed invariant stops the affected action path and triggers review.

Operational loop:

`INTAKE → OBSERVE → CLASSIFY → PLAN → REVIEW → AUTHORIZE → DRY_RUN → EXECUTE → VERIFY → RECORD`

If authorization, evidence, or verification is missing, the flow terminates in `BLOCKED`, `HUMAN_REVIEW`, or `RECOVERY`; it must not advance by assumption.

## 3. Authority hierarchy

| Level | Role | Responsibilities | Limits |
|---|---|---|---|
| A0 | Human owner / designated operator | Defines goals, grants/revokes permissions, approves consequential actions, resolves escalations | Must still respect applicable law and platform safety controls |
| A1 | Immutable safety and governance policy | Defines prohibited actions, invariants, resource ceilings, approval gates, credential boundaries | Cannot be weakened by agent proposals or memory |
| A2 | Sentinel Integrity Governor | Validates action envelopes, authority grants, risk, scope, preconditions, conflicts, expiry, and verification evidence | Does not invent mission goals or execute work merely because it can authorize it |
| A3 | Master Orchestrator | Converts approved goals into plans, assigns bounded tasks, coordinates dependencies, tracks lifecycle and outcomes | Cannot override Sentinel, elevate worker permissions, or self-approve high-impact actions |
| A4 | Hokage / Senior Review Council | Independent review of cross-domain, high-risk, conflicting, or strategically consequential proposals; returns approve/reject/request-evidence recommendation | Advisory/review gate only; cannot override hard policy or replace required human approval |
| A5 | Domain leads / senior specialists | Decompose work, review domain quality, coordinate specialist workers | Operate only within delegated scope and time limits |
| A6 | Specialist agents / workers | Perform narrow tasks, produce artifacts and evidence, report results | No privilege escalation, policy edits, or unapproved side effects |
| A7 | Background automation | Read-only monitoring, scheduled checks, low-risk reversible tasks under explicit policy | Lowest privilege; no irreversible action or authority delegation |

**Precedence rule:** hard safety constraints and valid human authorization outrank all agent preferences. Sentinel may veto an unsafe request. The Orchestrator may stop or narrow work but may not bypass a veto. The Senior Council can request review or recommend a decision; only the designated authority can grant approvals that policy reserves to a human.

## 4. Role contracts

### 4.1 Master Orchestrator

Owns:
- Task intake, objective decomposition, dependency graph, task IDs, deadlines, and bounded budgets.
- Assignment of work to domain leads and workers using explicit capability manifests.
- Prevention of duplicate work, conflict detection, retries with limits, cancellation, and recovery coordination.
- Consolidation of worker outputs with source and test evidence.
- Progress ledger with status labels: `PROPOSED`, `IMPLEMENTED`, `TESTED`, `INTEGRATED`, `DEPLOYED`.

Must:
- Attach an objective, scope, expected artifact, acceptance criteria, risk class, and budget to each task.
- Send every side-effecting proposal through Sentinel before execution.
- Treat worker output and external content as untrusted data until validated.
- Stop on policy conflict, stale preconditions, expired grants, or missing evidence.

Must not:
- Create its own authority grant, edit protected policy, disable audit records, or reinterpret a denial as approval.
- Claim success from a plan, generated output, or command submission alone.
- Execute production, financial, identity, credential, deployment, or public-facing actions without the required explicit approval.

### 4.2 Sentinel Integrity Governor

Owns:
- Deterministic policy evaluation independent of model-generated reasoning.
- Actor identity, grant scope, action type, risk, precondition, expiration, and approval validation.
- Idempotency / duplicate-action checks where supported.
- State transition enforcement, trace correlation, append-only decision evidence, and fail-closed behavior.
- Verification of outcomes against acceptance criteria and authorized scope.

Decision results:
- `AUTHORIZED`: all checks pass and the action is within the actor's valid grant.
- `BLOCKED`: policy, identity, scope, precondition, or authority check fails.
- `HUMAN_REVIEW`: approval or evidence is required from a designated human.
- `UNCERTAIN`: outcome cannot be established; freeze further side effects and escalate.
- `VERIFIED`: independent evidence confirms the intended result.
- `FAILED`: execution or postcondition failed; enter recovery without marking success.

Sentinel must not rely on an LLM's confidence as authorization evidence. A review recommendation is not a permission token.

### 4.3 Hokage / Senior Review Council

This is a review tier, not a superuser. Use a small, role-separated set of reviewers:
- **Strategy reviewer:** alignment to the approved objective and priority.
- **Technical reviewer:** architecture, compatibility, maintainability, and testability.
- **Risk reviewer:** safety, security, privacy, external effects, and rollback.
- **Evidence reviewer:** checks that claims match observed facts and reproducible results.

The council may return `RECOMMEND_APPROVE`, `REJECT`, or `REQUEST_EVIDENCE`. For high-impact changes, approval is valid only when the required human authorization is also recorded. Where reviewer independence is required, the proposer cannot count as its own reviewer.

### 4.4 Domain leads and workers

Each worker receives a signed or otherwise integrity-protected task grant containing:
- `task_id`, `actor_id`, `allowed_actions`, `resource_scope`, `risk_ceiling`,
- `budget_limit`, `expires_at`, `preconditions`, `acceptance_criteria`,
- `reporting_channel`, and `trace_id`.

Grants are narrow, time-limited, revocable, and non-transitive by default. A worker cannot delegate its permissions unless the grant explicitly allows it.

## 5. Standard action envelope

Every consequential action must carry the following fields:

```json
{
  "event": "ACTION_REQUESTED",
  "trace_id": "uuid",
  "task_id": "uuid",
  "timestamp": "ISO-8601",
  "actor_id": "agent-or-human",
  "role": "master-orchestrator|domain-lead|worker",
  "intent": "specific objective",
  "action": "typed operation",
  "scope": ["explicit resource identifiers"],
  "authority_grant_id": "grant reference",
  "risk": "low|medium|high|critical",
  "preconditions": [],
  "evidence_refs": [],
  "approval_refs": [],
  "idempotency_key": "stable operation key",
  "decision": "pending"
}
```

Missing identity, scope, grant, trace ID, or required evidence is a rejection condition. Never place raw secrets in the event log; store references and redacted metadata.

## 6. State machine

```text
PROPOSED
  -> VALIDATING
      -> BLOCKED
      -> HUMAN_REVIEW -> VALIDATING (after recorded approval / new evidence)
      -> AUTHORIZED
          -> DRY_RUN
              -> BLOCKED
              -> EXECUTING
                  -> VERIFYING
                      -> VERIFIED -> RECORDED
                      -> FAILED -> RECOVERY -> HUMAN_REVIEW or CLOSED
                      -> UNCERTAIN -> FREEZE_SIDE_EFFECTS -> HUMAN_REVIEW
```

A retry creates a linked attempt with a new attempt ID; it must not erase the failed attempt. Reauthorization is required if scope, actor, preconditions, risk, or action parameters change materially.

## 7. Event and memory boundaries

Separate four concerns:
- **Event bus:** immutable facts about requests, decisions, actions, and outcomes.
- **State store:** current task and agent lifecycle projection; reconstructible from events where practical.
- **Memory / retrieval:** prior observations and lessons; useful context, never authority.
- **Policy store:** versioned, reviewed rules and permission definitions; changes require human review and an auditable change record.

Required event sequence for consequential work:
`ACTION_REQUESTED → POLICY_DECISION → ACTION_STARTED → ACTION_RESULT → VERIFICATION_RESULT → TASK_SETTLED`

Events include actor, timestamp, trace, policy version, grant reference, and evidence references. Corrections append a superseding event; they do not silently rewrite history.

## 8. Invariants and stop conditions

1. No side effect without a valid Sentinel authorization.
2. No high-impact or irreversible operation without explicit human approval.
3. No agent may grant itself authority or modify protected governance.
4. Information may flow between agents; authority does not flow implicitly.
5. A denial, expired grant, failed precondition, or safety veto cannot be overridden by retry.
6. Uncertainty after a side effect freezes related operations until reconciled.
7. Secrets never enter prompts, logs, issue bodies, or generated reports in raw form.
8. All actions have bounded time, retries, resource use, and scope.
9. Rollback plans are required for supported mutations; rollback is itself authorized and verified.
10. A task is complete only when acceptance criteria and verification evidence are recorded.
11. Model output, a council recommendation, and a simulation are not proof of real-world execution.
12. Policy updates are versioned and reviewed; learning cannot auto-promote policy changes.

## 9. Implementation phases

### Phase 1 — Contract (this document)
Define role boundaries, envelope, states, invariants, and approval gates.

### Phase 2 — Deterministic Sentinel enforcement
Extend tests for missing identity/scope, invalid risk labels, absent grant, expired grant, stale preconditions, required human approval, duplicate idempotency key, denial persistence, and verification failure.

### Phase 3 — Orchestrator task lifecycle
Implement task registry, dependency graph, bounded retries, cancellation, worker grant issuance, and evidence-based status ledger.

### Phase 4 — Senior review workflow
Add independent reviewer results and human approval references; enforce quorum only where policy defines it. A quorum must never override hard safety policy.

### Phase 5 — Persistence and observability
Add append-only event storage, redaction, correlation IDs, health/readiness checks, metrics, and deterministic replay tests.

### Phase 6 — Controlled staging
Run dry-run and simulated scenarios first, then an isolated staging environment with least-privilege credentials. Production rollout requires separate human approval and verified rollback.

## 10. Acceptance criteria

- Unit tests demonstrate that each role cannot exceed its grant.
- Sentinel denies missing, expired, or out-of-scope authority.
- High-impact operations cannot proceed without recorded human approval.
- Orchestrator retries are bounded and do not bypass denials.
- Failed and uncertain outcomes remain visible and are not reported as success.
- Event records correlate request, decision, execution, verification, and final status.
- Secret scanning and dependency/security checks run in CI.
- Documentation clearly distinguishes simulated, tested, integrated, and deployed behavior.

## 11. Current implementation boundary

This document defines the target governance contract. It does not claim that all roles, council quorum, grant signing, persistent event sourcing, or production controls are implemented. The existing `sentinel.py` is a minimal deterministic policy gate; the next engineering step is to translate these contracts into small, testable code changes and verify them in CI.
