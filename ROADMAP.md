# Roadmap

This document tracks the phased build-out of Theodore's Automated Copilot Multi-Agent System.

---

## Phase 1 — Architecture and Documentation ✅ Complete

- [x] Repository structure established
- [x] README with purpose, agent types, orchestration diagram, and Daily Brief description
- [x] Agent specification documents (`/agents`)
- [x] Workflow documents (`/workflows`)
- [x] Reusable templates (`/templates`)
- [x] Mermaid architecture and workflow diagrams (`/diagrams`)
- [x] CONTRIBUTING and ROADMAP guides

---

## Phase 2 — Agent Implementation and Data Connection

See [GETTING_STARTED.md](GETTING_STARTED.md) for the complete step-by-step guide.

- [ ] Set up Excel Finance Workbook (using `/templates/excel-workbook-schema.md`)
- [ ] Fill in skill profile (using `/templates/skill-profile-template.md` → save as `/agents/skill-profile.md`)
- [ ] Build Financial Stability Agent in Copilot Studio
- [ ] Connect Excel finance workbook and Power BI dataset to Financial Stability Agent
- [ ] Build Job-Search Agent with board-scanning actions
- [ ] Build Development Tool Agent with toolchain health checks
- [ ] Build Automation Agent with Power Automate flow triggers
- [ ] Implement Daily Brief workflow in Power Automate
- [ ] Wire Orchestration Agent to all task agents
- [ ] Connect Power BI dashboards and configure scheduled refresh

---

## Phase 3 — Additional Agents

- [ ] **Income Opportunity Agent** — surface freelance, contract, and passive income opportunities
- [ ] **System Health Agent** — monitor infrastructure, services, and notification channels
- [ ] **Personal Knowledge Agent** — surface relevant notes, documents, and reminders from personal knowledge base

---

## Phase 4 — Intelligence and Optimization

- [ ] Improve stability scoring algorithm with weighted risk factors
- [ ] Add anomaly detection to Financial Stability Agent (unusual spend, income drops)
- [ ] Tune Job-Search Agent skill-matching with feedback loop from accepted/rejected applications
- [ ] Automated recommendations engine — agents suggest actions proactively, not just reactively

---

## Phase 5 — Autonomy and Reduced Manual Approvals

- [ ] Define trusted-action thresholds — actions below a risk threshold execute automatically
- [ ] Reduce the daily approval list to only high-impact or novel decisions
- [ ] Introduce confidence scoring — agents self-report certainty; low-confidence items always escalate
- [ ] Full audit trail and rollback support for all autonomous actions
