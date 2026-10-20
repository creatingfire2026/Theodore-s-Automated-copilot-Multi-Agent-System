# Approval Pattern

## Purpose

This document describes the human-in-the-loop approval pattern used throughout the system. Every action that modifies data, triggers an automated flow, or takes a consequential step must pass through this pattern before execution.

**Human approval is the default.** The system never assumes approval is granted. Approval scope is only reduced after observability, rollback, a kill switch, and explicit risk limits are all in place and tested.

---

## The Action Record

Every item requiring human decision is represented as a structured **action record**. A numbered Yes/No response list is not sufficient — each action must carry enough context for the human to make an informed decision, and the record must be immutable once created.

### Action Record Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `action_id` | String (UUID) | ✅ | Immutable identifier assigned at the time the action is surfaced. Never reused. |
| `source_agent` | String | ✅ | Name of the agent that surfaced this action |
| `target` | String | ✅ | The specific resource, account, or system the action will affect |
| `expected_effect` | String | ✅ | Plain-language description of what will happen if approved |
| `estimated_cost` | String | ✅ | Financial cost, data written, or external API calls involved. Use "None" if truly zero. |
| `expiration` | ISO 8601 datetime | ✅ | When this action record expires if no decision is made. After expiration, the action is auto-declined. |
| `reversible` | Boolean | ✅ | Whether the action can be undone after execution |
| `undo_procedure` | String | ✅ if reversible=true | How to undo the action if needed |
| `decision` | Enum | Set on response | `Approved`, `Declined`, `Expired`, `No response` |
| `decided_by` | String | Set on response | Identity of the decision-maker |
| `decided_at` | ISO 8601 datetime | Set on response | When the decision was recorded |
| `result` | String | Set after execution | Outcome of execution: `Succeeded`, `Failed`, `Skipped` with reason |

---

## How It Works

### 1. Agent Surfaces an Action Record

Each agent produces a list of action records requiring human approval. These are forwarded to the Orchestration Agent and assembled into the **Actions Requiring Approval** section of the Daily Brief.

Example action record as presented in the Daily Brief:

```
Action ID:       act_20260722_001
Source Agent:    Financial Stability Agent
Target:          Savings rate setting
Expected Effect: Increase savings rate from 15% to 20% for the next 30-day period
Estimated Cost:  None (configuration change only)
Expiration:      2026-07-22 11:00
Reversible:      Yes — revert to previous rate at any time
Reason Surfaced: Stability score dropped to 72; savings rate below target threshold (80)

→ Decision required: Approve or Decline
```

---

### 2. Human Reviews and Decides

The user reads each action record in the brief and responds with a decision per action ID.

Accepted response format (reference by action ID):

```
act_20260722_001: Approve
act_20260722_002: Decline
act_20260722_003: Approve
```

Shorthand (by position number if the brief displays them numbered):

```
1. Approve, 2. Decline, 3. Approve
```

**Any action record not mentioned in the response is treated as `No response` and auto-declined for the current cycle.**

---

### 3. Orchestration Agent Parses the Response

| Response | Outcome |
|---|---|
| `Approve` | Action is approved; forwarded to Automation Agent with the full action record |
| `Decline` | Action is declined; logged as `User declined` with the decision timestamp |
| Not mentioned | Treated as `No response`; logged as `No response — auto-declined` |
| Ambiguous or malformed | Orchestration Agent requests one clarification within 30 minutes; if no reply, auto-declines |
| Past expiration | Action record is marked `Expired`; no execution; logged |

---

### 4. Automation Agent Executes Approved Actions

For each approved action record, the Automation Agent:

1. Verifies the action record has `decision = Approved` and has not expired
2. Checks that the same `action_id` has not already been executed in this cycle (duplicate execution guard)
3. Triggers the corresponding flow or operation
4. Records the outcome in the action record: `result = Succeeded` or `result = Failed` with reason
5. Sends a completion confirmation

---

### 5. Audit Log Entry

Every action record — approved or declined — is written to the **durable audit log**. This log is for consequential decisions and must be retained long-term (not subject to routine telemetry rotation).

Routine operational telemetry (agent heartbeats, timing data, non-consequential events) is written to a separate short-lived telemetry log and may be rotated on a shorter schedule.

Durable audit record format:

```
| action_id           | source_agent               | target                   | expected_effect                      | decision | decided_at       | result    |
|---------------------|----------------------------|--------------------------|--------------------------------------|----------|------------------|-----------|
| act_20260722_001    | Financial Stability Agent  | Savings rate setting     | Increase savings rate 15% → 20%      | Approved | 2026-07-22 07:10 | Succeeded |
| act_20260722_002    | Job-Search Agent           | Application: Acme Corp   | Submit application to Acme Corp      | Declined | 2026-07-22 07:10 | Skipped   |
| act_20260722_003    | Development Tool Agent     | lodash dependency        | Upgrade lodash to 4.17.21            | Approved | 2026-07-22 07:10 | Succeeded |
```

---

## Design Principles

- **Nothing executes without an approved action record.** The system never assumes approval.
- **Every action record is immutable once created.** The `action_id`, `target`, `expected_effect`, `estimated_cost`, and `reversible` fields are set at creation and cannot be changed.
- **Declining is always safe.** A declined item reappears in the next Daily Brief if the condition persists.
- **Durable audit records are permanent.** Consequential decision records are never subject to routine log rotation.
- **Duplicate execution is prohibited.** An `action_id` can only be executed once. A second execution attempt with the same ID is rejected and logged.
- **Approval scope is never reduced prematurely.** Human approval remains the default until observability, rollback, a kill switch, and explicit risk limits are all in place and tested.
