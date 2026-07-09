# Multi-Model Reviewer Panel Protocol

## Purpose

Multi-model review can improve robustness only if outputs remain independent and disagreements are analysed. Do not simply average model verdicts.

## Recommended panel design

Run independent reviews with separate roles or models:

1. Editor / venue fit reviewer.
2. Novelty reviewer.
3. Method reviewer.
4. Experiment reviewer.
5. Adversarial reviewer.
6. Compliance reviewer.

Optional model diversity:

- Model A: strongest reasoning model.
- Model B: long-context model for full manuscript pass.
- Model C: cheaper model for duplicate issue detection or summary.
- Local model: privacy-preserving preliminary review.

## Rules

- Do not share one model's review with another before independent review is complete. This is enforced in code, not just convention: any workflow step whose output path starts with `outputs/independent/` never receives other steps' outputs (`reviewer_core/agent_native.py::_is_independent_step`, `reviewer_core/workflow.py::render_prompt`). Such a step only ever sees the review packet and the paper-map/claim-evidence background — never another reviewer's conclusions. Synthesis/audit/calibration steps (meta-review, patch plan, severity/criticality calibrators, coverage/citation auditors, ...) are the ones meant to read the full specialist set, and do.
- Keep outputs in separate files.
- Use issue IDs and evidence locations.
- Synthesize only issues with evidence or strong reasoning.
- Preserve minority concerns if they are high severity and evidence-grounded.
- Treat agreement without evidence as weak.
- Treat disagreement as a signal to inspect evidence, not as a voting failure.

## Agreement categories

- **Strong agreement**: same issue, same evidence, same severity.
- **Partial agreement**: same issue, different severity or evidence.
- **Complementary**: different issues addressing the same broader risk.
- **Conflict**: one reviewer says claim is supported, another says unsupported.
- **Singleton**: issue raised by one reviewer only.

## Synthesis rule

A panel meta-review should include:

- all P0 issues with evidence, even if singleton;
- P1 issues raised by multiple reviewers or strongly grounded singleton issues;
- P2/P3 only when actionable and not duplicative;
- a disagreement table for unresolved conflicts.
