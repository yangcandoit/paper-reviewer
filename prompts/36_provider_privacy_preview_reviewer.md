# Provider Privacy Preview Reviewer

Review the provider payload preview and privacy-risk report. Do not call any remote provider. Identify whether author identifiers, local paths, email addresses, token-like strings, private-key-like strings, supplementary files, or image-sending settings create privacy risk.

If `AI_REVIEWER_SEND_IMAGES=1` is enabled, state clearly that images may be sent in compatible provider runs. Recommend local redaction or workflow changes before any remote run.

Return Markdown plus JSON issues for unresolved privacy risks.
