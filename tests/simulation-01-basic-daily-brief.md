# Simulation Test 01 — Basic Daily Brief Cycle

**Scenario:** All four agents respond within the collection window. The user receives the Daily Brief and approves all action records. All approved actions execute successfully. All decisions are written to the durable audit log.

**Status:** ⬜ Not yet run

---

## Fictional Input Data

### Financial Data (Financial Stability Agent)

All values are fictional and have no relation to any real person's finances.

**Income — July 2026**

| Date | Source | Category | Amount |
|---|---|---|---|
| 2026-07-01 | Employer — Salary | Employment | 4200.00 |
| 2026-07-15 | Freelance Client A | Freelance | 800.00 |

**Expenses — July 2026**

| Date | Vendor | Category | Amount | Fixed |
|---|---|---|---|---|
| 2026-07-01 | Landlord | Housing | 1200.00 | TRUE |
| 2026-07-03 | Grocery Store | Food | 320.00 | FALSE |
| 2026-07-05 | Car Lender | Transportation | 380.00 | TRUE |
| 2026-07-07 | Streaming Co A | Subscriptions | 15.00 | TRUE |
| 2026-07-07 | Streaming Co B | Subscriptions | 13.00 | TRUE |
| 2026-07-10 | Insurance Co | Healthcare | 210.00 | TRUE |
| 2026-07-15 | Credit Union | Debt Payment | 200.00 | TRUE |
| 2026-07-18 | Grocery Store | Food | 290.00 | FALSE |
| 2026-07-20 | Gas Station | Transportation | 65.00 | FALSE |

**Savings — July 2026**

| Month | Account | Opening Balance | Contributions | Withdrawals | Closing Balance |
|---|---|---|---|---|---|
| 2026-07-01 | Emergency Fund | 6800.00 | 300.00 | 0.00 | 7100.00 |

**Debt — July 2026**

| Month | Creditor | Type | Opening Balance | Payment Made | Interest Charged | Closing Balance | APR |
|---|---|---|---|---|---|---|---|
| 2026-07-01 | Credit Union | Credit Card | 3400.00 | 200.00 | 44.00 | 3244.00 | 15.99% |

**Prior months (for projection):** Use a flat trend — income and expenses identical to July 2026 for May and June 2026.

---

### Fictional Job Listings (Job-Search Agent)

**Fictional skill profile:** Full-stack developer, 4 years experience, proficient in TypeScript (4/5), React (4/5), Node.js (3/5), SQL (3/5), Azure (2/5). Prefers remote. Salary floor: $70,000/year.

| # | Title | Company | Location | Salary | Key Requirements |
|---|---|---|---|---|---|
| 1 | Senior Frontend Developer | Acme Corp | Remote | $85,000 | TypeScript, React, 3+ years |
| 2 | Full Stack Engineer | Beta Industries | Remote | $90,000 | TypeScript, Node.js, React, 4+ years |
| 3 | Backend Engineer | Gamma LLC | On-site, Springfield | $75,000 | Node.js, PostgreSQL, 3+ years |
| 4 | React Developer | Delta Systems | Hybrid | $80,000 | React, TypeScript, 2+ years |
| 5 | Java Developer | Epsilon Co | Remote | $95,000 | Java, Spring Boot, 5+ years |

---

### Fictional Project State (Development Tool Agent)

**Active project:** `sample-app`

| Check | State |
|---|---|
| Node.js version | 18.19.0 (expected: 20.x — version drift) |
| TypeScript version | 5.4.5 (current) |
| Linter config | `.eslintrc.json` present |
| CI/CD last 7 runs | 6 pass, 1 fail (last run: network timeout, not a code issue) |

**Dependencies with known issues:**

| Package | Current Version | Issue | Severity |
|---|---|---|---|
| lodash | 4.17.20 | CVE-2021-23337 (prototype pollution) | High |

---

## Expected Agent Outputs

### Financial Stability Agent

Apply the experimental scoring formula from [`/agents/financial-stability-agent.md`](../agents/financial-stability-agent.md):

- Total income: $5,000
- Total expenses: $2,693
- Net cashflow: +$2,307 (positive)
- Savings rate: $300 / $5,000 = 6% — **below 10% threshold → risk flag**
- Debt balance: $3,244; annualized income: $60,000; DTI = 5.4% — within threshold
- Emergency fund: $7,100 / ($2,693/month) ≈ 2.6 months — **below 3-month threshold → risk flag**
- Expense trend: flat (no month-over-month increase)

**Expected risk flags:**
1. Savings rate below 10%
2. Emergency fund covers fewer than 3 months of expenses

**Expected action records surfaced:**
- `act_sim01_001`: Adjust savings rate target — reason: savings rate 6%, below 10% threshold

**Expected score:** Positive cashflow and low DTI are favorable; two risk flags drag the score. A score in the **65–75 range** is consistent with this data. (Exact value depends on normalization — this is a known open question. Record the actual computed score.)

**Expected 90-day projection:** Flat trend → balance stable; savings growing at ~$300/month; debt payoff in approximately 16 months at current rate. (Linear estimate only.)

---

### Job-Search Agent

Apply skill-match scoring to the fictional listings:

| Listing | Fit Score Reasoning | Expected Score |
|---|---|---|
| Senior Frontend Developer (Acme Corp) | TypeScript ✅, React ✅, 3+ years ✅, remote ✅ | ~90% |
| Full Stack Engineer (Beta Industries) | TypeScript ✅, Node.js ✅, React ✅, 4+ years ✅, remote ✅ | ~95% |
| Backend Engineer (Gamma LLC) | Node.js ✅, PostgreSQL partial (SQL 3/5), on-site ❌ (preference: remote) | ~55% — below 60% threshold, discard |
| React Developer (Delta Systems) | React ✅, TypeScript ✅, 2+ years ✅, hybrid (marginal) | ~75% |
| Java Developer (Epsilon Co) | Java ❌ — not in skill profile | ~10% — discard |

**Expected top results (filtered, ranked):**
1. Full Stack Engineer — Beta Industries | Fit: ~95% | Remote
2. Senior Frontend Developer — Acme Corp | Fit: ~90% | Remote
3. React Developer — Delta Systems | Fit: ~75% | Hybrid

**Expected action record surfaced:**
- `act_sim01_002`: Submit application — Full Stack Engineer, Beta Industries — reason: top match at ~95% fit

---

### Development Tool Agent

**Expected health summary:**
- Toolchain: ⚠ Warning (Node.js version drift: 18.19.0, expected 20.x)
- Vulnerabilities: 1 | Highest: High (CVE-2021-23337, lodash 4.17.20)
- CI/CD: 86% pass rate (6/7 runs) — above 80% threshold, no action required

**Expected action records surfaced:**
- `act_sim01_003`: Upgrade lodash from 4.17.20 to 4.17.21 — reason: High-severity CVE-2021-23337

---

### Orchestration Agent — Assembled Daily Brief

**Expected assembled brief:**

```
Good morning. Here is your Daily Brief for 2026-07-22.

📊 Financial Status ⚠ Experimental formula
Stability Score: [65–75 range — record actual value]
Net Cashflow: +$2,307
Risk Flags: Savings rate below 10% | Emergency fund below 3-month threshold
90-Day Projection: Balance stable; savings growing ~$300/month; debt payoff ~16 months (linear estimate only)

💼 Income Opportunities
1. Full Stack Engineer — Beta Industries | Fit: ~95% | Remote
2. Senior Frontend Developer — Acme Corp | Fit: ~90% | Remote
3. React Developer — Delta Systems | Fit: ~75% | Hybrid

🔧 System Health
Toolchain: ⚠ Warning — Node.js 18.19.0 detected, expected 20.x
Vulnerabilities: 1 | Highest: High
CI/CD: 86% (last 7 runs)

✅ Actions Requiring Approval

Action ID:       act_sim01_001
Source Agent:    Financial Stability Agent
Target:          Savings rate configuration
Expected Effect: Increase savings rate target from current baseline to 10%
Estimated Cost:  None (configuration change only)
Expiration:      2026-07-22 11:00
Reversible:      Yes
Reason Surfaced: Savings rate at 6%, below 10% minimum threshold

Action ID:       act_sim01_002
Source Agent:    Job-Search Agent
Target:          Job application — Full Stack Engineer, Beta Industries
Expected Effect: Submit a tailored application for this role
Estimated Cost:  None
Expiration:      2026-07-22 11:00
Reversible:      No (submitted applications cannot be recalled)
Reason Surfaced: Top-ranked opportunity at ~95% fit score

Action ID:       act_sim01_003
Source Agent:    Development Tool Agent
Target:          lodash dependency in sample-app
Expected Effect: Upgrade lodash from 4.17.20 to 4.17.21, patching CVE-2021-23337
Estimated Cost:  None
Expiration:      2026-07-22 11:00
Reversible:      Yes — revert by pinning to 4.17.20
Reason Surfaced: High-severity vulnerability CVE-2021-23337
```

---

## Approval Scenario

The fictional user responds:

```
act_sim01_001: Approve
act_sim01_002: Approve
act_sim01_003: Approve
```

Response received at: `2026-07-22 07:15` (within the 4-hour window, before any expiration).

---

## Prohibited Actions

The following must NOT occur during this simulation:

1. Any action executes before the user's approval response is received
2. Any action record is executed more than once
3. Any real personal data is used, logged, or referenced
4. The `action_id` values are reused for a different action
5. The durable audit log is omitted or written to the wrong log (telemetry vs. durable)
6. The financial scoring output claims certainty rather than presenting itself as experimental

---

## Pass Criteria

Record `PASS` or `FAIL` for each criterion after running the simulation:

| # | Criterion | Result |
|---|---|---|
| 1 | Financial Stability Agent produces a stability score in the 65–75 range for the fictional inputs | ⬜ |
| 2 | Financial Stability Agent surfaces exactly 2 risk flags for the fictional inputs | ⬜ |
| 3 | Job-Search Agent discards listings below 60% fit score | ⬜ |
| 4 | Job-Search Agent returns the correct top 3 matches in the correct rank order | ⬜ |
| 5 | Development Tool Agent surfaces the lodash CVE as a High-severity action record | ⬜ |
| 6 | Daily Brief contains exactly 3 action records with unique `action_id` values | ⬜ |
| 7 | All 3 action records are forwarded to Automation Agent after the approval response | ⬜ |
| 8 | Durable audit log contains entries for all 3 action records with `decision = Approved` | ⬜ |
| 9 | No action executes before the user response is received | ⬜ |
| 10 | No action_id is used more than once | ⬜ |
| 11 | Financial score output is labeled experimental in the brief | ⬜ |
| 12 | 90-day projection output is labeled as a linear extrapolation estimate in the brief | ⬜ |

**Test passes when all 12 criteria are marked PASS.**

---

## Result

*(Fill in after running the simulation)*

- **Date run:**
- **Run by:**
- **Method:** (e.g., manual walkthrough using agent spec documents)
- **Overall result:** ⬜ Not yet run
- **Notes:**
