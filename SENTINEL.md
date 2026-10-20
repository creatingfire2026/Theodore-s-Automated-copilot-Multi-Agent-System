# SENTINEL — System Integrity & Orchestration Contract

> Deterministic policy gate for a modular, human-governed multi-agent system.

## Mission

Sentinel validates proposed actions and enforces authority boundaries before an executor performs side effects. The Master Orchestrator coordinates work but does not own policy authority.

The full role hierarchy and target governance contract are defined in [ORCHESTRATOR_GOVERNANCE.md](ORCHESTRATOR_GOVERNANCE.md).

## Control loop

`INTAKE → OBSERVE → CLASSIFY → PLAN → REVIEW → AUTHORIZE → DRY_RUN → EXECUTE → VERIFY → RECORD`

Missing authority, failed preconditions, or unverified outcomes stop the affected path. Uncertainty after a side effect freezes related actions and escalates to human review.

## Authority hierarchy

1. **Human owner / designated operator** — defines objectives, grants permissions, and approves consequential actions.
2. **Safety and governance policy** — hard constraints that agents cannot override.
3. **Sentinel Integrity Governor** — deterministic policy evaluation and veto.
4. **Master Orchestrator** — decomposes approved objectives and coordinates bounded tasks.
5. **Hokage / Senior Review Council** — independent review; recommendations do not replace required human approval.
6. **Domain leads and specialist workers** — act only within explicit, scoped grants.
7. **Background automation** — lowest privilege, restricted to explicitly permitted operations.

Information may flow between agents; authority does not flow implicitly.

## Sentinel v1 enforcement

The current v1 implementation validates:
- Non-empty actor, intent, trace ID, action type, scope, and idempotency key.
- Risk labels against `low`, `medium`, `high`, and `critical`.
- Explicit grant presence, actor match, action allow-list, scope containment, risk ceiling, and timezone-aware expiry.
- Preconditions through an explicit validity signal; stale/failed preconditions are blocked.
- High/critical risk requires both explicit human approval and an approval reference.
- Reuse of an idempotency key is blocked within the current process, including attempts to retry a previously denied request.
- Verification failure remains `FAILED`; non-authorized decisions cannot be converted to success by calling `verify`.

### Deliberate v1 boundaries

- The decision/idempotency ledger is **in-memory only**. It does not persist across restarts or coordinate multiple processes.
- `AuthorityGrant` is a data contract, not a cryptographically signed grant or identity-provider integration.
- Human approval is represented by caller-supplied arguments and an approval reference; an authenticated approval service is not yet connected.
- Preconditions are represented by a boolean result supplied by the caller; Sentinel does not independently fetch live system state.
- Sentinel does not execute actions. A separate executor must call it and honor every non-`AUTHORIZED` decision as a hard stop.

These boundaries are explicit; v1 is not production-grade distributed enforcement.

## CI and validation

GitHub Actions compiles the policy module and tests, then runs the pytest regression suite. A green workflow is evidence for this commit only; it does not establish deployment or external integrations.

## Core invariants

- No side effect without valid Sentinel authorization.
- No high-impact or irreversible action without required human approval.
- No agent may grant itself authority or modify protected governance.
- Failed verification is never reported as success.
- Memory and model confidence cannot grant authority.
- Denials, expired grants, and failed preconditions cannot be bypassed by reusing an idempotency key.
- Consequential outcomes require evidence; policy and audit persistence remain future work.

## Status

**Sentinel Enforcement v1 — implementation proposed on branch `feat/sentinel-enforcement-v1`; CI results must be checked before calling it validated or merged.**
