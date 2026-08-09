# Orchestration Map

## Overview

The Orchestration Agent sits at the center of the system. It coordinates all agent-to-agent communication, owns the Daily Brief lifecycle, and is the only agent that interacts directly with the user.

No agent takes action without first routing through the Orchestration Agent. No action is executed without user approval via the Orchestration Agent.

---

## Orchestration Flow (Text Diagram)

```
User / Theodore
      │
      │ (reads Daily Brief, sends Yes/No responses)
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                  Orchestration Agent                │
│                                                     │
│  • Schedules and triggers all agents at 07:00       │
│  • Collects summaries from all agents               │
│  • Builds and delivers the Daily Brief              │
│  • Awaits and parses user approval responses        │
│  • Routes approved actions to Automation Agent      │
│  • Logs all outcomes to the audit trail             │
│  • Handles escalations from any agent               │
└──────┬──────────────┬──────────────┬───────────────┬┘
       │              │              │               │
       ▼              ▼              ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────┐
│  Financial   │ │  Job-Search  │ │Development │ │  Automation  │
│  Stability   │ │  Agent       │ │Tool Agent  │ │  Agent       │
│  Agent       │ │              │ │            │ │              │
│              │ │              │ │            │ │  ← Receives  │
│  Analytical  │ │  Analytical  │ │ Analytical │ │    approved  │
│  Agent       │ │  + Task      │ │ + Task     │ │    actions   │
│              │ │  Agent       │ │ Agent      │ │              │
│  Escalates → │ │  Escalates → │ │ Escalates→ │ │  Executes    │
│  if score<70 │ │ if no matches│ │ if Crit CVE│ │  PA flows    │
│              │ │   for 3 days │ │            │ │              │
└──────────────┘ └──────────────┘ └────────────┘ └──────────────┘
       │                │               │               │
       └────────────────┴───────────────┴───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Data & Platform     │
                    │                       │
                    │  • Excel Workbook     │
                    │  • Power BI Dataset   │
                    │  • Power Automate     │
                    │  • Notification Layer │
                    │  • Audit Log          │
                    └───────────────────────┘
```

---

## Agent Interaction Matrix

| From → To | Orchestration | Financial | Job-Search | Dev Tool | Automation |
|---|---|---|---|---|---|
| **Orchestration** | — | Trigger / Request | Trigger / Request | Trigger / Request | Execute approved actions |
| **Financial** | Escalate (score < 70) | — | — | — | — |
| **Job-Search** | Escalate (no matches for 3 consecutive days) | — | — | — | — |
| **Dev Tool** | Escalate (Critical CVE) | — | — | — | — |
| **Automation** | Execution report / errors | — | — | — | — |

---

## Orchestration Rules

1. **The Orchestration Agent is the only agent that communicates with the user.** All other agents communicate only with the Orchestration Agent.
2. **No action is taken without user approval**, except standing flows already approved for recurring execution.
3. **Escalations bypass the daily schedule** — critical flags trigger an immediate unscheduled brief.
4. **All agent outputs are logged** by the Orchestration Agent before any action is taken.
5. **The Automation Agent executes, it does not decide.** Decision authority rests with the user via the Orchestration Agent.
