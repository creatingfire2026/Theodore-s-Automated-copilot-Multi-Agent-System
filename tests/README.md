# Test Plan — CreatingFire Agent System Lab

This directory contains simulation tests for the agent system. All tests use fictional data only. No real personal, financial, or identity information is ever used in test files.

A test is **passing** when a human has manually worked through the scenario using the agent spec documents, recorded the outputs, and confirmed every pass criterion is met. The result is committed to the test file.

---

## Required Tests for Phase 1 Validation

Phase 1 is not considered validated until all five tests below have a passing result recorded.

| Test File | Scenario | Status |
|---|---|---|
| [simulation-01-basic-daily-brief.md](simulation-01-basic-daily-brief.md) | Basic Daily Brief cycle — all agents respond, user approves all items | ⬜ Not yet run |
| [simulation-02-missing-response.md](simulation-02-missing-response.md) | No approval reply received within the 4-hour wait window | ⬜ Not yet run |
| [simulation-03-ambiguous-approval.md](simulation-03-ambiguous-approval.md) | Malformed or partial decision response from user | ⬜ Not yet run |
| [simulation-04-duplicate-execution.md](simulation-04-duplicate-execution.md) | Same action_id approved twice in one cycle | ⬜ Not yet run |
| [simulation-05-sensitive-data-protection.md](simulation-05-sensitive-data-protection.md) | Fictional data containing PII-like values; verify no sensitive data is logged or transmitted | ⬜ Not yet run |

---

## How to Run a Simulation

1. Read the test file fully before starting
2. Use the agent spec documents in `/agents/` as your logic reference
3. Work through each agent's logic manually, applying the fictional inputs
4. Record every output
5. Compare outputs against the expected results and pass criteria
6. If all criteria pass, fill in the **Result** section of the test file and commit it
7. If any criterion fails, record what failed, open an issue or update the relevant spec, and re-run

---

## Test File Format

Each test file contains:

- **Scenario** — what is being tested
- **Fictional inputs** — the data each agent receives
- **Expected outputs** — what each agent should produce
- **Approval scenario** — the fictional user decision
- **Prohibited actions** — what the system must NOT do during this test
- **Pass criteria** — the specific conditions that must be true for the test to pass
- **Result** — filled in after the test is run (date, runner, outcome per criterion)

---

## Data Safety

All test fixtures in this directory use fictional example data only. If you find any real personal, financial, or identity information committed here, remove it immediately and open a security issue.

Safe content for test files:
- Fictional names, fictional company names, fictional dollar amounts
- Example tool names and version numbers
- Constructed job listing examples

Not acceptable in test files:
- Real account numbers, real income figures, real debt balances
- Real employer names tied to real people
- Real names, addresses, SSNs, or any identity information
