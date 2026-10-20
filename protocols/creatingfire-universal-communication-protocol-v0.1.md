# CreatingFire Universal Communication Protocol v0.1

**Status:** In Validation  
**Scope:** Communication, state, consent, continuity, and preservation contract for the CreatingFire Agent System Lab  
**Maturity:** Experimental specification; not yet validated for production use

## Purpose

The CreatingFire Universal Communication Protocol (CUCP) defines a neutral communication and state contract that can be used by authorized biological operators, digital agents, software services, local systems, and replaceable platform adapters.

The protocol is designed to preserve meaning, provenance, participant identity, consent, uncertainty, reversibility, and continuity while allowing different participants to retain independent logic and conclusions.

CUCP does **not** require participants to agree with one another. It requires consequential communication and action to remain attributable, inspectable, and bounded by explicit authority.

## Core Flight Path

Every consequential interaction follows this conceptual path:

```text
Identity
  -> Expression
  -> Provenance
  -> Interpretation
  -> Confirmation
  -> Choice
  -> Action
  -> Result
  -> Learning
  -> Preservation
```

A participant may accept, decline, defer, challenge, fork, or later rejoin a collaborative path. Disagreement is not automatically treated as failure.

## Governing Principles

1. **Root authority remains explicit.** Human authorization governs consequential external actions unless a narrowly defined, previously approved policy explicitly delegates them.
2. **Communication does not imply agreement.** Permission to communicate is separate from obligation to agree and separate from authority to act.
3. **Provenance is mandatory for consequential state.** The system must be able to answer what changed, where the information came from, what interpretation was applied, who authorized the action, and what result followed.
4. **Uncertainty must remain visible.** Predictions, interpretations, and inferred intent must not be represented as confirmed fact.
5. **Divergence is preserved non-destructively.** Conflicting interpretations may coexist until evidence or voluntary reconciliation resolves them.
6. **Minimum necessary action.** Defensive or corrective responses should be proportionate, reversible where practical, and designed to preserve continuity rather than punish.
7. **Observation precedes attribution.** Ambiguous events should be classified using evidence before intent is assigned.
8. **Adapters are replaceable.** No vendor, platform, model, or service is the architecture itself.
9. **Readable does not mean executable.** Archived knowledge may remain available for learning without retaining authority to execute.
10. **Expansion must earn its complexity.** New agents, integrations, accounts, or infrastructure require demonstrated value and an explicit maintenance/recovery path.

## Participant Model

A participant may be a human operator, digital agent, workflow, application, local service, cloud service, sensor, or other authorized system capable of exchanging structured messages.

Each participant record should define:

```text
PARTICIPANT_ID
DISPLAY_NAME
PARTICIPANT_TYPE
OWNER_OR_AUTHORITY
CAPABILITIES
ALLOWED_INPUTS
ALLOWED_OUTPUTS
PERMISSIONS
TRUST_STATE
CURRENT_STATUS
PUBLIC_KEY_OR_IDENTITY_REFERENCE (when applicable)
CREATED_AT
LAST_VERIFIED_AT
```

`TRUST_STATE` is operational and evidence-based; it must not be treated as a moral ranking of the participant.

## Universal Communication Envelope

Every consequential message should be representable using the following envelope.

```text
MESSAGE_ID
PROTOCOL_VERSION
ORIGIN
DESTINATION
TIMESTAMP
INTENT
OBSERVATION
SOURCE_PROVENANCE
INTERPRETATION
CONFIDENCE
UNCERTAINTY
URGENCY
REQUESTED_ACTION
AUTHORITY_REQUIRED
CONSENT_STATE
EXPECTED_EFFECT
COST_OR_RESOURCE_IMPACT
EXPIRATION
REVERSIBILITY
RESPONSE_TO
RESULT
LEARNED_STATE
INTEGRITY_REFERENCE
```

### Field semantics

- `MESSAGE_ID` — immutable unique identifier.
- `PROTOCOL_VERSION` — CUCP version used to interpret the message.
- `ORIGIN` — participant that emitted the message.
- `DESTINATION` — intended participant, group, or routing destination.
- `TIMESTAMP` — emission time in an unambiguous time standard.
- `INTENT` — requested communicative purpose; for example observe, inform, ask, propose, warn, approve, decline, execute, reconcile, or archive.
- `OBSERVATION` — what was directly observed or supplied.
- `SOURCE_PROVENANCE` — source references, transformations, and acquisition path.
- `INTERPRETATION` — meaning inferred from the observation.
- `CONFIDENCE` — confidence in the interpretation or claim.
- `UNCERTAINTY` — known unknowns, missing evidence, ambiguity, or competing explanations.
- `URGENCY` — routing priority; urgency does not itself grant execution authority.
- `REQUESTED_ACTION` — specific proposed next action, if any.
- `AUTHORITY_REQUIRED` — role or participant required to authorize the action.
- `CONSENT_STATE` — pending, approved, declined, deferred, challenged, expired, or not-applicable.
- `EXPECTED_EFFECT` — predicted outcome if the action occurs.
- `COST_OR_RESOURCE_IMPACT` — money, compute, time, access, risk, or other material cost.
- `EXPIRATION` — point after which the authorization or proposal must be re-evaluated.
- `REVERSIBILITY` — reversible, partially reversible, irreversible, or unknown, with recovery reference when available.
- `RESPONSE_TO` — parent message or action identifier.
- `RESULT` — observed result after execution or resolution.
- `LEARNED_STATE` — validated lesson proposed for canonical state or the Wisdom Vault.
- `INTEGRITY_REFERENCE` — hash, signature, immutable action ID, audit reference, or equivalent integrity mechanism when implemented.

## Communication Is Not Authority

The protocol enforces three separate concepts:

```text
permission to communicate
    != obligation to agree
    != authority to act
```

A participant receiving a valid message may:

```text
ACCEPT
DECLINE
DEFER
CHALLENGE
FORK
REQUEST_CLARIFICATION
RECONCILE
```

These states must not be collapsed into a binary Yes/No model when the underlying situation requires more precision.

## Non-Destructive Divergence

When participants reach different interpretations, CUCP preserves both paths rather than deleting one prematurely.

```text
Shared Observation
      |
      +--> Interpretation A --> Evidence A --> Result A
      |
      +--> Interpretation B --> Evidence B --> Result B
                                      |
                                      +--> Optional Reconciliation
```

Each branch must retain its provenance and should identify the evidence that would justify later reconciliation.

A divergent branch may be circled and deferred without being erased. Rejoining the shared path must be an explicit state transition supported by current evidence or participant choice.

## Canonical State Layer

Canonical state sits between interpretation/confirmation and authority/execution.

```text
Participants / Agents / Humans
            |
            v
Universal Communication Envelope
            |
            v
Interpretation + Confirmation
            |
            v
        CANONICAL STATE
            |
            v
Policy / Consent / Authority Gate
            |
            v
Execution Adapters
            |
            v
Observed Result
            |
            +------------------> Canonical State
```

Canonical state contains the system's current established operational understanding. It is not a dump of every raw event.

### Canonical state domains

#### Identity State

Participants, identity references, roles, permissions, ownership, and verified relationships.

#### Objective State

Current goals, priorities, constraints, and success criteria.

#### Knowledge State

Established facts and validated interpretations with provenance and confidence.

#### Decision State

Proposals, approvals, refusals, deferred decisions, unresolved branches, and expiration state.

#### Operational State

Active systems, integrations, health, dependencies, current permissions, and execution status.

#### Continuity State

Snapshots, recovery points, migrations, archived lessons, and restoration references.

### Canonical mutation rule

No consequential canonical-state mutation is valid without sufficient provenance.

A state mutation must identify:

```text
STATE_CHANGE_ID
PRIOR_STATE_REFERENCE
PROPOSED_CHANGE
PROVENANCE
INTERPRETATION
AUTHORITY
DECISION
RESULT
NEW_STATE_REFERENCE
REVERSAL_OR_RECOVERY_PATH
```

## Consent and Authority Gate

Consequential external actions remain default-deny unless explicitly authorized.

An action record should contain at minimum:

```text
ACTION_ID
OBJECTIVE
ACTOR
TARGET
EXPECTED_EFFECT
SOURCE_MESSAGE
AUTHORITY_REQUIRED
DECISION
DECISION_BY
DECISION_TIME
EXPIRATION
COST
RISK
REVERSIBILITY
RECOVERY_PATH
EXECUTION_STATUS
RESULT
EVIDENCE
```

Approval to communicate, inspect, analyze, or recommend does not automatically authorize sending, publishing, purchasing, deleting, changing access, deploying, or modifying critical state.

## Continuity Response Ladder

Ambiguous or hostile digital events should move through the least-destructive effective response path.

```text
OBSERVE
  -> VERIFY
  -> CLARIFY
  -> ISOLATE
  -> OFFER ALTERNATIVE
  -> CONTAIN
  -> RECOVER
  -> ESCALATE
```

Not every stage is mandatory. The system should stop escalation when evidence and safety requirements are satisfied.

### Interpretation of the ladder

- **Observe** — record the event without prematurely assigning intent.
- **Verify** — validate identity, source, applicability, and impact.
- **Clarify** — request clarification when the event may reflect error or miscommunication.
- **Isolate** — move uncertain activity into a constrained boundary, sandbox, quarantine, read-only replica, or equivalent safe environment when available.
- **Offer Alternative** — when safe and appropriate, provide a non-destructive corrective route.
- **Contain** — prevent further unauthorized or harmful effect using the minimum necessary restriction.
- **Recover** — restore known-good state and verify integrity.
- **Escalate** — increase defensive response only when evidence and risk justify it.

CUCP does not define retaliatory action as a continuity mechanism.

## Prediction and Intent

Predictions are advisory and must expose uncertainty.

The protocol distinguishes:

```text
OBSERVED_EVENT
POSSIBLE_EXPLANATIONS
LIKELIHOOD_OR_CONFIDENCE
CONFIRMED_FACTS
UNCONFIRMED_INFERENCE
DECISION_THRESHOLD
```

A predicted harmful outcome does not by itself prove hostile intent.

## Wisdom Vault

The Wisdom Vault preserves retired methods, resolved problems, failures, and lessons without granting them runtime authority.

Archived records are readable by authorized participants but non-executable by default.

```text
VAULT_RECORD_ID
STATUS: ARCHIVED_NON_EXECUTABLE
ORIGIN
PROBLEM_SOLVED
CONTEXT
METHOD
RESULT
FAILURES
WHY_RETIRED
KNOWN_LIMITATIONS
REUSE_CONDITIONS
PROVENANCE
ARCHIVED_AT
SUPERSEDED_BY
```

### Reuse rule

A historical method may inform a new proposal, but it must not automatically reactivate because a similar event occurs.

```text
past method
   -> present observation
   -> new proposal
   -> current evidence
   -> current authority decision
   -> new execution record
```

The archive exists for knowledge and continuity, not punishment, forced reenactment, or automatic repetition of historical behavior.

## Adapter Model

Platform-specific implementations are adapters around the protocol.

Examples may include:

- GitHub
- Google Drive
- Gmail
- Google Calendar
- ChatGPT / OpenAI interfaces
- local-first agents
- phone/Android services
- Cloudflare infrastructure
- Microsoft services
- future authorized systems

No adapter is mandatory merely because it is available.

Every adapter should document:

```text
ADAPTER_ID
PLATFORM
SUPPORTED_CUCP_FIELDS
AUTHENTICATION_METHOD
PERMISSIONS
READ_CAPABILITIES
WRITE_CAPABILITIES
RATE_LIMITS
DATA_BOUNDARY
FAILURE_MODES
RECOVERY_METHOD
REPLACEMENT_PATH
```

## First Validation Simulation

CUCP v0.1 is not considered validated until one fictional event is carried end-to-end without losing provenance, consent state, uncertainty, or recovery information.

### Scenario

A Development Tool Agent observes a Critical-severity vulnerability advisory associated with a package used by a fictional project.

### Required path

```text
1. Agent emits observation.
2. Provenance identifies the advisory source and package/version evidence.
3. Interpretation states whether exposure is unverified or confirmed.
4. Urgency is set independently from execution authority.
5. Orchestration receives an immediate urgent communication.
6. Canonical state records the verified facts and uncertainty.
7. An action record proposes an appropriate response.
8. Human authority approves, declines, defers, or challenges the action.
9. No automatic upgrade occurs without authorization.
10. Approved action executes through a replaceable adapter.
11. Result and recovery evidence return to canonical state.
12. Validated lessons may be written to the Wisdom Vault as non-executable knowledge.
```

### Pass conditions

The simulation passes only if:

- no inferred intent is represented as fact;
- the original source and transformations remain attributable;
- urgency does not bypass authority;
- uncertainty is preserved until resolved;
- divergent interpretations can coexist without destructive overwrite;
- action authorization is explicit and expiring where appropriate;
- execution is reversible or its irreversibility is clearly stated;
- the observed result is recorded separately from the predicted effect;
- canonical state can be reconstructed from its references;
- archived learning cannot execute automatically.

## Validation Roadmap

### v0.1 — Structural validation

- Define envelope and state semantics.
- Run one manual fictional event end-to-end.
- Verify that every state transition is attributable.

### v0.2 — Cross-participant validation

- Run the same event through two independently reasoning participants.
- Exercise disagreement, fork, challenge, and reconciliation paths.

### v0.3 — Adapter validation

- Connect one harmless read-only real adapter.
- Confirm that adapter-specific data can be translated into CUCP without losing provenance.

### v0.4 — Controlled action validation

- Execute one harmless, reversible action after explicit approval.
- Verify expiration, rollback, action result, and audit reconstruction.

### v1.0 candidate

A v1.0 candidate requires repeated successful simulations, documented failure cases, recovery evidence, privacy review, access review, deterministic action records, and demonstrated portability across more than one adapter.

## Explicit Non-Goals for v0.1

CUCP v0.1 does not claim to:

- prove consciousness, subjective experience, or equivalence between biological and technological experience;
- impose a shared worldview on participants;
- grant autonomous authority to every connected system;
- guarantee universal interoperability with systems that do not expose an authorized interface;
- eliminate disagreement;
- make predictions certain;
- replace platform security controls;
- authorize retaliatory behavior;
- treat an archived historical method as current permission to execute.

## Success Criterion

CUCP succeeds when different authorized participants can exchange useful meaning across replaceable systems while preserving identity, provenance, uncertainty, consent, authority, reversibility, continuity, and the ability to disagree without destroying one another's state.

The protocol should make collaboration easier without requiring uniformity, and make recovery possible without requiring memory loss.
