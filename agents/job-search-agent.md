# Job-Search Agent

## Mission

Scan job boards and opportunity sources daily, filter listings by skill match and fit score, draft tailored application materials, and surface the top opportunities to the Orchestration Agent for human review and approval.

---

## Inputs

| Source | Description |
|---|---|
| Skill Profile | Theodore's current skills, certifications, and experience (maintained in a linked document) |
| Job Board Feeds | RSS or API feeds from configured job boards (e.g., LinkedIn, Indeed, GitHub Jobs) |
| Orchestration Agent | Activation signal when Financial Stability score drops below threshold |
| Preference Config | Location, remote preference, salary floor, role types, excluded industries |

---

## Triggers

| Trigger | Condition |
|---|---|
| Scheduled | Daily at **07:00** — feeds into the Daily Brief |
| Escalation | Triggered by Orchestration Agent when Financial Stability score < 70 |
| On-demand | On explicit request from the user via Orchestration Agent |

---

## Core Actions

### 1. Board Scan
- Query configured job board feeds for new listings since the last run
- Normalize listing format (title, company, location, salary, requirements)

### 2. Skill Match Scoring
- Compare each listing's requirements against the skill profile
- Compute fit score (0–100) based on keyword overlap and seniority alignment
- Discard listings below the configured minimum fit score (default: 60)

### 3. Rank and Filter
- Sort remaining listings by fit score (descending)
- Apply preference filters: location, remote flag, salary floor, excluded industries
- Select top 5 opportunities for the Daily Brief

### 4. Draft Application Materials
- For each top opportunity, generate a tailored cover letter outline
- Highlight matching skills and relevant experience
- Flag gaps between job requirements and skill profile

### 5. Summary Generation
- Produces a structured summary of the top opportunities for the Daily Brief

---

## Approval Checkpoints

| # | Action | Condition |
|---|---|---|
| 1 | Submit application for a specific role | User selects from the ranked list |
| 2 | Expand search criteria (lower fit floor, wider location) | Fewer than 3 matches found |
| 3 | Update skill profile with new skills | Agent detects a recurring missing skill across listings |

---

## Outputs

- Ranked list of top 5 job opportunities (title, company, fit score, link)
- Draft cover letter outlines (one per opportunity)
- Skill gap summary
- Approval item list (for Daily Brief)

---

## Escalation

If no matching opportunities are found for 3 consecutive days, the agent notifies the Orchestration Agent and requests a skill profile review or expansion of search criteria.
