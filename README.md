# CreatingFire Agent System Lab

An evidence-driven laboratory for designing, simulating, testing, and validating a sovereign AI-agent operating system.

> **Status: Unverified — In Active Design and Simulation**
> This repository is a laboratory and requirements scaffold. The architecture described here has not been deployed, tested end-to-end, or validated against real data. All agent logic, scoring formulas, and workflow patterns are **proposals under review**, not proven designs. No claim is made that the system is production-ready or that any component works as described until a passing test case is committed.

---

## Purpose

This repository is an evidence-driven laboratory for:

- **Designing** a multi-agent operating system that surfaces daily intelligence and routes human decisions
- **Simulating** agent behavior with fictional data before any real infrastructure is connected
- **Testing** each workflow, approval pattern, and scoring formula against defined pass criteria
- **Validating** that human approval remains the execution authority at every consequential step

The lab is **implementation-agnostic**. Microsoft 365, Copilot Studio, Power Automate, Excel, and Power BI are one possible implementation path, not mandatory foundations. Any orchestration runtime, spreadsheet, notification channel, or approval mechanism that satisfies the test criteria is acceptable.

---

## Agent Types

| Type | Role |
|---|---|
| **Orchestration Agent** | Coordinates all agents, collects summaries, builds the Daily Brief, routes approvals |
| **Task Agent** | Executes a single repeatable action (e.g., update a record, send a notification) |
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
│ • Cashflow       │       │ • Board scanner   │       │ • Toolchain health   │       │ • Execute flows  │
│ • Stability score│       │ • Skill matcher   │       │ • Lint & config check│       │ • Update records │
│ • Risk flags     │       │ • Draft apps      │       │ • Optimizations      │       │ • Notifications  │
│ • Projections    │       │ • Rank opps       │       │ • Dependency audit   │       │ • Log outcomes   │
│ ⚠ Experimental  │       │                   │       │                      │       │                  │
└──────────────────┘       └───────────────────┘       └──────────────────────┘       └──────────────────┘
```

---

## Daily Brief Workflow

The proposed daily sequence. Each step is a **design claim** that requires a passing simulation before it is treated as verified.

1. **Trigger** — Runs at 07:00 via a configured scheduler
2. **Collect** — Orchestration Agent requests summaries from all agents
3. **Build** — Assembles a structured Daily Brief with four sections:
   - 📊 **Financial Status** — current score, risks, projections *(scoring formula experimental)*
   - 💼 **Income Opportunities** — top job matches, ranked by fit
   - 🔧 **System Health** — toolchain status, pending upgrades
   - ✅ **Actions Requiring Approval** — structured action records pending human decision
4. **Present** — Brief is delivered via the configured notification channel
5. **Await** — System waits for decisions against each action record
6. **Route** — Orchestration Agent sends approved items for execution; logs all decisions
7. **Log** — Consequential decisions written to the durable audit record; routine telemetry to short-lived logs

---

## Repository Structure

```
/
├── README.md                      ← This file
├── GETTING_STARTED.md             ← How to run the first simulation (no paid services required)
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
│   ├── skill-profile-template.md
│   └── approval-pattern.md
│
├── tests/
│   ├── README.md                  ← Test plan index and pass criteria
│   └── simulation-01-basic-daily-brief.md  ← First validation test
│
└── diagrams/
    ├── multi-agent-map.mermaid
    └── workflow-diagram.mermaid
```

---

## Validation Before Deployment

**No component of this system should be connected to real data, real accounts, or real notification channels until it has a passing simulation test recorded in `/tests/`.**

The first required test is defined in [`/tests/simulation-01-basic-daily-brief.md`](tests/simulation-01-basic-daily-brief.md). It uses fictional data only, requires no paid services, and can be run manually.

Required conditions before reducing human approval scope:

- [ ] Observability: every agent action is logged with an action ID before execution
- [ ] Rollback: at least one approved action class has a documented undo procedure
- [ ] Kill switch: there is a defined procedure to halt all autonomous execution immediately
- [ ] Risk limits: explicit maximum cost, scope, and frequency limits per action class are documented and tested

---

## Data Safety

- **Do not commit real financial data, employment records, identity information, or credentials** to this repository.
- Use the example/template files provided in `/templates/` for structural reference only.
- Personal financial data belongs in private storage (OneDrive, local encrypted drive) — never in this public repository.
- The `.gitignore` excludes `*.xlsx`, `*.pbix`, `*.env`, `secrets/`, and runtime logs. Safe test fixtures (JSON, CSV, SVG) **can** be committed if they contain only fictional example data.

---

## Getting Started

See **[GETTING_STARTED.md](GETTING_STARTED.md)** for the recommended starting path: a zero-cost manual simulation of the first Daily Brief cycle using fictional data, with no Microsoft 365 or Copilot Studio required.

---

## License

MIT — see [LICENSE](LICENSE)
