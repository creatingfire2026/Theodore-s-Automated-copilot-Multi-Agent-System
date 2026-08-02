# Financial Stability Agent

## Mission

Analyze financial data daily, compute a stability score (0–100), detect risks and anomalies, run short-term projections, and surface decisions requiring human approval before any consequential action is taken.

> **⚠ Experimental Status:** The scoring formula, risk flag thresholds, and projection method described in this document are design proposals. They have not been validated against real data, calibrated for different financial situations, or tested against a defined set of pass criteria. Treat all outputs as directional estimates until simulation test cases pass and the formula is reviewed by someone with relevant financial domain expertise.

---

## Inputs

| Source | Description |
|---|---|
| Financial Data Store | Monthly income, expenses, savings, debt payments — provided in fictional form during simulation |
| Reporting Dataset | Aggregated financial trends, historical data, KPIs |
| Orchestration Agent | On-demand requests for summary or escalation trigger |

> **Data safety:** This agent must never be connected to real personal financial data until simulation tests pass. Use fictional example data from `/tests/` during development and validation.

---

## Triggers

| Trigger | Condition |
|---|---|
| Scheduled | Daily at **07:00** — feeds into the Daily Brief |
| Data event | On new row added to the financial data store |
| On-demand | On request from the Orchestration Agent |

---

## Core Logic

> ⚠ All formulas and thresholds below are experimental. They require defined test cases, normalization documentation, and calibration review before production use.

### 1. Cashflow Analysis
- Sum all income sources for the current period
- Sum all fixed and variable expenses
- Calculate net cashflow: `Income − Expenses`
- Flag negative cashflow periods

### 2. Stability Score (0–100) — Experimental Formula

| Factor | Weight | Open Question |
|---|---|---|
| Net cashflow (positive) | 30% | How is this normalized across different income scales? |
| Savings rate vs target | 25% | What is the baseline target? Is it configurable? |
| Debt-to-income ratio | 20% | Is this annualized debt or monthly? |
| Emergency fund coverage | 15% | Coverage of what expense baseline? |
| Expense trend (stable/declining) | 10% | Over what time window? What constitutes "stable"? |

Score is computed as a weighted sum; rounded to the nearest integer.

**Open questions that must be answered and documented before this formula is used in production:**
- How are factors normalized so the weighted sum reliably produces values in the 0–100 range?
- Has the formula been tested against edge cases (zero income, all expenses fixed, etc.)?
- What does a score of 70 mean in practical terms, and has that threshold been validated?

### 3. Risk Flags — Experimental Thresholds
- Net cashflow negative for 2+ consecutive periods
- Savings rate below 10%
- Debt-to-income ratio above 40%
- Emergency fund covers fewer than 3 months of expenses
- Any single expense category up more than 20% month-over-month

> These thresholds are initial design choices, not validated financial guidance. They should be reviewed and adjusted based on simulation results and domain expertise.

### 4. 90-Day Projection — Experimental Method
- Linear trend extrapolation from the last 3 months of data
- Outputs: projected balance, projected savings, projected debt payoff date

> Linear extrapolation assumes trends continue unchanged. It will produce misleading results for irregular income, seasonal expenses, or anticipated large events. This limitation must be disclosed in every projection output.

### 5. Summary Generation
- Produces a structured plain-language paragraph for inclusion in the Daily Brief
- Must include an experimental disclaimer when scoring or projection data is present

---

## Approval Checkpoints

The agent surfaces the following items as structured action records to the Orchestration Agent for human approval before execution. See [`/templates/approval-pattern.md`](../templates/approval-pattern.md) for the full action record format.

| Condition | Action Surfaced |
|---|---|
| Score drops below 80 | Adjust savings rate target |
| Overspend flag on any category | Reallocate budget category |
| Score drops below 70 | Trigger Job-Search Agent |
| Net cashflow negative | Pause non-essential subscriptions |
| Debt-to-income above 40% | Increase debt payoff allocation |

---

## Outputs

- Stability score (integer 0–100, marked experimental)
- Risk flag list (array of strings)
- 90-day projection summary (text, marked as linear extrapolation estimate)
- Action record list (structured records, for Daily Brief)
- Full structured summary (for Orchestration Agent audit log)

---

## Escalation

If the stability score falls below **70**, the agent immediately notifies the Orchestration Agent outside the normal 07:00 schedule. The Orchestration Agent triggers an unscheduled Daily Brief and marks all Financial Status items as **High Priority**.

> This threshold (70) has not been validated. It is a starting point for simulation and calibration.
