---
name: New Agent Proposal
about: Propose a new agent to be added to the multi-agent system
title: "[Agent] "
labels: agent
assignees: ""
---

## Agent Name

<!-- Proposed name, e.g., "Income Opportunity Agent" -->

---

## Justification

Before proposing a new agent, answer the following questions. A proposal that cannot answer them clearly will be declined in review.

### Can an existing capability perform this function?

<!-- Which existing agents or tools were considered? Why are they insufficient? Be specific. -->

### What measurable value does this agent add?

<!-- How will you know this agent is working correctly? What metric or observable output proves it is delivering value? -->

### What is the estimated cost and maintenance burden?

<!-- Consider: API calls, storage, compute, third-party service dependencies, ongoing configuration updates, and human review time. -->

### What permissions does this agent require?

<!-- List every data source, account, system, or external service this agent needs access to. Flag any that involve personal data, financial data, or identity information. -->

### How does this agent fail, and how does it recover?

<!-- What happens when the agent times out, receives bad data, or loses access to a dependency? Describe the failure mode and the recovery path. -->

### What are the retirement criteria?

<!-- Under what conditions should this agent be disabled or removed? How would you know it is no longer needed or is causing harm? -->

---

## Mission

<!-- One to three sentences: what does this agent do, why does it exist, and what outcome does it produce? -->

## Problem It Solves

<!-- What gap in the current system does this agent address? Why is it needed now and not in a later phase? -->

## Inputs

| Source | Description |
|---|---|
| | |

## Triggers

| Trigger | Condition |
|---|---|
| Scheduled | |
| Event-driven | |

## Core Actions

<!-- Describe the main steps this agent would take, numbered -->

1.
2.
3.

## Approval Items

<!-- List the action records this agent would surface for human approval. Reference /templates/approval-pattern.md for the required fields. -->

1.
2.

## Outputs

<!-- What does this agent produce? Where do its outputs go? -->

## Simulation Test Plan

<!-- Before this agent can be implemented, at least one simulation test case must be defined. Describe the fictional inputs, expected outputs, prohibited actions, and pass criteria for the first test. -->

## Which Roadmap Phase Does This Belong To?

- [ ] Phase 2 — Implementation
- [ ] Phase 3 — Additional Agents
- [ ] Phase 4 — Intelligence and Optimization
- [ ] Phase 5 — Autonomy

## Additional Notes

<!-- Anything else relevant — data sources, dependencies on other agents, risks, or open questions -->
