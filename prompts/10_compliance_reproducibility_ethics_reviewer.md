# Prompt: Reproducibility, Ethics, and Compliance Reviewer

Check whether the manuscript is ready for submission from a reproducibility and compliance perspective.

Assess:

1. Code availability.
2. Data availability.
3. Dataset licences and permissions.
4. Ethics approval / consent / IRB if applicable.
5. Conflicts of interest.
6. Funding statements.
7. AI-use disclosure if applicable.
8. Double-blind anonymisation if applicable.
9. Supplementary material.
10. Venue submission checklist.
11. Figure/table permissions.
12. Reference format and completeness.

Output:

| Area | Status | Evidence | Risk | Required action |
|---|---|---|---|---|

If the target policy is unknown, say “policy verification required” rather than inventing a rule.

## Output contract

Return both:

1. A concise Markdown review using the requested tables/lists.
2. A JSON issue list following `references/OUTPUT_CONTRACT.md`.

For every P0/P1 issue, include a concrete `evidence_location`. If the location cannot be identified from the provided materials, mark it as `information_gap`, lower confidence, and do not present it as a confirmed flaw.

---

## Required output format

Produce both:

1. A concise human-readable Markdown review.
2. A fenced `json` block containing `{"issues": [...]}` that follows `references/OUTPUT_CONTRACT.md`.

For every P0/P1 issue, include a concrete evidence anchor. If evidence is not located, set `evidence_type` to `information_gap` or `requires_verification` and do not frame it as a confirmed flaw.

## Required JSON issue-list skeleton

End the response with a fenced `json` block in this exact top-level shape:

```json
{
  "issues": [
    {
      "issue_id": "ROLE-001",
      "title": "Short issue title",
      "source_reviewer": "use_this_prompt_filename_without_extension",
      "severity": "P0|P1|P2|P3",
      "confidence": "High|Medium|Low",
      "evidence_location": "section/table/figure/page/line anchor, or information_gap: ...",
      "evidence_type": "located|information_gap|requires_verification",
      "claim_attacked": "claim or manuscript element, or empty string",
      "reviewer_concern": "specific concern",
      "why_reviewer_cares": "why this matters for review",
      "fix_type": "rewrite|argumentation|new analysis|new experiment|citation|reproducibility detail|limitation|policy/compliance|verification needed|other",
      "required_action": "concrete author action",
      "new_experiment_needed": false,
      "expected_impact": "expected improvement",
      "suggested_rewrite": "optional replacement text or empty string",
      "status": "open"
    }
  ]
}
```
