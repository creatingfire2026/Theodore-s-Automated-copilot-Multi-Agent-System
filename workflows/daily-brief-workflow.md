# Daily Brief Workflow

## Purpose

The Daily Brief is the central human-in-the-loop touchpoint of the multi-agent system. It collects intelligence from all agents each morning, assembles it into a structured summary, presents it for approval, and routes approved action records to the Automation Agent for execution.

---

## Schedule

**Trigger:** Configured scheduled flow — runs daily at **07:00**

The scheduler is implementation-agnostic. Power Automate, cron, a cloud function, or any reliable scheduled trigger is acceptable.

---

## Workflow Steps

### Step 1 — Initiate Collection

The Orchestration Agent sends a collection request to all four agents simultaneously:

- Financial Stability Agent → return stability score, risks, and action records
- Job-Search Agent → return top 5 opportunities and action records
- Development Tool Agent → return system health status and action records
- Automation Agent → return standing flow status and any pending retries

**Timeout:** If an agent does not respond within 5 minutes, its section is marked `⚠ Data unavailable` and the brief proceeds.

---

### Step 2 — Build the Daily Brief

The Orchestration Agent assembles four sections. Each action record in the approval section is assigned a unique `action_id` at this step.

#### 📊 Financial Status *(Experimental — see agent spec for caveats)*
```
Stability Score: [0–100] ⚠ Experimental formula
Net Cashflow: [amount]
Risk Flags: [list or "None"]
90-Day Projection: [summary sentence — linear extrapolation estimate only]
```

#### 💼 Income Opportunities
```
1. [Role Title] — [Company] | Fit: [score]% | [Link]
2. [Role Title] — [Company] | Fit: [score]% | [Link]
3. [Role Title] — [Company] | Fit: [score]% | [Link]
(up to 5 listings)
```

#### 🔧 System Health
```
Toolchain: [OK / Warning / Error]
Vulnerabilities: [count] | Highest: [severity]
CI/CD: [pass rate]% (last 7 runs)
```

#### ✅ Actions Requiring Approval

Each item is a structured action record. See [`/templates/approval-pattern.md`](../templates/approval-pattern.md) for the full field definitions.

```
Action ID:       [action_id]
Source Agent:    [agent name]
Target:          [specific resource or system]
Expected Effect: [plain-language description]
Estimated Cost:  [cost or "None"]
Expiration:      [ISO 8601 datetime]
Reversible:      [Yes/No — with undo procedure if Yes]
Reason Surfaced: [why this action is being proposed]

→ Decision required: Approve or Decline
```

---

### Step 3 — Deliver the Brief

The Orchestration Agent sends the completed brief to the user via the configured notification channel.

Message format:
```
Good morning. Here is your Daily Brief for [Date].

[Assembled brief sections]

Please respond with your approval decisions for each action record.
Reference by Action ID or by position number.
Example: "act_xxx_001: Approve, act_xxx_002: Decline"
or: "1. Approve, 2. Decline, 3. Approve"

Any action record not mentioned will be auto-declined for this cycle.
Expiration times are listed per item.
```

---

### Step 4 — Await Response

The workflow enters a **wait state** for up to **4 hours**. If no response is received within the window, all pending action records are marked `No response — auto-declined` and the Orchestration Agent writes the outcome to the durable audit log.

---

### Step 5 — Parse and Route Decisions

The Orchestration Agent parses the user's response and matches decisions to action records:

- `Approve` → action record is approved; verified not expired and not already executed; forwarded to Automation Agent
- `Decline` → action record is declined; logged to durable audit log with decision timestamp
- Not mentioned → treated as `No response — auto-declined` for this cycle
- Past expiration → logged as `Expired`; not forwarded

---

### Step 6 — Execute Approved Actions

The Automation Agent receives the approved action record list and for each record:

1. Verifies `decision = Approved`, not expired, `action_id` not already executed
2. Triggers the corresponding flow or operation
3. Records `result = Succeeded` or `result = Failed` in the action record
4. Sends a completion confirmation

---

### Step 7 — Write Audit Records

Consequential decisions are written to the **durable audit log** (long-term retention):

| action_id | source_agent | target | expected_effect | decision | decided_at | result |
|---|---|---|---|---|---|---|
| act_20260722_001 | Financial Stability Agent | Savings rate | Increase rate 15% → 20% | Approved | 2026-07-22 07:10 | Succeeded |
| act_20260722_002 | Job-Search Agent | Acme Corp application | Submit application | Declined | 2026-07-22 07:10 | Skipped |

Routine operational events (timing, agent response status, cycle completion) are written to **operational telemetry** (short-lived, separate from durable audit records).

---

## Error Handling

| Scenario | Response |
|---|---|
| Agent timeout during collection | Section marked unavailable; brief sent anyway |
| User response not received in 4 hours | All action records auto-declined; written to durable audit log as `No response` |
| Flow execution failure | Automation Agent flags item; added to next day's brief as a new action record |
| Malformed user response | Orchestration Agent requests clarification once within 30 minutes, then auto-declines unresolved items |
| Action record expired before decision | Marked `Expired`; not executed; written to durable audit log |
| Duplicate `action_id` execution attempt | Rejected; logged as `Duplicate execution attempt — rejected` |
