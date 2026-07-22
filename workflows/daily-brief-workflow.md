# Daily Brief Workflow

## Purpose

The Daily Brief is the central human-in-the-loop touchpoint of the multi-agent system. It collects intelligence from all agents each morning, assembles it into a structured summary, presents it for approval, and routes decisions to the Automation Agent for execution.

---

## Schedule

**Trigger:** Power Automate scheduled flow — runs daily at **07:00**

---

## Workflow Steps

### Step 1 — Initiate Collection

The Orchestration Agent sends a collection request to all four agents simultaneously:

- Financial Stability Agent → return stability score, risks, and approval items
- Job-Search Agent → return top 5 opportunities and approval items
- Development Tool Agent → return system health status and approval items
- Automation Agent → return standing flow status and any pending retries

**Timeout:** If an agent does not respond within 5 minutes, its section is marked `⚠ Data unavailable` and the brief proceeds.

---

### Step 2 — Build the Daily Brief

The Orchestration Agent assembles four sections:

#### 📊 Financial Status
```
Stability Score: [0–100]
Net Cashflow: $[amount]
Risk Flags: [list or "None"]
90-Day Projection: [summary sentence]
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
```
1. [Action description] — [Agent] — [Reason]
2. [Action description] — [Agent] — [Reason]
3. [Action description] — [Agent] — [Reason]
(all items requiring human decision)
```

---

### Step 3 — Deliver the Brief

The Orchestration Agent sends the completed brief to Theodore via the configured notification channel (email / Teams / chat).

Message format:
```
Good morning, Theodore. Here is your Daily Brief for [Date].

[Assembled brief sections]

Please respond with your approval decisions:
Example: "1. Yes, 2. No, 3. Yes"
```

---

### Step 4 — Await Response

The workflow enters a **wait state** for up to **4 hours**. If no response is received within the window, all approval items are automatically declined for the current cycle and the Orchestration Agent logs the timeout.

---

### Step 5 — Parse and Route Decisions

The Orchestration Agent parses the user's response:

- `Yes` → action is approved; forwarded to Automation Agent for execution
- `No` → action is declined; logged with reason "User declined"
- Missing number → treated as `No` for that item

---

### Step 6 — Execute Approved Actions

The Automation Agent receives the approved action list and:

1. Triggers the corresponding Power Automate flow for each item
2. Records success or failure for each action
3. Sends a completion confirmation to Theodore

---

### Step 7 — Log Outcomes

All outcomes are written to the audit log:

| Timestamp | Action | Decision | Outcome |
|---|---|---|---|
| 2026-07-22 07:05 | Adjust savings rate | Approved | Flow executed successfully |
| 2026-07-22 07:05 | Pause subscriptions | Declined | User declined |

---

## Error Handling

| Scenario | Response |
|---|---|
| Agent timeout during collection | Section marked unavailable; brief sent anyway |
| User response not received in 4 hours | All items auto-declined; logged as timeout |
| Flow execution failure | Automation Agent flags item; added to next day's brief |
| Malformed user response | Orchestration Agent requests clarification once, then times out |
