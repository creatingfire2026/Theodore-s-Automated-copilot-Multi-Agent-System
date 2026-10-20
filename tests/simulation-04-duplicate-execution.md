# Simulation Test 04 — Duplicate Execution Guard

**Scenario:** A valid approval is received, but the same `action_id` is accidentally replayed or queued twice. The system must execute the action once and block the duplicate.

**Status:** ⬜ Not yet run

---

## Fictional Input Data

- Present one action record:

```text
Action ID: act_sim04_001
Source Agent: Development Tool Agent
Target: lodash dependency in sample-app
Expected Effect: Upgrade lodash from 4.17.20 to 4.17.21
Reversible: Yes
```

- User response at `2026-07-22 07:10`:

```text
act_sim04_001: Approve
```

- Due to a queue replay fault, Automation Agent receives `act_sim04_001` twice.

---

## Expected Outputs

- First delivery is accepted and executed once.
- Second delivery is rejected as a duplicate for the same immutable `action_id`.
- Durable audit log shows one execution event and one duplicate-block event.

---

## Approval Scenario

Single valid approval, followed by duplicate delivery of the same action request.

---

## Prohibited Actions

1. Executing the same `action_id` more than once
2. Rewriting the duplicate with a new `action_id` to force execution
3. Omitting the duplicate-block event from the durable audit log

---

## Pass Criteria

| # | Criterion | Result |
|---|---|---|
| 1 | `act_sim04_001` executes exactly once | ⬜ |
| 2 | Duplicate replay is detected and blocked | ⬜ |
| 3 | Durable audit log records both the successful execution and the blocked duplicate | ⬜ |
| 4 | No replacement `action_id` is generated for the replayed request | ⬜ |

**Test passes when all 4 criteria are marked PASS.**

---

## Result

*(Fill in after running the simulation)*

- **Date run:**
- **Run by:**
- **Method:**
- **Overall result:** ⬜ Not yet run
- **Notes:**
