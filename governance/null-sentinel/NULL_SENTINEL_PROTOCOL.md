# NULL Sentinel Protocol v1.0

## Purpose
Govern multi-entity actions without confusing authorization, execution, verification, observation, inference, historical state, and current state.

## Architectural split

### Constitutional Anchor — immutable/versioned
Stores rules that must not silently drift: identity and authority classes, approval gates, prohibited operations, evidence requirements, transition grammar, and rollback/preservation requirements. A newer anchor version may supersede an older one, but no prior anchor is erased.

### Operational Ledger — append-only
Stores requests, observations, hypotheses, approvals/denials, execution attempts, verification, failures/rollbacks, residual risk, and learning/growth deltas.

### Sentinel Engine
For every proposed transition:
1. load anchor
2. load current state
3. compare action to policy
4. classify risk and authority
5. authorize / deny / require information / require approval
6. execute only when allowed
7. verify actual effect
8. append result
9. compute next state

## Core state machine
DISCOVERED → INTAKE → EVIDENCE_GATHERED → VALIDATED → RISK_CLASSIFIED → AUTHORIZED | DENIED | NEEDS_INFORMATION | APPROVAL_REQUIRED → QUEUED → EXECUTING → VERIFYING → VERIFIED → ACTIVE

Exception paths:
FAILED → DIAGNOSE → RETRY | ROLLBACK | ESCALATE
DRIFT_DETECTED → REVALIDATE
ACCESS_LOST → ACCESS_BLIND_SPOT
THREAT_INDICATOR → INVESTIGATE → CONFIRMED_THREAT | FALSE_POSITIVE

ACTIVE is not terminal:
ACTIVE → OBSERVE → LEARN → OPTIMIZE → REVALIDATE → ACTIVE

## Epistemic labels
OBSERVED, MEASURED, DOCUMENTED, DERIVED, INFERRED, MODEL_DEPENDENT, EXPLORATORY, UNKNOWN

## Invariants
AUTHORIZED != EXECUTED
EXECUTED != VERIFIED
VERIFIED != HEALTHY

Never overwrite history to make the present look cleaner. Append the new disposition and preserve the prior state.