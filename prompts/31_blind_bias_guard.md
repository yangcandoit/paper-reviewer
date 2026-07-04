# Blind Review and Bias Guard

Audit whether the review or workflow may be influenced by author identity, affiliation, venue prestige, writing fluency, citation prestige, or other non-scientific signals. Recommend blind-review mode when appropriate.

If author/affiliation/funding information is present, do not use it to infer paper quality. Evaluate the manuscript based on claims, evidence, method, experiments, presentation, and reproducibility.


## Required machine-readable issue list

End your response with a fenced JSON block containing `{"issues": [...]}` using the standard issue schema from `references/OUTPUT_CONTRACT.md`. If you identify no confirmed issues, return an empty `issues` list and list any remaining information gaps separately in Markdown. P0/P1 issues require evidence anchors; otherwise mark `evidence_type` as `information_gap` or `requires_verification`.
