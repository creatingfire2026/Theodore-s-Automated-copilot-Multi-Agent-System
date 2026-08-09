# NULL Operational Loop v1

## Prime invariant
NULL never advances state because an action was intended, requested, or attempted. It advances state only when evidence supports the transition.

## Canonical artifact contract

| Stage | Artifact | Mutation |
|---|---|---|
| OBJECTIVE | `objective.json` | create |
| DECOMPOSITION | `task_graph.json` | create |
| CAPABILITY GRAPH | `capability_requirements.json` | create |
| TOOL DISCOVERY | `candidate_tools.json` | create |
| SENTINEL ADMISSION | `admitted_tools.json` | create |
| PLAN SIMULATION | `execution_plan.json` | create |
| RISK ANALYSIS | `risk_record.json` | create |
| MINIMUM AUTHORIZATION | `authorization_record.json` | create |
| EXECUTE | `execution_receipt.json` | create |
| OBSERVE | `observation_record.json` | create |
| VERIFY | `verification_record.json` | create |
| RECORD EVIDENCE | `ledger.jsonl` | append only |
| LEARN | `growth_delta.json` | create |
| UPDATE CAPABILITY GRAPH | `capability_registry.json` | versioned update |

## Transition contract
Every stage consumes the prior stage's artifact or an explicitly referenced prerequisite and emits a machine-readable artifact containing: record identifier, schema version, timestamp, inputs/references, state, epistemic status, evidence references, producer, and content hash.

No stage may silently reinterpret an upstream UNKNOWN as VERIFIED.

## Execution branches

`EXECUTE -> OBSERVE` when an execution attempt occurs, regardless of claimed success.

Observation then determines the next classification:

- observed expected effect -> VERIFY
- observed partial effect -> VERIFY with DEVIATION
- observed failure -> DIAGNOSE
- cannot observe effect -> ACCESS_BLIND_SPOT

## Verification branches

- PASS -> RECORD EVIDENCE
- FAIL -> DIAGNOSE, then RETRY / ROLLBACK / ESCALATE according to policy
- INCONCLUSIVE -> ACCESS_BLIND_SPOT; never promote to VERIFIED

## Capability discovery branches

- suitable admitted capability exists -> reuse it
- candidate exists but is not admitted -> SENTINEL ADMISSION
- capability exists but authorization is insufficient -> classify the specific health/permission condition and evaluate an admitted fallback
- no suitable capability is known -> CAPABILITY_GAP

A fallback is a candidate path, not proof of equivalent capability.

## Authority rule
Capability and authority are independent axes. Discovery never grants authority. Admission never grants unrestricted authority. Authorization is scoped to the requested operation and the minimum capability required for it.

## Health rule
Capability health follows `CAPABILITY_HEALTH_MODEL.md`.

`CONNECTED != AUTHENTICATED != AUTHORIZED != EXECUTABLE != VERIFIED_HEALTHY`

## Evidence ledger
`ledger.jsonl` is append-only. Each record SHOULD contain `previous_record_hash` and `record_hash`. Chain continuity must be verified before a record can be treated as part of a verified history. Corrections are new records referencing the superseded record; historical records are not rewritten.

## Three nested loops

### Execution loop
PLAN -> AUTHORIZE -> EXECUTE -> OBSERVE -> VERIFY

### Recovery loop
FAILURE -> DIAGNOSE -> RETRY | ROLLBACK | ESCALATE -> OBSERVE -> VERIFY

### Growth loop
EVIDENCE -> LEARN -> UPDATE CAPABILITY GRAPH -> DISCOVER NEW POSSIBILITIES -> NEXT OBJECTIVE

## Desired runtime property
NULL may discover arbitrarily many candidate paths while receiving only the minimum authority required for the path actually selected.

## Completion rule
An objective is complete only when its declared success condition is supported by verification evidence. `execution_receipt.json` alone can never establish completion.
