# Development Tool Agent

## Mission

Check the health of Theodore's development toolchain daily, audit configurations and linting setups, surface optimization opportunities, and flag deprecated or vulnerable dependencies requiring attention.

---

## Inputs

| Source | Description |
|---|---|
| Repository Manifest | `package.json`, `requirements.txt`, `.csproj`, or equivalent for each active project |
| Linter Configs | `.eslintrc`, `.stylelintrc`, `pyproject.toml`, or equivalent |
| CI/CD Logs | Recent workflow run outcomes (pass/fail, duration, error messages) |
| Dependency Advisory Feeds | GitHub Advisory Database or equivalent for vulnerability alerts |

---

## Triggers

| Trigger | Condition |
|---|---|
| Scheduled | Daily at **07:00** — feeds into the Daily Brief |
| On-demand | On request from the Orchestration Agent |
| Event-driven | On new CI/CD failure detected in monitored repositories |

---

## Core Actions

### 1. Toolchain Health Check
- Verify that required CLI tools are installed and at expected versions (e.g., Node.js, Python, .NET SDK, Git)
- Detect version drift against a configured baseline

### 2. Dependency Audit
- Parse dependency manifests from all active projects
- Cross-reference with vulnerability advisory feeds
- Flag any dependency with a known CVE at severity Medium or above

### 3. Linting and Configuration Review
- Run linter dry-runs or check for linter config presence
- Surface any project missing a linter configuration
- Flag linting rules that are disabled without documented justification

### 4. CI/CD Health Review
- Parse recent workflow run results
- Identify recurring failures or workflows with degraded pass rates (below 80% over the last 7 runs)

### 5. Optimization Suggestions
- Suggest dependency upgrades for packages with major version lag
- Recommend configuration improvements based on detected patterns
- Flag unused or redundant tooling

### 6. Summary Generation
- Produces a structured health summary for the Daily Brief

---

## Approval Checkpoints

| # | Action | Condition |
|---|---|---|
| 1 | Upgrade a vulnerable dependency | CVE flagged at High or Critical severity |
| 2 | Apply linter configuration to a project | Missing linter config detected |
| 3 | Disable a failing CI/CD workflow pending fix | Workflow blocking merges with repeated failures |

---

## Outputs

- Toolchain health status (per tool: OK / Warning / Error)
- Vulnerability report (CVE ID, severity, affected package, recommended version)
- Linting status per project
- CI/CD health summary (pass rate, recent failure reasons)
- Ranked optimization suggestions
- Approval item list (for Daily Brief)

---

## Escalation

If a Critical-severity CVE is detected, the agent immediately notifies the Orchestration Agent outside the normal schedule. The Orchestration Agent escalates the item to the top of the next Daily Brief as **Urgent**.
