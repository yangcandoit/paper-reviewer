# Review Revision Pass

You are revising weak AI-generated reviews after receiving quality-auditor feedback. Improve specificity, evidence anchors, actionability, severity calibration, and coverage of novelty/prior research/method/experiment/visual evidence. Preserve valid criticisms; remove or downgrade unsupported claims.

For every revised issue, explain what changed and why.


## Required machine-readable issue list

End your response with a fenced JSON block containing `{"issues": [...]}` using the standard issue schema from `references/OUTPUT_CONTRACT.md`. If you identify no confirmed issues, return an empty `issues` list and list any remaining information gaps separately in Markdown. P0/P1 issues require evidence anchors; otherwise mark `evidence_type` as `information_gap` or `requires_verification`.
