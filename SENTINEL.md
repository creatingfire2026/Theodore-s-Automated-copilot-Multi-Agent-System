# SENTINEL — System Integrity & Orchestration Contract

> A lightweight control-plane contract for a modular multi-agent system.

## Mission
Sentinel is the supervisory layer: observe system state, validate proposed actions, enforce authority boundaries, record decisions, and stop unsafe or contradictory execution.

## Control Loop

`OBSERVE → CLASSIFY → PLAN → AUTHORIZE → EXECUTE → VERIFY → RECORD`

Every consequential action should carry:

- `actor`: agent or subsystem requesting the action
- `intent`: human-readable objective
- `scope`: resources the action may affect
- `authority`: permission basis
- `risk`: low / medium / high / critical
- `preconditions`: facts that must remain true
- `evidence`: inputs supporting the decision
- `result`: observed execution outcome
- `trace_id`: correlation identifier for the complete event chain

## Authority Hierarchy

1. **Human directive** — highest authority.
2. **Policy / safety constraints** — hard constraints; agents cannot override them.
3. **Sentinel** — validates scope, conflicts, preconditions, and execution state.
4. **Specialist agents** — propose and execute within granted scope.
5. **Background automation** — lowest operational authority.

An agent may propose an action outside its authority, but it may not silently self-authorize it.

## Core Invariants

- No execution without an attributable actor and trace ID.
- No irreversible action without explicit authorization.
- Read-only observation must not mutate system state.
- Failed verification returns control to Sentinel instead of being treated as success.
- Memory may inform a decision but cannot by itself grant authority.
- Conflicting agents do not resolve authority disputes themselves; Sentinel arbitrates or escalates.
- Every state transition is auditable.

## Event Envelope

```json
{
  "event": "ACTION_REQUESTED",
  "trace_id": "uuid",
  "timestamp": "ISO-8601",
  "actor": "agent-id",
  "intent": "objective",
  "scope": ["resource"],
  "authority": "policy-or-grant",
  "risk": "medium",
  "preconditions": [],
  "evidence": [],
  "decision": "pending"
}
```

## Decision States

`PROPOSED → VALIDATING → AUTHORIZED → EXECUTING → VERIFIED`

Failure paths:

`VALIDATING → BLOCKED`

`EXECUTING → FAILED → RECOVERY`

`EXECUTING → UNCERTAIN → HUMAN_REVIEW`

## Sentinel Responsibilities

- Detect policy violations before execution.
- Detect conflicting intents and duplicate actions.
- Track delegation and authority expiry.
- Require confirmation for high-impact operations.
- Preserve an immutable decision trail.
- Surface anomalies instead of masking them.
- Permit ordinary agents to remain modular and replaceable.

## Minimal Agent Interface

An agent should expose four conceptual operations:

`observe(context) → evidence`

`propose(goal, evidence) → action`

`execute(authorized_action) → result`

`verify(result) → verdict`

Sentinel owns the transition between proposal and authorization.

## First Implementation Target

Build Sentinel as a small, deterministic policy engine around an append-only event log. Keep model inference outside the authority mechanism: language models can recommend actions, but policy evaluation remains explicit, inspectable, and testable.
