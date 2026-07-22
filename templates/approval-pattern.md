# Approval Pattern

## Purpose

This document describes the standard human-in-the-loop approval pattern used throughout the system. Every action that modifies data, triggers a flow, or takes a consequential step must pass through this pattern before execution.

---

## How It Works

### 1. Agent Surfaces Approval Items

Each agent produces a numbered list of actions requiring human approval. These are forwarded to the Orchestration Agent, which assembles them into the **Actions Requiring Approval** section of the Daily Brief.

Example output from the Daily Brief:

```
✅ Actions Requiring Approval

1. Adjust savings rate from 15% to 20% — Financial Stability Agent
   Reason: Stability score dropped to 72; savings rate below target.

2. Submit application to Acme Corp (Senior Dev, Fit: 87%) — Job-Search Agent
   Reason: Top-ranked opportunity from today's scan.

3. Upgrade lodash to 4.17.21 (CVE-2021-23337 patched) — Development Tool Agent
   Reason: High-severity vulnerability detected.
```

---

### 2. User Responds with Yes/No

The user reads the brief and replies with a comma-separated response list, one decision per numbered item:

```
1. Yes, 2. No, 3. Yes
```

Or written out:

```
1 yes
2 no
3 yes
```

Both formats are accepted. **Any item not mentioned is treated as No for the current cycle.**

---

### 3. Orchestration Agent Parses the Response

| Response | Outcome |
|---|---|
| `Yes` | Action is approved; forwarded to Automation Agent |
| `No` | Action is declined; logged as "User declined" |
| Item not mentioned | Treated as `No`; logged as "No response — auto-declined" |
| Ambiguous or malformed | Orchestration Agent requests one clarification; if no reply, auto-declines |

---

### 4. Automation Agent Executes Approved Actions

For each approved item, the Automation Agent:
1. Triggers the corresponding Power Automate flow
2. Records the outcome (success / failure)
3. Sends a completion confirmation to the user

---

### 5. Audit Log Entry

Every approval decision — whether Yes or No — is written to the audit log:

```
| Timestamp           | Item | Action                          | Decision | Outcome               |
|---------------------|------|---------------------------------|----------|-----------------------|
| 2026-07-22 07:10    | 1    | Adjust savings rate to 20%      | Approved | Flow executed: OK     |
| 2026-07-22 07:10    | 2    | Submit application to Acme Corp | Declined | User declined         |
| 2026-07-22 07:10    | 3    | Upgrade lodash to 4.17.21       | Approved | Flow executed: OK     |
```

---

## Design Principles

- **Nothing executes without explicit approval.** The system never assumes Yes.
- **Declining is always safe.** A declined item is simply deferred; it reappears in the next Daily Brief if the condition persists.
- **The audit log is permanent.** All decisions are recorded regardless of outcome.
- **One approval window per day.** Approval requests are batched into the Daily Brief. Emergency escalations are the only exception.
