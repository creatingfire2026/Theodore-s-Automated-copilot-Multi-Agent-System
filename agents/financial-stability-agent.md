# Financial Stability Agent

## Mission

Analyze Theodore's financial data daily, compute a stability score (0–100), detect risks and anomalies, run short-term projections, and surface decisions requiring human approval before any consequential action is taken.

---

## Inputs

| Source | Description |
|---|---|
| Excel Finance Workbook | Monthly income, expenses, savings, debt payments |
| Power BI Dataset | Aggregated financial trends, historical data, KPIs |
| Orchestration Agent | On-demand requests for summary or escalation trigger |

---

## Triggers

| Trigger | Condition |
|---|---|
| Scheduled | Daily at **07:00** — feeds into the Daily Brief |
| Data event | On new row added to the Excel finance workbook |
| On-demand | On request from the Orchestration Agent |

---

## Core Logic

### 1. Cashflow Analysis
- Sum all income sources for the current period
- Sum all fixed and variable expenses
- Calculate net cashflow: `Income − Expenses`
- Flag negative cashflow periods

### 2. Stability Score (0–100)
| Factor | Weight |
|---|---|
| Net cashflow (positive) | 30% |
| Savings rate vs target | 25% |
| Debt-to-income ratio | 20% |
| Emergency fund coverage | 15% |
| Expense trend (stable/declining) | 10% |

Score is computed as a weighted sum; rounded to the nearest integer.

### 3. Risk Flags
- Net cashflow negative for 2+ consecutive periods
- Savings rate below 10%
- Debt-to-income ratio above 40%
- Emergency fund covers fewer than 3 months of expenses
- Any single expense category up more than 20% month-over-month

### 4. 90-Day Projection
- Linear trend extrapolation from the last 3 months of data
- Outputs: projected balance, projected savings, projected debt payoff date

### 5. Summary Generation
- Produces a structured plain-language paragraph for inclusion in the Daily Brief

---

## Approval Checkpoints

The agent surfaces the following items to the Orchestration Agent for human approval before execution:

| # | Action | Condition |
|---|---|---|
| 1 | Adjust savings rate target | Score drops below 80 |
| 2 | Reallocate budget category | Overspend flag on any category |
| 3 | Trigger Job-Search Agent | Score drops below 70 |
| 4 | Pause non-essential subscriptions | Net cashflow negative |
| 5 | Increase debt payoff allocation | Debt-to-income above 40% |

---

## Outputs

- Stability score (integer 0–100)
- Risk flag list (array of strings)
- 90-day projection summary (text)
- Approval item list (numbered, for Daily Brief)
- Full structured summary (for Orchestration Agent log)

---

## Escalation

If the stability score falls below **70**, the agent immediately notifies the Orchestration Agent outside the normal 07:00 schedule. The Orchestration Agent triggers an unscheduled Daily Brief and marks all Financial Status items as **High Priority**.
