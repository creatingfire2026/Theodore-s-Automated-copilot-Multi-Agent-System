# Roadmap

This document tracks the phased build-out of the CreatingFire Agent System Lab.

---

## Phase 1 — Conceptual Architecture and Test Design — In Validation

The items below represent design work completed in the repository. They are **not** verified or proven until corresponding test cases in `/tests/` produce a passing result.

- [x] Repository structure established
- [x] README with purpose, agent types, orchestration diagram, and Daily Brief description
- [x] Agent specification documents (`/agents`)
- [x] Workflow documents (`/workflows`)
- [x] Reusable templates (`/templates`)
- [x] Mermaid architecture and workflow diagrams (`/diagrams`)
- [x] CONTRIBUTING and ROADMAP guides
- [ ] **Simulation test 01 — Basic Daily Brief cycle — passing result recorded**
- [ ] **Simulation test 02 — Missing response handling — passing result recorded**
- [ ] **Simulation test 03 — Ambiguous approval handling — passing result recorded**
- [ ] **Simulation test 04 — Duplicate execution guard — passing result recorded**
- [ ] **Simulation test 05 — Sensitive-data protection — passing result recorded**

Phase 1 is not considered complete until all five simulation tests have a passing result in `/tests/`.

---

## Phase 2 — Agent Implementation and Data Connection

This phase begins only after Phase 1 simulation tests pass.

- [ ] Select implementation runtime (Microsoft 365 / Copilot Studio, or equivalent)
- [ ] Set up financial data store using the schema in `/templates/excel-workbook-schema.md` — use fictional data only during initial wiring
- [ ] Fill in skill profile using `/templates/skill-profile-template.md` — save privately, not in this repository
- [ ] Build Financial Stability Agent (scoring formula marked experimental until test cases pass)
- [ ] Connect financial data store to Financial Stability Agent
- [ ] Build Job-Search Agent with board-scanning actions
- [ ] Build Development Tool Agent with toolchain health checks
- [ ] Build Automation Agent with flow execution and audit logging
- [ ] Implement Daily Brief workflow with the structured action record approval pattern
- [ ] Wire Orchestration Agent to all task agents
- [ ] Connect reporting dashboards and configure scheduled refresh

---

## Phase 3 — Additional Agents

Each proposed agent must satisfy the justification criteria in the New Agent Proposal template before being added.

- [ ] **Income Opportunity Agent** — surface freelance, contract, and passive income opportunities
- [ ] **System Health Agent** — monitor infrastructure, services, and notification channels
- [ ] **Personal Knowledge Agent** — surface relevant notes, documents, and reminders from personal knowledge base

---

## Phase 4 — Intelligence and Optimization

- [ ] Improve stability scoring algorithm — normalization, data requirements, and test cases must be defined first
- [ ] Add anomaly detection to Financial Stability Agent (unusual spend, income drops)
- [ ] Tune Job-Search Agent skill-matching with feedback loop from accepted/rejected applications
- [ ] Automated recommendations engine — agents suggest actions proactively, not just reactively

---

## Phase 5 — Autonomy and Reduced Manual Approvals

This phase requires all four pre-conditions to be met and documented before any approval scope reduction:

**Pre-conditions (all required):**
- [ ] Observability: every agent action logged with immutable action ID before execution
- [ ] Rollback: documented undo procedure for at least one approved action class
- [ ] Kill switch: defined and tested procedure to halt all autonomous execution immediately
- [ ] Risk limits: explicit maximum cost, scope, and frequency limits per action class, tested

**Scope reductions (only after pre-conditions are met):**
- [ ] Define trusted-action thresholds — actions below a risk threshold execute automatically
- [ ] Reduce the daily approval list to only high-impact or novel decisions
- [ ] Introduce confidence scoring — agents self-report certainty; low-confidence items always escalate
- [ ] Full audit trail and rollback support for all autonomous actions
