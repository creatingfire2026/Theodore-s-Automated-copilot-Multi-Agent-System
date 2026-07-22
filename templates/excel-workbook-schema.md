# Excel Finance Workbook Schema

This document defines the expected structure of the Excel Finance Workbook used as the primary data input for the Financial Stability Agent. The workbook must match this schema for the agent to parse and score data correctly.

**Do not commit real financial data.** Use placeholder values in any test or example files. See `CONTRIBUTING.md` for data safety guidelines.

---

## Workbook Overview

| Sheet Name | Purpose |
|---|---|
| `Income` | All income sources by month |
| `Expenses` | All expense categories by month |
| `Savings` | Savings account balances and contributions |
| `Debt` | Outstanding debt balances and payment schedule |
| `Summary` | Auto-calculated KPIs consumed by the Financial Stability Agent |

---

## Sheet: `Income`

Tracks all income sources. One row per income event per month.

| Column | Type | Required | Description | Example |
|---|---|---|---|---|
| `Date` | Date (`YYYY-MM-DD`) | ✅ | Date income was received | `2026-07-01` |
| `Source` | Text | ✅ | Name of income source | `Employer - Salary` |
| `Category` | Text | ✅ | Type of income | `Employment`, `Freelance`, `Passive`, `Other` |
| `Amount` | Currency (USD) | ✅ | Gross amount received | `4500.00` |
| `Notes` | Text | ❌ | Optional context | `July paycheck` |

---

## Sheet: `Expenses`

Tracks all spending. One row per expense event per month.

| Column | Type | Required | Description | Example |
|---|---|---|---|---|
| `Date` | Date (`YYYY-MM-DD`) | ✅ | Date expense occurred | `2026-07-03` |
| `Vendor` | Text | ✅ | Payee or vendor name | `Landlord` |
| `Category` | Text | ✅ | Expense category (see below) | `Housing` |
| `Amount` | Currency (USD) | ✅ | Amount spent | `1200.00` |
| `Fixed` | Boolean (`TRUE`/`FALSE`) | ✅ | Whether this is a fixed recurring expense | `TRUE` |
| `Notes` | Text | ❌ | Optional context | `Monthly rent` |

**Allowed Expense Categories:**

| Category | Examples |
|---|---|
| `Housing` | Rent, mortgage, utilities |
| `Transportation` | Car payment, fuel, transit pass |
| `Food` | Groceries, restaurants |
| `Healthcare` | Insurance premiums, prescriptions |
| `Subscriptions` | Streaming, SaaS, gym membership |
| `Debt Payment` | Credit card, loan payments |
| `Savings Transfer` | Transfer to savings account |
| `Personal` | Clothing, entertainment, personal care |
| `Other` | Anything not covered above |

---

## Sheet: `Savings`

Tracks savings account balances and monthly contributions.

| Column | Type | Required | Description | Example |
|---|---|---|---|---|
| `Month` | Date (`YYYY-MM-01`) | ✅ | First day of the month | `2026-07-01` |
| `Account` | Text | ✅ | Account name or label | `Emergency Fund` |
| `Opening Balance` | Currency (USD) | ✅ | Balance at start of month | `8000.00` |
| `Contributions` | Currency (USD) | ✅ | Total deposited this month | `500.00` |
| `Withdrawals` | Currency (USD) | ✅ | Total withdrawn this month | `0.00` |
| `Closing Balance` | Currency (USD) | ✅ | Balance at end of month | `8500.00` |
| `Notes` | Text | ❌ | Optional context | `Target: 3-month cover` |

---

## Sheet: `Debt`

Tracks all outstanding debt obligations.

| Column | Type | Required | Description | Example |
|---|---|---|---|---|
| `Month` | Date (`YYYY-MM-01`) | ✅ | First day of the month | `2026-07-01` |
| `Creditor` | Text | ✅ | Lender or creditor name | `Credit Union` |
| `Type` | Text | ✅ | Type of debt | `Credit Card`, `Student Loan`, `Auto Loan`, `Personal Loan`, `Other` |
| `Opening Balance` | Currency (USD) | ✅ | Balance at start of month | `3200.00` |
| `Payment Made` | Currency (USD) | ✅ | Payment made this month | `200.00` |
| `Interest Charged` | Currency (USD) | ✅ | Interest applied this month | `42.00` |
| `Closing Balance` | Currency (USD) | ✅ | Balance at end of month | `3042.00` |
| `APR` | Percentage | ✅ | Annual percentage rate | `18.99%` |
| `Notes` | Text | ❌ | Optional context | `Target payoff: Dec 2027` |

---

## Sheet: `Summary`

This sheet is **calculated automatically** from the other four sheets. The Financial Stability Agent reads from this sheet. Do not edit values here manually.

| Cell / Named Range | Formula Source | Description |
|---|---|---|
| `TotalIncome` | SUM of `Income[Amount]` for current month | Total gross income this month |
| `TotalExpenses` | SUM of `Expenses[Amount]` for current month | Total expenses this month |
| `NetCashflow` | `TotalIncome − TotalExpenses` | Net cashflow this month |
| `SavingsRate` | `SavingsTransfers / TotalIncome` | Savings rate as a percentage |
| `TotalDebt` | SUM of `Debt[Closing Balance]` for current month | Total outstanding debt |
| `DebtToIncome` | `TotalDebt / (TotalIncome × 12)` | Debt-to-income ratio |
| `EmergencyFundMonths` | `EmergencyFundBalance / AvgMonthlyExpenses` | Months of expenses covered by emergency fund |
| `StabilityScore` | Computed by Financial Stability Agent | Read-only — written back by the agent after scoring |

---

## Naming and Format Rules

- All currency values are in **USD**, formatted as numbers with 2 decimal places — no currency symbols in cells
- All dates use **`YYYY-MM-DD`** or **`YYYY-MM-01`** ISO format
- Boolean columns use Excel `TRUE` / `FALSE` (not `Yes`/`No` or `1`/`0`)
- Sheet names must match exactly — the agent uses named sheet references
- Named ranges on the `Summary` sheet must be defined using Excel's Name Manager for the agent to resolve them

---

## Data Safety Reminder

- Never enter real account numbers, SSNs, or login credentials in any cell
- Use realistic but fictional placeholder values when testing
- This workbook must never be committed to the repository — it is excluded by `.gitignore` (`*.xlsx`)
