# Safety, Confidentiality, and Responsible Use

## Intended use

This skill is for authors reviewing their own manuscripts before submission, revision, thesis examination, or public release.

## Do not use without permission

Do not use this skill to process a confidential manuscript received through peer review unless all of the following are true:

1. The user has explicit permission to use AI tools on that manuscript.
2. The target venue, publisher, or institution allows such use.
3. The user can comply with confidentiality, privacy, and data-handling requirements.

If these conditions are not met, provide only a generic review checklist that does not use the confidential manuscript text.

## AI-use disclosure

When the review produces text that may be incorporated into the manuscript, remind the author to follow the target venue's policy on generative AI disclosure. Do not state that disclosure is required unless the policy is known; instead say it may be required and should be checked.

## No fabricated scholarship

Do not invent citations, prior work, author names, results, or venue policies. Mark unverifiable claims as requiring literature or policy verification.

## Human responsibility

AI reviewer output is advisory. The author must decide which changes to make and verify every technical claim, citation, number, and policy statement.


## Code-level input sandboxing

Prompt-injection filtering is not a substitute for filesystem safety. This package treats manuscript source files as untrusted. LaTeX include resolution is restricted to the manuscript project root, and workflow outputs are restricted to the configured outputs directory. Do not remove these checks when adapting the package.

## Export safety

Reviewer-generated text is untrusted because manuscript content can influence it. CSV exports therefore escape spreadsheet-formula prefixes in `issue_tracker.csv`: values beginning with `=`, `+`, `-`, `@`, tab, or carriage return are prefixed with a single quote so spreadsheet applications treat them as literal text. JSON and Markdown exports preserve the original issue text.

## Visual asset safety

PDF visual assets are treated as manuscript content. Page render images and embedded images may contain unpublished results, figures, tables, equations, author names, reviewer-sensitive claims, or confidential information.

The workflow may create visual assets locally by default, but it does **not** send images to an OpenAI-compatible provider unless image sending is explicitly enabled with:

```bash
export AI_REVIEWER_SEND_IMAGES=1
```

Use this only with a provider and model that you are allowed to use for the manuscript. If image sending is disabled, the visual reviewer should treat image-specific findings as `information_gap` or `requires_verification` unless the images are inspected manually.
