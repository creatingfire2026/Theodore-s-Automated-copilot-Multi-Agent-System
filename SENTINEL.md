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
- `aud` — required: the receiving agent's ID. Sentinel blocks a missing or mismatched audience and logs the reason (proposed AIP-001 amendment).
- `test_result` — `{ "run_id", "conclusion" }` CI run reference. The caller-supplied `conclusion` is an untrusted claim and is never used as proof: `VERIFIED` requires an independently configured verifier (for example `GitHubActionsEvidenceVerifier`) to confirm the run against GitHub's records. Missing references, a missing verifier, verifier errors, or any non-success result (including `startup_failure`) end in `FAILED`.
- `risk` — must be one of `low`, `medium`, `high`, `critical` (case-insensitive). Unknown labels are `BLOCKED` rather than treated as low risk.

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

### Protected A7 dissent store (F34)

Sentinel no longer relies on the caller to report a protected A7 dissent. Every
`authorize()` call reads `dissent_store.py` itself:

- Any open A7 dissent whose target equals `*`, the request `trace_id`, its `intent`,
  or one of its `scope` entries yields `HUMAN_REVIEW`. A `HumanApproval` envelope
  does not lift it; only a human-signed receipt row in the store does.
- `protected_dissent_id` is now only a hint. A hinted ID that is not in the store
  yields `HUMAN_REVIEW`.
- Every dissent row is Ed25519-signed by the A7 key (`aip001_council.file_protected_dissent`);
  every receipt is signed by the human key (passphrase-encrypted at rest).
- After each append a signed head anchor (row count + head hash) is written to a
  file outside the database directory. The store must equal or extend it.
- Store missing, unreadable, corrupt, missing triggers, broken hash chain, bad
  A7 or human signature, truncation, rewrite, missing/invalid anchor, or missing
  key configuration all yield `HUMAN_REVIEW`, never `AUTHORIZED`.

**Production setting:** `SENTINEL_REQUIRE_DISSENT_STORE=1` (with
`SENTINEL_DISSENT_DB`, `SENTINEL_DISSENT_ANCHOR`, `SENTINEL_HUMAN_PUBKEY`,
`SENTINEL_A7_PUBKEY`, and for writers `SENTINEL_A7_KEY`). Without it and without a
configured store, Sentinel keeps the legacy caller-hint behavior (kept only so
library/unit use stays opt-in).

Known limits: restoring an older database together with its older anchor file
(a consistent rollback) is not detected; whoever holds a private key can sign
as that role, so keep the human key and passphrase away from agent hosts. The
A7 private key is stored unencrypted (0600) so the agent can sign unattended.
Operate the store with `python dissent_cli.py --help`.
