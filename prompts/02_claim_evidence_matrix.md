# Prompt: Claim-Evidence Matrix

Extract the manuscript's major claims and test whether the evidence supports them.

Cover claims from the title, abstract, introduction, contribution list, method motivation, result analysis, discussion, and conclusion.

Use this table:

| Claim ID | Claim | Where stated | Evidence used | Evidence sufficiency | Risk | Required fix |
|---|---|---|---|---|---|---|

Evidence sufficiency labels:

- Strong
- Adequate
- Partial
- Weak
- Missing

Rules:

1. Do not invent evidence.
2. If the claim is too strong for the evidence, recommend a safer version.
3. Mark unsupported central claims as P0 or P1 depending on severity.
4. Identify phrases such as “significant”, “consistent”, “robust”, “state-of-the-art”, “novel”, “first”, “substantial”, and check whether the manuscript proves them.

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
