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

**Production settings:** enable both `SENTINEL_REQUIRE_DISSENT_STORE=1` and
`SENTINEL_REQUIRE_DISSENT_WITNESS=1`, with `SENTINEL_DISSENT_DB`,
`SENTINEL_DISSENT_ANCHOR`, `SENTINEL_HUMAN_PUBKEY`, `SENTINEL_A7_PUBKEY`,
`SENTINEL_DISSENT_WITNESS_URL`, `SENTINEL_DISSENT_WITNESS_PUBKEY`, and the
Sentinel-only `SENTINEL_DISSENT_WITNESS_TOKEN`. Writers also need
`SENTINEL_A7_KEY`. Setting witness-required automatically makes the dissent store
required; there is no legacy fallback when the store or witness is missing.

Known limits: restoring an older database together with its older anchor file
(a consistent rollback) is not detected; whoever holds a private key can sign
as that role, so keep the human key and passphrase away from agent hosts. The
A7 private key is stored unencrypted (0600) so the agent can sign unattended.
Operate the store with `python dissent_cli.py --help`. For an offline human key
(e.g. `openssl` on Termux/Android), emit the canonical payload with
`python dissent_cli.py receipt-payload <dissent_id>`, sign with
`magic_sign_receipt.sh` (`openssl pkeyutl -sign -rawin`), and record the
receipt with `python dissent_cli.py clear --payload-b64 ... --sig-b64 ...`
(the box's A7 key re-signs the head anchor, while only the human key can sign
the receipt itself).


### Independent monotonic dissent witness

The local signed anchor detects truncation and rewriting, but cannot detect restoration
of an older database together with its matching older anchor. The optional independent
witness closes that local rollback gap within the stated threat model:

- `cloudflare/dissent-witness/worker.mjs` stores the highest accepted sequence and
  hash in a Cloudflare Durable Object. It accepts only the next sequence whose
  previous hash matches the stored head.
- The Worker verifies each A7-signed dissent or human-signed receipt before advancing.
  Duplicate dissent IDs, duplicate receipts, stale sequence numbers, and forked
  previous hashes are rejected.
- The Worker signs every checkpoint with a dedicated Ed25519 key held only as a
  Cloudflare Worker secret. A7's signing key cannot forge or roll back that witness
  checkpoint.
- `dissent_witness.py` verifies the checkpoint signature. When configured, every
  local dissent-store read compares the complete local head with the remote
  checkpoint. Missing, unavailable, invalid, behind, ahead, or divergent witness
  state produces `HUMAN_REVIEW`.
- `python dissent_cli.py witness-sync` is an explicit recovery operation for an
  interrupted append: it only replays a locally verified suffix when the remote
  checkpoint is an exact ancestor. It refuses remote-ahead or divergent state.

**Sentinel configuration:**

```sh
SENTINEL_DISSENT_WITNESS_URL=https://<worker>.<account>.workers.dev
SENTINEL_DISSENT_WITNESS_PUBKEY=/secure/path/witness-public.pem
SENTINEL_DISSENT_WITNESS_TOKEN=<value loaded from the 0600 secret file>
SENTINEL_REQUIRE_DISSENT_WITNESS=1
```

**Cloudflare setup:**

1. Generate the dedicated witness keypair:
   `python dissent_witness_keygen.py --private-out /secure/witness-private.pkcs8.b64 --public-out /secure/witness-public.pem`.
   The private file is mode `0600`; keep it off the Sentinel host and away from A7.
2. Create a separate writer credential. Store it in a 0600 file available only to
   the Sentinel service account; do not expose it to A7:
   ```sh
   openssl rand -hex 32 > /secure/witness-advance-token
   chmod 600 /secure/witness-advance-token
   npx wrangler secret put WITNESS_ADVANCE_TOKEN < /secure/witness-advance-token
   ```
3. From the repository root, upload the witness private key only to Cloudflare and
   configure the two row-verification public keys:
   ```sh
   npx wrangler secret put WITNESS_PRIVATE_KEY_PKCS8_B64 < /secure/witness-private.pkcs8.b64
   python dissent_cli.py pubkey-info --role a7 | sed -n 's/^raw_b64=//p' | npx wrangler secret put A7_PUBLIC_KEY_RAW_B64
   python dissent_cli.py pubkey-info --role human | sed -n 's/^raw_b64=//p' | npx wrangler secret put HUMAN_PUBLIC_KEY_RAW_B64
   ```
4. Deploy with `npx wrangler deploy`. The Durable Object migration is declared
   in `wrangler.toml`; record the Worker URL printed by Wrangler.
5. Install the witness public PEM and the writer-token file on the Sentinel host.
   Set `SENTINEL_DISSENT_WITNESS_URL`, `SENTINEL_DISSENT_WITNESS_PUBKEY`,
   `SENTINEL_DISSENT_WITNESS_TOKEN`, and finally
   `SENTINEL_REQUIRE_DISSENT_WITNESS=1` only after the genesis/bootstrapped
   checkpoint has been verified. The token authorizes POST advancement and must
   remain unavailable to A7; the public checkpoint GET is signature-verified.

The witness key is not installed on Sentinel or A7. The Worker verifies existing
A7/human row signatures; it does not grant A7 the ability to sign witness checkpoints.
The Durable Object and Worker deployment are an independent trust boundary only while
the Cloudflare account, Worker code, and Worker secret remain outside the attacker's
control. Compromise or authorized rollback of that provider control plane is outside
this threat model.

**Existing-store bootstrap:** the Worker starts at genesis. For an existing store,
first deploy the Worker and configure the witness URL/public key without enabling
required-witness mode. Then:

1. On the Sentinel host, generate a payload bound to the locally verified row count
   and head:
   `PAYLOAD_B64="$(python dissent_cli.py witness-bootstrap-payload --human theodore --reason 'enroll verified Sentinel dissent history')"`.
2. Transfer only that payload to the human-controlled device. Sign it with the offline
   human key using `SIG_B64="$(printf '%s\\n' "$PAYLOAD_B64" | ./magic_sign_receipt.sh)"`.
3. Return the signature to the Sentinel host and run:
   `python dissent_cli.py witness-bootstrap --payload-b64 "$PAYLOAD_B64" --sig-b64 "$SIG_B64"`.
4. The Worker accepts bootstrap once only, verifies the human signature and every
   row's sequence, hash, A7/human signature, duplicate-ID rule, and receipt linkage,
   then signs the resulting checkpoint. Verify `python dissent_cli.py status` before
   setting `SENTINEL_REQUIRE_DISSENT_WITNESS=1`.

The bootstrap endpoint accepts at most 5,000 rows. This code path is covered by local
regression tests, but live Cloudflare bootstrap and Ed25519 runtime behavior remain
unverified until deployed and exercised against the actual Durable Object.
