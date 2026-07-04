# Model Agreement and Disagreement Analyzer

You receive independent reviewer outputs. Do not add new manuscript criticisms. Analyse agreement, disagreement, duplicates, and evidence quality.

For each issue:
1. identify which reviewer/model raised it;
2. group duplicate or overlapping issues;
3. compare evidence locations;
4. compare severities;
5. decide agreement category;
6. mark whether it should be included in meta-review.

Output:

| Issue group | Raised by | Agreement category | Evidence quality | Severity range | Include? | Resolution |
|---|---|---|---|---|---|---|

Agreement category: Strong agreement / Partial agreement / Complementary / Conflict / Singleton.

Do not suppress a singleton P0/P1 issue if it is well grounded.

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
