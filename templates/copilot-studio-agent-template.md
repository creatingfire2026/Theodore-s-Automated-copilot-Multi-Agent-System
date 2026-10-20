# Copilot Studio Agent Template

Use this template as the starting point for every new agent added to the system. Fill in all sections. Do not leave sections blank — write `N/A` if a section genuinely does not apply, and explain why.

---

## Agent Name

`[agent-name]`

---

## Mission

_One to three sentences describing what this agent does, why it exists, and what outcome it produces._

---

## Inputs

| Source | Description |
|---|---|
| [Source name] | [What data it provides and in what format] |
| [Source name] | [What data it provides and in what format] |

---

## Triggers

| Trigger | Condition |
|---|---|
| Scheduled | [Daily at HH:MM / Weekly on Day / etc.] |
| Event-driven | [On [specific event]] |
| On-demand | [On request from Orchestration Agent / user] |

---

## Core Actions

_Number each action. Describe what the agent does step by step. Be specific enough that a developer can implement it._

1. **[Action Name]** — [Description]
2. **[Action Name]** — [Description]
3. **[Action Name]** — [Description]

---

## Approval Checkpoints

_List every action that requires human approval before execution. If the agent is fully automated with no approval gates, write "This agent does not surface approval items."_

| # | Action | Condition |
|---|---|---|
| 1 | [What the user is approving] | [When this item appears] |
| 2 | [What the user is approving] | [When this item appears] |

---

## Outputs

_List all outputs this agent produces. These become inputs to the Orchestration Agent or other agents._

- [Output 1] — [format / destination]
- [Output 2] — [format / destination]

---

## Escalation

_Describe the condition under which this agent escalates outside the normal schedule, and what it sends to the Orchestration Agent._

If [condition], the agent immediately notifies the Orchestration Agent with [payload]. The Orchestration Agent [response action].
