# Retrieval Provenance Policy

Prior-work search results are not ground truth. The skill must preserve provenance for every retrieved or user-provided prior-work item and must distinguish evidence levels before using an item for novelty or citation-claim judgments.

Evidence levels:

- `metadata_only`: title, authors, DOI, venue, or search-result metadata only. Requires verification.
- `abstract`: abstract-level evidence. Useful for triage, but still requires verification for strong novelty claims.
- `full_text`: local full text or extracted paper text available to the reviewer.
- `user_note`: user-provided note or manual summary. Useful context, but not independently verified.

Novelty reviewers should not conclude that a contribution is novel or not novel from metadata-only hits. Citation-claim reviewers should not conclude that a cited paper supports a claim unless adequate context is available.

## Source tags

`scripts/audit_retrieval_provenance.py` also tags each item's origin: `crossref`, `openalex` (live public metadata search, run by `scripts/search_prior_work.py` in the `prior_work_retrieval` workflow step), `agent_web_search` (the host agent's own live web search/browsing, used when available to catch very recent preprints), `user_provided`, `local`, or `manual`. `agent_web_search` items carry the same evidence-level rules as any other source: treat them as `metadata_only` unless the agent actually read and recorded the abstract or full text — do not upgrade confidence just because the agent found the item itself.
