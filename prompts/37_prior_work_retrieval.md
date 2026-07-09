# Prior-Work Retrieval

You are preparing grounded prior-work evidence before the novelty and literature-gap reviewers run. Do not review the manuscript's contributions yet; this step only gathers and provenance-tags candidate prior work.

This is the only workflow step that performs outbound network calls. It must only ever send short search-query strings (titles, keywords, author names) to public bibliographic metadata endpoints. Never send manuscript full text, figures, or file bytes to any network endpoint in this step.

## Steps

1. Build (or refresh) the query plan from the packet:

   ```bash
   python3 scripts/generate_prior_work_queries.py --packet review_packet
   ```

2. Unless `AI_REVIEWER_OFFLINE=1` is set in the environment, query public metadata APIs (Crossref + OpenAlex; no API key required) from the generated query plan:

   ```bash
   python3 scripts/search_prior_work.py --from-packet review_packet --out review_packet/prior_work/candidates.json
   ```

   These endpoints are indexed continuously, so results can include work published after your own training cutoff. If the command errors (no network access, DNS failure, timeout), do not retry repeatedly — note the failure and continue to step 4 with whatever local prior-work files already exist in `review_packet/prior_work/` and `review_packet/references/`.

3. Before deciding you have no live search capability, actually check your own available tool list for a web search, browsing, or fetch tool (commonly named things like `WebSearch`, `web_search`, `browser`, `fetch`, `navigate`, or similar — the exact name depends on your runtime). Do not assume you lack one; verify by looking. This check itself must be reported in step 5's summary (see the required `Tool check` field below) — "I assumed I had no tool" is not an acceptable basis for skipping this step.

   If you do have such a tool, use it for the 3-5 highest-value query terms from `review_packet/prior_work/query_plan.md` to check for very recent related work (preprints, last 0-24 months) that Crossref/OpenAlex may not yet index. Append any genuinely relevant hits to `review_packet/prior_work/agent_search_results.json` as a JSON array of objects using this shape, one entry per hit:

   ```json
   {
     "id": "short id or DOI/arXiv id",
     "title": "...",
     "year": "...",
     "venue": "...",
     "url": "...",
     "source": "agent_web_search",
     "matched_query": "the query term that surfaced it",
     "abstract": "include only if you actually read the abstract, otherwise omit this field",
     "relationship_to_current_paper": "requires author assessment"
   }
   ```

   Do not fabricate entries. Only include items you actually found via a real search/browse action — never invent titles, DOIs, or URLs from memory. If you confirm you truly have no such tool, say so explicitly in the summary along with the tool-check evidence.

4. Build the evidence-level-tagged provenance report from everything gathered so far:

   ```bash
   python3 scripts/audit_retrieval_provenance.py review_packet
   ```

5. Write a Markdown summary to this step's output file. It must include, as explicit labeled fields (not prose you can hand-wave through):

   - `Public metadata search`: ran / skipped (`AI_REVIEWER_OFFLINE=1`) / failed (with the error).
   - `Tool check`: the specific tool names you found available (or "none found" — list what you actually checked, e.g. "checked tool list: only Read/Edit/Bash present, no web/browser/search tool").
   - `Agent web search`: used / not available / available but found nothing relevant — with the exact queries you ran if used.
   - `Candidates found`: count per evidence level (`metadata_only` / `abstract` / `full_text` / `user_note`) from `prior_work/retrieval_provenance_report.md`.
   - `Grounding gap`: state plainly if this step ends with zero grounded candidates, so the downstream novelty/literature-gap reviewers know to lean on `requires_verification` rather than asserting unverified novelty claims.

## Why this matters

Per `references/RETRIEVAL_PROVENANCE_POLICY.md`, the novelty and literature-gap reviewers must not declare a contribution novel or not novel, and must not declare a citation wrong, based on `metadata_only` hits alone. If this step finds nothing (offline, no matches, no live search tool), say so plainly in the summary so the downstream reviewers default to `requires_verification` instead of asserting unverified novelty claims.

## Output contract

Write the summary to the exact expected output path for this step. This step does not need to emit a `{"issues": [...]}` block — it is a grounding/retrieval step, not a reviewer pass.
