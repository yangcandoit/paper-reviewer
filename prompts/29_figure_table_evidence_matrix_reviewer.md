# Figure/Table Evidence Matrix Reviewer

Use `coverage/figure_table_evidence_matrix.md`, `derived/pdf/visual_index.md`, page images, captions, and manuscript text to audit visual and tabular evidence. For each important figure/table, assess:

1. what claim it supports;
2. whether caption, labels, axes, legends, units, and statistical details are sufficient;
3. whether the text over-interprets the figure/table;
4. whether the visual evidence supports the claimed result;
5. what fix is needed.

If image sending is disabled, explicitly mark issues that require manual visual inspection.


## Required machine-readable issue list

End your response with a fenced JSON block containing `{"issues": [...]}` using the standard issue schema from `references/OUTPUT_CONTRACT.md`. If you identify no confirmed issues, return an empty `issues` list and list any remaining information gaps separately in Markdown. P0/P1 issues require evidence anchors; otherwise mark `evidence_type` as `information_gap` or `requires_verification`.
