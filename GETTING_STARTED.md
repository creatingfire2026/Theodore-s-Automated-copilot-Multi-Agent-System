# Getting Started — Phase 2 Build Guide

Phase 1 is done. The architecture is solid, every agent is specified, and the workflows are mapped. This document is your guide for Phase 2: turning the blueprint into a running system.

Work at your own pace. Each step is independent — you can do one a day, one a week, whatever your situation allows. The system builds incrementally and delivers value even before it is fully wired together.

---

## Before You Begin

Confirm you have access to all of the following. You do not need all of them on Day 1 — but you will need them before the system can run end to end.

| Service | Required For | Where to Get It |
|---|---|---|
| Microsoft 365 | Power Automate, Excel, Teams | microsoft.com/microsoft-365 |
| Copilot Studio | Building each agent | copilotstudio.microsoft.com |
| Power Automate | Daily trigger, flow execution | powerautomate.microsoft.com |
| Power BI | Financial dashboards | powerbi.microsoft.com |
| GitHub Copilot | Code assistance (optional) | github.com/features/copilot |

---

## Week 1 — Financial Foundation

### Day 1: Set Up the Excel Finance Workbook

This is the system's data source. Everything else reads from it.

1. Open Excel (desktop or online)
2. Create a new blank workbook
3. Create five sheets named exactly:
   - `Income`
   - `Expenses`
   - `Savings`
   - `Debt`
   - `Summary`
4. Build each sheet using the column definitions in [`/templates/excel-workbook-schema.md`](templates/excel-workbook-schema.md)
5. Enter **one month of real data** — this gives the Financial Stability Agent something to score on Day 1
6. On the `Summary` sheet, define the named ranges listed in the schema using Excel's **Formulas → Name Manager**
7. Save the workbook to **OneDrive or SharePoint** (not your local drive — the agent needs to reach it via Power Automate)

> Do not commit this file to the repository. It is already excluded by `.gitignore`.

---

### Day 2–3: Build the Financial Stability Agent in Copilot Studio

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com)
2. Click **Create** → **New agent**
3. Name it: `Financial Stability Agent`
4. In the description, paste the Mission statement from [`/agents/financial-stability-agent.md`](agents/financial-stability-agent.md)
5. Under **Actions**, add a new action connected to **Excel Online (Business)** via the Power Automate connector
   - Action: Read rows from `Summary` sheet
   - Map each named range to a variable in the agent
6. Build the **Stability Score topic**:
   - Input variables: `NetCashflow`, `SavingsRate`, `DebtToIncome`, `EmergencyFundMonths`, expense trend delta
   - Apply the weighted scoring formula from the agent spec (30/25/20/15/10 weights)
   - Output: `StabilityScore` (integer 0–100)
7. Build the **Risk Flag topic**:
   - Check each of the five risk conditions defined in the spec
   - Output: array of flag strings
8. Build the **90-Day Projection topic**:
   - Use the last 3 months of income and expense data from Excel
   - Apply linear trend extrapolation
   - Output: a plain-language projection sentence
9. Build the **Summary Generation topic**:
   - Assemble the four outputs into the structured paragraph format defined in the Daily Brief workflow
10. **Publish** the agent

---

### Day 4–5: Test the Financial Stability Agent

1. In Copilot Studio, open the **Test chat** panel
2. Send: `Run financial stability check`
3. Verify the agent reads from your Excel workbook and returns:
   - A score between 0–100
   - A risk flag list (or "None")
   - A 90-day projection sentence
4. If the score reads correctly, the Financial Stability Agent is functional
5. Update [`ROADMAP.md`](ROADMAP.md) — check off: `Build Financial Stability Agent in Copilot Studio` and `Connect Excel finance workbook to Financial Stability Agent`

---

## Week 2 — Job Search Engine

### Day 1: Fill In Your Skill Profile

1. Copy [`/templates/skill-profile-template.md`](templates/skill-profile-template.md) to a new file at `/agents/skill-profile.md`
2. Fill in your actual skills, certifications, experience, preferences, and constraints
3. Commit the file — this becomes the Job-Search Agent's reference document

> This is the single most important configuration step for the Job-Search Agent. The more accurate your profile, the better the fit scores.

---

### Day 2–4: Build the Job-Search Agent in Copilot Studio

1. Create a new agent: `Job-Search Agent`
2. Paste the Mission from [`/agents/job-search-agent.md`](agents/job-search-agent.md)
3. Connect your Skill Profile (`/agents/skill-profile.md`) as a knowledge source
4. Under **Actions**, configure board feeds:
   - LinkedIn Jobs API or RSS (requires LinkedIn developer access)
   - Indeed RSS feed (publicly available)
   - Any other boards you prefer
5. Build the **Board Scan topic**: fetch and normalize listings since last run
6. Build the **Skill Match Scoring topic**: compare each listing against skill profile; compute fit score; discard below 60
7. Build the **Rank and Filter topic**: apply your preference filters; return top 5
8. Build the **Draft Cover Letter topic**: for each top opportunity, generate a tailored outline
9. **Publish** the agent

---

## Week 3 — System Health and Automation Layers

### Development Tool Agent

1. Create a new agent: `Development Tool Agent`
2. Connect your active GitHub repositories as knowledge/data sources
3. Build topics for: toolchain health check, dependency audit, linting check, CI/CD health review
4. Reference [`/agents/development-tool-agent.md`](agents/development-tool-agent.md) for the full spec

### Automation Agent

1. Create a new agent: `Automation Agent`
2. Its primary function is executing Power Automate flows — connect it to your Power Automate environment
3. Build topics for: execute approved flows, trigger Power BI refresh, send notifications, write audit log entries
4. Reference [`/agents/automation-agent.md`](agents/automation-agent.md) for the full spec

---

## Week 4 — Orchestration Layer

This is the most important and most complex agent. Build it last, after all four sub-agents are tested and running.

1. Create a new agent: `Orchestration Agent`
2. Connect it to all four sub-agents as callable actions
3. Build the **Daily Brief Assembly topic** — calls all four agents, collects responses, assembles the four-section brief
4. Build the **Response Parsing topic** — parses `1. Yes, 2. No, 3. Yes` format
5. Build the **Route Decisions topic** — sends approved items to Automation Agent; logs declined
6. Build the **Escalation Handling topic** — out-of-schedule urgent briefs
7. Build the **Audit Logging topic** — writes every event to the log store
8. Reference [`/agents/orchestration-agent.md`](agents/orchestration-agent.md) and [`/workflows/orchestration-map.md`](workflows/orchestration-map.md) for the full spec
9. **Publish** the agent

---

## Week 5 — Wire It All Together

### Set Up the Power Automate Daily Trigger

1. Go to [powerautomate.microsoft.com](https://powerautomate.microsoft.com)
2. Create a new **Scheduled cloud flow**
3. Set trigger: **Daily at 07:00** (your local timezone)
4. Add action: **Call Copilot Studio agent** → select `Orchestration Agent`
5. Pass trigger payload: `{ "trigger": "daily_brief" }`
6. Save and **turn on** the flow
7. Test by manually running the flow — verify the Daily Brief arrives in your email or Teams channel

### Connect Power BI

1. Open Power BI
2. Create a new dataset sourced from your Excel Finance Workbook (via OneDrive)
3. Build two report pages:
   - **Financial Status** — stability score gauge, cashflow trend, risk flags
   - **Job Opportunities** — top matches from the last 7 days
4. Set the dataset to **Daily scheduled refresh at 07:30**

---

## You're Done When

- [ ] Daily Brief arrives at 07:00 every morning
- [ ] You can reply with approval decisions and see them execute
- [ ] Financial stability score updates from your real Excel data
- [ ] Job opportunities appear in the brief on days they exist
- [ ] All decisions appear in the audit log

That's the complete system. Every piece was already designed. This guide is just the order in which to build it.

---

## If You Get Stuck

- Each agent spec in `/agents` has the full logic definition
- Each workflow in `/workflows` has the step-by-step flow
- The templates in `/templates` have reusable patterns for approvals, agent structure, and data schemas
- Open an issue in this repository using the templates in `.github/ISSUE_TEMPLATE` if you want to propose a change or ask for help

Take it one week at a time. The system will be running before you know it.
