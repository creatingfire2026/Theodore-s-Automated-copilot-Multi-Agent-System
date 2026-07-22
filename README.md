# Theodore's Automated Copilot Multi-Agent System

A commanding Copilot-driven multi-agent system forged for stability, opportunity, and precision. Financial intelligence, job-seeking automation, and toolchain optimization unite under a disciplined orchestration core, empowering Theodore's digital ecosystem to rise, adapt, and endure — and scale with new and existing pioneers in the technology sector.

---

## Purpose

This repository is a blueprint and scaffold for a **Copilot-driven multi-agent automation system** built on:

- **GitHub Copilot** — AI-assisted development and code review
- **Copilot Studio** — custom agent authoring and orchestration
- **Power Automate** — workflow automation and approvals
- **Excel** — financial data input and modeling
- **Power BI** — dashboards and reporting

The system runs daily, surfaces intelligent summaries, and routes decisions through a human-in-the-loop approval layer before taking any consequential action.

---

## Agent Types

| Type | Role |
|---|---|
| **Orchestration Agent** | Coordinates all agents, collects summaries, builds the Daily Brief, routes approvals |
| **Task Agent** | Executes a single repeatable action (e.g., update a spreadsheet, send a notification) |
| **Analytical Agent** | Processes data, computes scores, detects patterns, and surfaces insights |
| **Workflow Agent** | Drives multi-step automated flows with conditional logic and human checkpoints |

---

## Multi-Agent Orchestration Diagram

```
                         ┌──────────────────────────────┐
                         │      Orchestration Agent      │
                         │  (Daily Brief · Approvals)    │
                         └──────────────┬───────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │                            │
           ▼                            ▼                            ▼                            ▼
┌──────────────────┐       ┌───────────────────┐       ┌──────────────────────┐       ┌──────────────────┐
│ Financial        │       │  Job-Search       │       │ Development Tool     │       │ Automation       │
│ Stability Agent  │       │  Agent            │       │ Agent                │       │ Agent            │
│                  │       │                   │       │                      │       │                  │
│ • Cashflow       │       │ • Board scanner   │       │ • Toolchain health   │       │ • Run PA flows   │
│ • Stability score│       │ • Skill matcher   │       │ • Lint & config check│       │ • Update dashbds │
│ • Risk flags     │       │ • Draft apps      │       │ • Optimizations      │       │ • Notifications  │
│ • Projections    │       │ • Rank opps       │       │ • Dependency audit   │       │ • Log outcomes   │
└──────────────────┘       └───────────────────┘       └──────────────────────┘       └──────────────────┘
```

---

## Daily Brief Workflow

Every morning the system executes the following sequence:

1. **Trigger** — Runs at **07:00** via Power Automate scheduled flow
2. **Collect** — Orchestration Agent requests summaries from all agents
3. **Build** — Assembles a structured Daily Brief with four sections:
   - 📊 **Financial Status** — current score, risks, projections
   - 💼 **Income Opportunities** — top job matches, ranked by fit
   - 🔧 **System Health** — toolchain status, pending upgrades
   - ✅ **Actions Requiring Approval** — numbered list of pending decisions
4. **Present** — Brief is delivered to Theodore (email / Teams / chat)
5. **Await** — System waits for Yes/No responses (e.g., `1. Yes, 2. No, 3. Yes`)
6. **Route** — Orchestration Agent sends approved items to the Automation Agent for execution; logs declined ones
7. **Log** — All decisions and outcomes are written to the audit log

---

## Repository Structure

```
/
├── README.md                      ← This file
├── GETTING_STARTED.md             ← Week-by-week Phase 2 build guide
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
├── ROADMAP.md
│
├── .github/
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
│       ├── new-agent-proposal.md
│       └── workflow-improvement.md
│
├── agents/
│   ├── orchestration-agent.md
│   ├── financial-stability-agent.md
│   ├── job-search-agent.md
│   ├── development-tool-agent.md
│   └── automation-agent.md
│
├── workflows/
│   ├── daily-brief-workflow.md
│   └── orchestration-map.md
│
├── templates/
│   ├── copilot-studio-agent-template.md
│   ├── excel-workbook-schema.md
│   ├── skill-profile-template.md  ← Fill in and save as /agents/skill-profile.md
│   └── approval-pattern.md
│
└── diagrams/
    ├── multi-agent-map.mermaid
    └── workflow-diagram.mermaid
```

---

## Getting Started

See **[GETTING_STARTED.md](GETTING_STARTED.md)** for a complete week-by-week Phase 2 build guide — from setting up the Excel Finance Workbook on Day 1 to running the full Daily Brief by the end of Week 5.

Quick orientation:
1. Review the agent specs in `/agents`
2. Fill in your skill profile using `/templates/skill-profile-template.md`
3. Follow `/templates/copilot-studio-agent-template.md` to build each agent in Copilot Studio
4. Configure Power Automate flows using `/workflows/daily-brief-workflow.md`
5. Connect Excel and Power BI data sources to the Financial Stability Agent
6. Deploy and run the Daily Brief workflow

---

## License

MIT — see [LICENSE](LICENSE)
