# Review Protocol

This document defines the full pre-submission AI review protocol.

## 1. Intake and scope check

Capture:

| Field | Value |
|---|---|
| Manuscript title | |
| Field | |
| Paper type | journal / conference / thesis chapter / short paper / survey / dataset / system paper |
| Target venue | |
| Review mode | quick / standard / full / visual-citation / final-check / diagnostic / privacy-preview / revision-check / research-eval |
| Available inputs | PDF / LaTeX / Markdown / DOCX / tables / figures / references / related papers |
| Missing inputs | |
| Confidentiality constraints | author-owned / public preprint / third-party confidential / unknown |

If the manuscript is third-party confidential and the user has not confirmed permission, do not proceed with detailed review. Offer a generic review checklist instead.

## 2. Paper map

Before criticism, produce:

1. One-sentence summary.
2. Research problem.
3. Claimed gap.
4. Claimed contributions.
5. Method overview.
6. Data/datasets.
7. Baselines/comparators.
8. Metrics/evaluation criteria.
9. Main findings.
10. Stated limitations.
11. Reviewer-sensitive claims.
12. Missing information.

## 3. Claim-evidence matrix

Extract every major claim from:

- title;
- abstract;
- introduction;
- contribution list;
- method motivation;
- experiment analysis;
- discussion/conclusion.

Use this table:

| Claim ID | Claim | Where stated | Evidence used | Evidence sufficiency | Risk | Required fix |
|---|---|---|---|---|---|---|

Evidence sufficiency labels:

- Strong: directly supported by multiple results or rigorous argument.
- Adequate: supported, but could use clearer explanation.
- Partial: evidence exists but does not fully support claim strength.
- Weak: mostly asserted, under-evidenced, or vulnerable.
- Missing: no clear support found.

## 4. Specialist reviewers

### 4.1 Editor / venue-fit reviewer

Assess:

- venue scope fit;
- contribution level;
- clarity of abstract/introduction;
- whether the paper looks journal-ready;
- desk-rejection risk;
- mismatch between topic and venue expectations.

Output:

| Risk | Evidence | Why it matters | Severity | Fix |
|---|---|---|---|---|

### 4.2 Novelty and related-work reviewer

Assess each contribution:

- novelty type: theoretical / methodological / empirical / dataset / resource / application / system / integration;
- closest prior work;
- missing literature clusters;
- whether contribution is strong, moderate, incremental but acceptable, weak, or not demonstrated.

Output:

| Contribution | Evidence in manuscript | Closest prior work / required verification | Novelty level | Concern | Fix |
|---|---|---|---|---|---|

### 4.3 Method reviewer

Assess:

- method clarity;
- technical validity;
- assumptions;
- component necessity;
- reproducibility;
- implementation detail;
- whether method supports claimed contribution.

### 4.4 Experiment / evidence reviewer

Assess:

- baseline sufficiency and fairness;
- ablation validity;
- metrics;
- datasets;
- robustness;
- qualitative analysis;
- failure cases;
- generalisation;
- whether results support claims.

### 4.5 Statistics and claim-safety reviewer

Assess:

- unsupported numeric claims;
- missing variance / confidence interval / statistical tests;
- multiple-seed requirements;
- overclaiming phrases;
- cherry-picking risk;
- conclusion strength.

### 4.6 Writing and structure reviewer

Assess:

- abstract story;
- introduction funnel;
- contribution list;
- section order;
- paragraph logic;
- result explanation;
- limitation honesty;
- conclusion quality.

### 4.7 Adversarial reviewer

Find the strongest reasons a strict reviewer would reject or request major revision.

For each attack point:

| Attack point | Evidence | Fairness | Severity | Can be fixed by | Author-side response |
|---|---|---|---|---|---|

Fairness labels:

- Fair and serious.
- Fair but fixable.
- Partly fair; needs clarification.
- Unfair but likely to appear.
- Speculative; verify before acting.

### 4.8 Reproducibility, ethics, and compliance reviewer

Assess:

- code/data availability;
- dataset licensing;
- ethics approval if needed;
- AI-use disclosure if needed;
- conflict-of-interest/declarations;
- supplementary material;
- venue formatting and submission checklist;
- anonymisation requirements for double-blind review.

## 5. Conflict resolution

When reviewers disagree, produce:

| Conflict | Reviewer A | Reviewer B | Resolution | Action |
|---|---|---|---|---|

Rules:

- Prefer evidence-grounded criticism over generic praise.
- Prefer venue-specific criteria when venue is known.
- Treat novelty and evidence sufficiency as central for submission readiness.
- Do not suppress a concern merely because another reviewer was positive.

## 6. Meta-review

Produce:

1. Summary of the paper.
2. Main strengths.
3. Main weaknesses.
4. Desk-rejection risk.
5. Major-revision risk.
6. Required fixes before submission.
7. Optional improvements.
8. Readiness label.
9. Confidence and limitations.

## 7. Revision plan

Use:

| Priority | Section | Issue | Evidence | Required action | Fix type | New experiment? | Expected impact |
|---|---|---|---|---|---|---|---|

Fix types:

- Rewrite.
- Reposition contribution.
- Add citation.
- Add analysis.
- Add experiment.
- Add ablation.
- Add statistical evidence.
- Add limitation.
- Add reproducibility detail.
- Adjust claim strength.
- Improve figure/table/caption.

## 8. Patch generation protocol

When asked to rewrite, do not rewrite the whole paper at once. Patch one target section at a time.

Inputs for a patch:

1. Original text.
2. Reviewer concern.
3. Required technical facts to preserve.
4. Target venue/style.
5. Desired tone: cautious / confident / journal-style / concise.

Output:

1. Revised text.
2. What changed.
3. Which reviewer concern it addresses.
4. Any remaining evidence gap.

## 9. Final-check protocol

After revision:

| Previous issue | Status | Evidence of fix | Remaining risk | Next action |
|---|---|---|---|---|

Then give readiness label.

## Full-paper coverage protocol

Before final revision planning, ensure the review has addressed all manuscript channels:

- main text and section structure;
- claims and evidence anchors;
- PDF page/line anchors;
- figures, tables, diagrams, equations, plots, and captions;
- reference-list candidates and in-text citation markers;
- prior-work query plan and supplied prior-work packet;
- supplementary material and data/code availability statements.

Run the deterministic coverage audit before the LLM coverage auditor:

```bash
python scripts/audit_review_packet_coverage.py ./review_packet
```

The LLM coverage auditor should use `coverage/coverage_report.md`, `derived/pdf/visual_index.md`, and `derived/pdf/citation_reference_index.md` when deciding whether the review is comprehensive enough for revision planning.

## Stronger evidence-alignment protocol

When the packet contains normalized-document, citation-claim, and figure/table evidence matrices, reviewers should use the following order:

1. Use `REVIEW_PACKET_INDEX.md` and `coverage/coverage_report.md` to check coverage.
2. Use `derived/normalized_document/advanced_markdown.md` to obtain a compact overview of sections, visual items, formulas, and references.
3. Use `coverage/figure_table_evidence_matrix.md` to connect visual items to textual claims.
4. Use `coverage/citation_claim_matrix.md` to identify citation-bearing claims that need verification.
5. Use original source anchors before declaring any P0/P1 issue.

Citation support must not be declared wrong unless cited-paper abstract/full text is available. If only citation markers and reference entries are available, mark the issue as `requires_verification`.
