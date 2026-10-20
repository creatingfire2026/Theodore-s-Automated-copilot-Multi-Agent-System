# Excel Finance Workbook Schema

This is the simulation data contract for the Financial Stability Agent. Do not commit real financial data.

## Workbook
`Income`, `Expenses`, `Savings`, `Debt`, `Summary`

## Income
Required: `Date`, `Source`, `Category`, `Amount`. Optional: `Notes`.

## Expenses
Required: `Date`, `Vendor`, `Category`, `Amount`, `Fixed`. Optional: `Notes`.

## Savings
Required: `Month`, `Account`, `Opening Balance`, `Contributions`, `Withdrawals`, `Closing Balance`.

## Debt
Required columns:
- `Month`
- `Creditor`
- `Type`
- `Opening Balance`
- `Minimum Payment` — contractually required monthly payment
- `Payment Made` — actual payment; may include voluntary extra payment
- `Interest Charged`
- `Closing Balance`
- `APR`

`Minimum Payment`, not `Payment Made`, is used for monthly DTI so voluntary extra payments do not artificially increase the ratio.

## Summary named ranges
- `TotalIncome` = current-month gross income
- `TotalExpenses` = current-month expenses
- `NetCashflow` = `TotalIncome - TotalExpenses`
- `SavingsRate` = current-month savings transfers / TotalIncome
- `TotalDebt` = current closing debt principal
- `MonthlyDebtPayments` = SUM of required `Debt[Minimum Payment]` for current month
- `MonthlyDTI` = `MonthlyDebtPayments / TotalIncome`; used for the 40% recurring-payment risk threshold
- `DebtToIncomeBalance` = `TotalDebt / (TotalIncome * 12)`; informational only, not used for the DTI risk flag
- `EmergencyFundMonths` = emergency fund balance / average monthly expenses
- `StabilityScore` = experimental agent output

## Format rules
- Currency: numeric, two decimal places
- Dates: ISO `YYYY-MM-DD` or `YYYY-MM-01`
- Boolean: `TRUE`/`FALSE`
- Sheet and named-range names must match exactly

## Safety
Never place account numbers, SSNs, credentials, tokens, or other secrets in the workbook. Simulation fixtures must be fictional. `*.xlsx` remains excluded from version control.