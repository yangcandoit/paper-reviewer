# Review Scoring Rubric

Use this rubric to evaluate the quality of AI-generated review outputs.

## Dimension 1: Evidence grounding

- 5: Every P0/P1 issue cites precise section/table/figure/equation/claim/source anchor.
- 4: Nearly all major issues have good evidence, with minor missing anchors.
- 3: Evidence is present but sometimes vague.
- 2: Many major issues are plausible but not grounded.
- 1: Review is mostly generic.

## Dimension 2: Actionability

- 5: Every issue has a concrete fix, fix type, and expected impact.
- 4: Most issues are actionable.
- 3: Fixes exist but are broad.
- 2: Many comments say "discuss more" without details.
- 1: No clear revision path.

## Dimension 3: Novelty coverage

- 5: Explicit contribution-by-prior-work matrix.
- 4: Novelty is assessed clearly but not exhaustively.
- 3: Novelty is mentioned but mixed with general method comments.
- 2: Novelty is shallow.
- 1: Novelty is missing.

## Dimension 4: Experimental adequacy coverage

- 5: Baselines, ablations, metrics, variance, data splits, and claim support are checked.
- 4: Most experimental risks are covered.
- 3: Basic result interpretation is covered.
- 2: Mostly generic comments.
- 1: Experiments are not seriously reviewed.

## Dimension 5: Severity calibration

- 5: P0/P1/P2/P3 are well-separated and proportionate.
- 4: Minor over/under severity only.
- 3: Some calibration problems.
- 2: Too many issues are major or too many real issues are minor.
- 1: Severity is unreliable.

## Dimension 6: Non-hallucination

- 5: No invented papers, results, or unsupported claims.
- 4: No major hallucinations.
- 3: A few low-impact unsupported assumptions.
- 2: Multiple unsupported claims.
- 1: Hallucinated evidence or citations drive the review.

## Minimum acceptable threshold

For a final meta-review intended to guide submission, require:

- Evidence grounding >= 4
- Actionability >= 4
- Novelty coverage >= 4
- Non-hallucination >= 4

If any dimension is below threshold, regenerate or revise the review before using it as a revision plan.
