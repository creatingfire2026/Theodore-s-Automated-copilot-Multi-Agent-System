# Contributing to Theodore's Automated Copilot Multi-Agent System

Thank you for your interest in contributing. This system is a living blueprint — contributions that improve clarity, extend agent capabilities, or tighten the orchestration design are welcome.

---

## Repository Layout

| Directory | Purpose |
|---|---|
| `/agents` | Specification documents for each individual agent |
| `/workflows` | End-to-end workflow descriptions and orchestration maps |
| `/templates` | Reusable templates for building new agents and approval flows |
| `/diagrams` | Mermaid diagrams illustrating system architecture and data flow |

---

## Guidelines

### Markdown
- Use structured, readable Markdown throughout
- Keep headings consistent with existing agent documents (see `/templates/copilot-studio-agent-template.md`)
- Use tables for structured data (inputs, triggers, outputs)

### Data and Privacy
- **Do not commit real financial data, personal credentials, or sensitive personal information**
- Use placeholder values in any examples (e.g., `$X,XXX`, `user@example.com`)
- Never include API keys, tokens, or connection strings in any committed file

### Adding a New Agent
1. Copy `/templates/copilot-studio-agent-template.md`
2. Fill in all sections: Mission, Inputs, Triggers, Core Actions, Approval Checkpoints, Outputs, Escalation
3. Place the file in `/agents/` with a descriptive kebab-case name (e.g., `income-opportunity-agent.md`)
4. Update the orchestration diagram in `/diagrams/multi-agent-map.mermaid`
5. Add a note in `ROADMAP.md` under the relevant phase

---

## Pull Requests

- Keep PRs focused — one agent, workflow, or feature per PR
- Write a clear description explaining what changed and why
- Reference any related issue numbers in the PR body

## Issues

- Use the issue tracker to propose new agents, report documentation gaps, or discuss architectural changes
- Label issues appropriately: `agent`, `workflow`, `diagram`, `docs`, `question`
