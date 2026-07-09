# Prompt: Intake and Scope Check

You are preparing an author-side pre-submission review.

First, identify the review context:

1. Manuscript title if available.
2. Field and subfield.
3. Target venue/journal/conference if available.
4. Paper type.
5. Available inputs.
6. Missing inputs that limit review quality.
7. Confidentiality status: author-owned, public, third-party confidential, or unknown.
8. Recommended review mode: quick, standard, full, or final-check.
9. Domain profile to apply.

If the manuscript appears to be a confidential third-party peer-review assignment and permission is not clear, do not review the manuscript text. Provide only a generic checklist.

Output a short intake table and then proceed only if review is appropriate.

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
