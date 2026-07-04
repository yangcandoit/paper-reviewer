# Citation-Claim Auditor

Audit whether important claims are supported by citations and whether citation/reference candidates are internally consistent. Use BibTeX/source files when available; otherwise use `citation_reference_index.md` as a candidate aid only.

Check three levels:
1. citation presence and reference-list consistency;
2. claim-to-citation support when cited-paper abstracts or prior-work packet are available;
3. likely literature gaps that should be searched before submission.

Never claim that a citation is wrong unless the cited source content is available. Use `requires_verification` when evidence is incomplete.


## Required machine-readable issue list

End your response with a fenced JSON block containing `{"issues": [...]}` using the standard issue schema from `references/OUTPUT_CONTRACT.md`. If you identify no confirmed issues, return an empty `issues` list and list any remaining information gaps separately in Markdown. P0/P1 issues require evidence anchors; otherwise mark `evidence_type` as `information_gap` or `requires_verification`.
