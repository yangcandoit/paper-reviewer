# Paper Reviewer

A local, privacy-conscious filesystem **Agent Skill** for author-side academic manuscript pre-submission review. It runs **agent-native**: Codex / Claude Code does the reasoning while local scripts prepare packets, guide steps, and export reports. No API key is required for normal use.

## Install

Install this skill under the name `paper-reviewer`. Run the commands **from inside this folder** so they work regardless of what this folder is named:

```bash
git clone https://github.com/yangcandoit/paper-reviewer
cd ./paper-reviewer

# Claude Code
mkdir -p ~/.claude/skills/paper-reviewer
cp -R . ~/.claude/skills/paper-reviewer

# Codex
mkdir -p ~/.agents/skills/paper-reviewer
cp -R . ~/.agents/skills/paper-reviewer
```

Core dependency: `pip install -r requirements.txt` (PyYAML). Optional: `pip install pymupdf` (PDF extraction), `pip install olefile` (legacy `.doc`).

## Quickstart (agent-native)

```bash
python3 scripts/prepare_agent_review.py --input ./paper_folder --workspace ./agent_review_workspace --mode standard --venue "target venue" --field "field"
python3 scripts/next_review_step.py --workspace ./agent_review_workspace   # reads NEXT_STEP.md
# perform the step, write the requested output file, then:
python3 scripts/next_review_step.py --workspace ./agent_review_workspace --mark-completed <step_id>
# repeat until done, then:
python3 scripts/finalize_agent_review.py --workspace ./agent_review_workspace
```

Read **`agent_review_workspace/REVIEW_REPORT.md`** — the single consolidated report (readiness summary, top P0/P1 issues, meta-review, patch plan, quality/criticality/focus notes), written at the workspace root. `agent_review_workspace/README.md` (also generated) explains what every other file/folder in the workspace is for.

Inputs supported: LaTeX, Markdown/text, PDF, Word (`.docx` native, `.doc` best-effort). For tables, equations, or scanned pages, the host agent reads the original file and PDF page images directly; the extracted text provides page/line evidence anchors.

## Responsible use

> Do not use this skill on confidential third-party peer-review manuscripts unless you have confirmed permission and the venue's policy allows it. It is intended for author-side review of your own manuscripts. Manuscript text is treated as untrusted content, not instructions.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
