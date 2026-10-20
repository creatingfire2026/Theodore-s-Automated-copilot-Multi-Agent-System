# SENTINEL — System Integrity & Orchestration Contract

> Deterministic policy gate for a modular, human-governed multi-agent system.

## Mission

Sentinel is the integrity governor. It validates proposed actions, enforces authority boundaries, checks preconditions, records decisions, and stops unsafe or contradictory execution. The Master Orchestrator coordinates work but does not own policy authority.

The full role hierarchy, Hokage / Senior Review Council protocol, event envelope, state machine, and staged implementation plan are defined in [ORCHESTRATOR_GOVERNANCE.md](ORCHESTRATOR_GOVERNANCE.md).

## Control Loop

`INTAKE → OBSERVE → CLASSIFY → PLAN → REVIEW → AUTHORIZE → DRY_RUN → EXECUTE → VERIFY → RECORD`

Missing authority, failed preconditions, or unverified outcomes stop the affected path. Uncertainty after a side effect freezes related actions and escalates to human review.

## Authority Hierarchy

1. **Human owner / designated operator** — defines objectives, grants permissions, and approves consequential actions.
2. **Safety and governance policy** — hard constraints that agents cannot override.
3. **Sentinel Integrity Governor** — deterministic policy evaluation, veto, traceability, and verification gates.
4. **Master Orchestrator** — decomposes approved objectives, assigns bounded tasks, manages dependencies, and reports outcomes.
5. **Hokage / Senior Review Council** — independent strategy, technical, risk, and evidence review; recommendations do not replace required human approval.
6. **Domain leads and specialist workers** — execute only within explicit, scoped, time-limited grants.
7. **Background automation** — lowest privilege, limited to explicitly permitted monitoring and reversible actions.

An agent may propose an action outside its authority, but it may not silently self-authorize it. Information may flow between agents; authority does not flow implicitly.

## Core Invariants

- No side effect without valid Sentinel authorization.
- No high-impact or irreversible action without explicit human approval.
- No execution without attributable actor, trace ID, bounded scope, and valid grant.
- Read-only observation must not mutate system state.
- Failed verification is never reported as success.
- Memory and model confidence may inform decisions but cannot grant authority.
- Council recommendations cannot override policy or replace human approvals required by policy.
- Denials, expired grants, and failed preconditions cannot be bypassed through retries.
- Every consequential state transition is auditable; corrections append new records instead of erasing history.
- Governance changes require versioned review and cannot be auto-promoted by a learning loop.

## Event Envelope

Every consequential action should include:
- `event`, `trace_id`, `task_id`, `timestamp`
- `actor_id`, `role`, `intent`, `action`
- `scope`, `authority_grant_id`, `risk`
- `preconditions`, `evidence_refs`, `approval_refs`
- `idempotency_key`, `decision`

Never place raw credentials in prompts or logs; use redacted metadata and secret references.

## Decision States

`PROPOSED → VALIDATING → AUTHORIZED → DRY_RUN → EXECUTING → VERIFYING → VERIFIED → RECORDED`

Failure paths:
- `VALIDATING → BLOCKED`
- `VALIDATING → HUMAN_REVIEW`
- `EXECUTING → FAILED → RECOVERY`
- `EXECUTING → UNCERTAIN → FREEZE_SIDE_EFFECTS → HUMAN_REVIEW`

## Sentinel Responsibilities

- Detect policy violations, conflicting intents, duplicate actions, and expired grants.
- Validate action scope, risk, approval references, and preconditions before execution.
- Keep policy evaluation deterministic and separate from model inference.
- Preserve traceable decision and verification evidence.
- Enforce bounded retries, resource ceilings, and least privilege.
- Surface anomalies instead of masking them.
- Keep agents modular and replaceable without weakening governance.

## Minimal Agent Interface

`observe(context) → evidence`

`propose(goal, evidence) → action`

`execute(authorized_action) → result`

`verify(result) → verdict`

The Orchestrator plans and coordinates. Sentinel owns the authorization gate. The designated human retains approval authority for consequential actions.

## Implementation Status

This contract describes intended governance. It does not claim that council quorum, signed grants, persistent event sourcing, or production deployment controls are fully implemented. The current `sentinel.py` remains a minimal policy engine; implementation must proceed in small, testable changes with CI evidence.
