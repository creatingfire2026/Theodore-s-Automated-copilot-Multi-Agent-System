# Getting Started — Run the First Simulation

This guide walks through the **first and most important step**: a zero-cost manual simulation of one Daily Brief cycle using completely fictional data.

No Microsoft 365. No Copilot Studio. No Power Automate. No real personal data.

The simulation is the validation gate for Phase 1. Until it passes, no real data or paid services should be connected.

---

## Why Simulate First

This system is a proposal, not a proven design. The agent logic, scoring formulas, approval workflows, and orchestration patterns are design claims. Simulation is how we find out whether the claims hold before connecting real accounts, real finances, or real notifications.

A simulation also costs nothing. It can be run today with a text editor.

---

## Step 1 — Read the First Test Case

Open [`/tests/simulation-01-basic-daily-brief.md`](tests/simulation-01-basic-daily-brief.md).

This document defines:
- The fictional input data for one Daily Brief cycle
- The expected outputs from each agent
- The approval decision scenario
- The prohibited actions the system must not take
- The pass evidence required to call the test a success

Read it fully before proceeding.

---

## Step 2 — Run the Simulation Manually

You do not need any running software. Work through the test case using the agent spec documents in `/agents/` as your logic reference.

For each agent, manually apply the logic to the fictional inputs:

1. **Financial Stability Agent** — apply the scoring formula from [`/agents/financial-stability-agent.md`](agents/financial-stability-agent.md) to the fictional financial data. Record the score, risk flags, and projection.
2. **Job-Search Agent** — apply the skill-match scoring to the fictional job listings against the fictional skill profile. Record the top 5 ranked results.
3. **Development Tool Agent** — apply the dependency audit and toolchain health rules to the fictional project state. Record the health summary.
4. **Orchestration Agent** — assemble the four sections of the Daily Brief from the outputs above. Record the assembled brief.
5. **Approval step** — apply the fictional approval decision from the test case. Record which action records are approved and which are declined.
6. **Automation Agent** — record what would be executed for each approved action. Verify no prohibited actions occur.
7. **Audit log** — write the audit log entries for all decisions and outcomes.

---

## Step 3 — Record Pass Evidence

Compare your simulation outputs against the expected outputs and pass criteria defined in the test case.

If every criterion passes, record the result in the test file:
- Date
- Your name or handle
- A brief description of how you ran the simulation
- Confirmation of each pass criterion

If any criterion fails, record what failed and what the correct behavior should be. Open an issue or update the relevant agent spec before re-running.

---

## Step 4 — Run the Remaining Simulation Tests

Once Test 01 passes, work through the remaining tests in `/tests/`:

| Test | Scenario |
|---|---|
| 02 | Missing response — no approval reply within the wait window |
| 03 | Ambiguous approval — malformed or partial decision response |
| 04 | Duplicate execution guard — same action approved twice in one cycle |
| 05 | Sensitive-data protection — fictional data containing PII-like values |

All five tests must pass before Phase 1 is considered validated.

---

## Step 5 — Phase 2 Implementation (Only After Simulation Tests Pass)

Once all five simulation tests have passing results recorded in `/tests/`, Phase 2 implementation can begin.

**Implementation is adapter selection, not architecture design.** The architecture is specified in `/agents/` and `/workflows/`. Phase 2 is choosing which runtime to use to implement it.

### Option A — Microsoft 365 Ecosystem
- Copilot Studio for agent authoring
- Power Automate for scheduling and flow execution
- Excel Online (via OneDrive/SharePoint) as the financial data store
- Power BI for reporting dashboards
- Teams or email for notification delivery

### Option B — Alternative Runtime
Any combination of tools that satisfies the agent specs and passes the simulation tests is acceptable. The agent specs are implementation-agnostic.

### Setting Up the Financial Data Store (Use Fictional Data First)

Before connecting any real financial data:

1. Build the workbook structure using [`/templates/excel-workbook-schema.md`](templates/excel-workbook-schema.md)
2. Populate it with fictional data matching the format in the test cases
3. Verify the Financial Stability Agent reads and scores it correctly
4. Only replace fictional data with real data after the agent produces correct results on fictional inputs

> **Data safety reminder:** Never commit the financial workbook to this repository. It is excluded by `.gitignore`. Store it in private cloud storage or locally. Do not include real account numbers, income amounts, employer names, or any personally identifying information in any file committed here.

### Setting Up the Skill Profile

1. Copy [`/templates/skill-profile-template.md`](templates/skill-profile-template.md) to a private location outside this repository
2. Fill in your actual skills, certifications, experience, and preferences
3. Do not commit real employment history, identity information, or contact details to this public repository

---

## What Has Not Been Verified Yet

- The stability scoring formula produces meaningful, calibrated results across different financial situations
- The 90-day linear projection is accurate for the data patterns it will encounter
- The skill-match fit score correlates with actual job interview success rates
- The orchestration agent correctly handles all edge cases (timeouts, partial responses, duplicate approvals)
- Any of the agent logic works correctly in a real implementation runtime

These are all open questions that the simulation tests and Phase 2 are designed to answer.
