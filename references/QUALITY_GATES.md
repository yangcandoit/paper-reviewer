# Quality Gates for AI-Generated Reviews

Use these gates to decide whether an AI-generated review is usable. If a review fails important gates, revise or rerun the relevant reviewer prompt before producing the meta-review.

## Gate 1: Evidence grounding

A review passes when every P0/P1 issue includes at least one evidence location:

- section;
- paragraph;
- table;
- figure;
- equation;
- appendix;
- claim;
- experimental setting;
- cited reference;
- missing source marked as requires literature verification.

Fail cases:

- "The method is unclear" without location.
- "The baselines are weak" without naming baselines.
- "Novelty is limited" without comparison target.

## Gate 2: Specificity

A review passes when comments identify concrete paper elements.

Good:

- "Table 3 supports the 10-shot claim but not the general claim that the method is consistently superior across all shot counts."

Weak:

- "More experiments are needed."

## Gate 3: Actionability

A review passes when each issue has a fix type and action.

Fix types:

- rewrite claim;
- add citation;
- add related-work comparison;
- add ablation;
- add statistical test;
- add qualitative examples;
- add failure analysis;
- add reproducibility detail;
- add limitation;
- add ethical/data statement.

## Gate 4: Novelty coverage

A review passes when it explicitly addresses:

- what the paper claims as novel;
- closest prior work or missing comparison;
- whether novelty is methodological, empirical, dataset/resource, theoretical, application, or integration;
- whether claims should be strengthened, narrowed, or re-positioned.

## Gate 5: Experiment-to-claim alignment

A review passes when it maps main experimental results to the claims they support.

Required checks:

- baseline sufficiency;
- ablation isolation;
- stability across datasets/seeds/settings;
- statistical significance or variance;
- failure cases;
- metric appropriateness;
- whether reported results justify abstract/conclusion claims.

## Gate 6: Confidence calibration

A review passes when speculative comments are labelled as low confidence and verification needs are explicit.

Use confidence labels:

- High: directly supported by manuscript evidence.
- Medium: plausible based on manuscript evidence but may need author verification.
- Low: hypothesis or concern requiring external literature/source verification.

## Gate 7: Non-duplication and conflict resolution

A review passes when similar comments are merged and conflicts across reviewers are resolved.

Examples:

- Merge "novelty unclear" and "contribution not differentiated" if they point to the same root issue.
- Resolve whether to strengthen or weaken a claim by checking evidence sufficiency.

## Gate 8: Professional tone

A review passes when it is strict but not insulting. Adversarial mode may be direct, but still must be useful.

Avoid:

- dismissive language;
- unsupported accusations;
- sarcasm;
- personal comments.

## Gate 9: Policy and confidentiality

A review passes when it respects author-side usage boundaries and does not encourage uploading confidential third-party manuscripts.

## Gate 10: Final revision-plan usability

The final plan passes when it can be executed section by section.

Each item should have:

- priority;
- section;
- issue;
- action;
- evidence;
- fix type;
- whether new experiment is needed;
- expected impact.
