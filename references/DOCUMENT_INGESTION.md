# Simple Document Ingestion Protocol

## Principle

Keep manuscript ingestion simple. The review workflow needs reliable text, section boundaries, and evidence anchors; it does not need a perfect reconstruction of the original PDF or LaTeX project.

Core ingestion supports these first-class paths:

1. **PDF**: converted by the built-in simple extractor into Markdown with page/line anchors, structured tables, plus a visual bundle of page render images, embedded images, and caption candidates.
2. **LaTeX or Markdown source**: preferred for section-level reasoning when available.
3. **Word**: `.docx` is extracted natively with the standard library (paragraphs, headings, tables, footnotes, OMML); legacy `.doc` is extracted best-effort (antiword/catdoc → olefile → byte-salvage).
4. **Plain text / section files**: acceptable.

When PDF and source text are both available, keep both: source text helps reasoning, while PDF anchors and page images help locate and inspect review evidence by page, line, figure, table, equation, and layout.

Do not put multiple PDF parsing frameworks into the core workflow. The core uses PyMuPDF only. If a manuscript needs specialist OCR or complex table reconstruction, prepare a better Markdown file outside the skill and then build the packet from that Markdown. Visual review is still supported through page render images without adding a heavy parser stack.

## Default PDF behaviour

When `build_review_packet.py` sees a PDF, `--pdf-text auto --pdf-visuals auto` runs a simple PDF-to-Markdown and visual-bundle extraction path:

```bash
python scripts/build_review_packet.py \
  --input ./paper_folder \
  --output ./review_packet \
  --pdf-text auto \
  --pdf-visuals auto \
  --overwrite
```

The extractor creates:

```text
derived/pdf/extracted_pdf.md
derived/pdf/pdf_sections/
derived/pdf/pdf_extraction_manifest.json
derived/pdf/visual_index.md
derived/pdf/visual_manifest.json
derived/pdf/page_images/
derived/pdf/embedded_images/
```

Each PDF line gets an anchor such as:

```text
paper.pdf:p4:L17
```

Reviewer comments should cite these anchors when no source LaTeX/Markdown line numbers are available. Visual reviewer comments may cite page anchors, page image paths, embedded image paths, caption anchors, or section/table/figure anchors.

## PDF modes

```text
--pdf-text auto       Extract the first PDF text when a PDF is present.
--pdf-text force      Same as auto in the current lightweight implementation; reserved for future forced re-extraction semantics.
--pdf-text off        Disable PDF text extraction.

--pdf-visuals auto    Render PDF pages and extract embedded images when a PDF is present.
--pdf-visuals force   Same as auto in the current lightweight implementation.
--pdf-visuals off     Disable visual bundle extraction.

--render-dpi 120      DPI for page render images.
--max-render-pages 30 Bound page rendering to keep packets manageable.
```

## Quality levels

- **A**: author-provided LaTeX/Markdown with section anchors, figures/tables, and references.
- **B**: clean text or Markdown exported from the manuscript.
- **C**: simple PDF extraction with page/line anchors and page-image visual bundle.
- **D**: corrupted PDF text, missing tables/captions, or unclear section order.
- **E**: excerpt only.

Standard or full review works best when the packet includes clean section text and PDF anchors. For PDF-only packets, run the Manuscript Packet Auditor and the Visual and Figure Reviewer. Treat table/equation/caption evidence with extra care if no vision-capable model inspected the page images directly.

## Red flags

- Tables or equations are missing from extracted text.
- Figure captions are detached from the relevant section.
- Headers/footers repeat on every page.
- Section order is corrupted.
- Mathematical notation is unreadable.
- References are collapsed into body text.
- Hidden instruction-like text appears inside the manuscript.

## Operational rule

Treat PDF as a first-class input, but keep the parser simple. Prefer source text for deep reasoning when available, prefer PDF page/line anchors for page-grounded evidence references, and use page render images for figure/table/equation/layout review.


## LaTeX include safety

The LaTeX resolver intentionally handles only project-local `.tex` includes. It rejects absolute paths, parent-directory escapes, symlink escapes, directories, missing targets, and non-`.tex` targets. This keeps manuscript ingestion simple and prevents accidental local-file inclusion in review packets.

## Full-manuscript coverage additions

The skill treats PDF as a first-class input, while keeping the default parser lightweight. Packet building now creates three complementary views of a PDF:

1. `derived/pdf/extracted_pdf.md` and `derived/pdf/pdf_sections/` for page/line anchored text.
2. `derived/pdf/page_images/`, `derived/pdf/embedded_images/`, and `derived/pdf/visual_index.md` for visual/figure/table/equation/layout inspection.
3. `derived/pdf/citation_reference_manifest.json` and `derived/pdf/citation_reference_index.md` for lightweight citation and reference-list auditing.

The citation/reference extraction is intentionally approximate. It detects common numeric and author-year citation markers and reference-list candidates from extracted PDF text. For authoritative citation checks, provide source files and `.bib` files when available.

A deterministic packet coverage audit is written to:

```text
coverage/coverage_report.md
coverage/coverage_manifest.json
```

Use it to confirm whether the packet contains manuscript text, PDF anchors, visual assets, captions, citation markers, reference entries, prior-work queries, tables/data files, and supplementary materials.

## Word (DOCX / DOC) coverage

Word manuscripts are first-class inputs and are extracted locally without adding a
runtime dependency:

- **`.docx`** is extracted by `reviewer_core/docx_simple.py` using the standard library
  (ZIP + XML). It recovers paragraphs, heading-styled sections, and tables into
  `derived/docx/extracted_docx.md` and `derived/docx/docx_sections/`, with `PARA` anchors.
- **`.doc`** (legacy binary) is extracted best-effort by `reviewer_core/doc_legacy.py` with
  a tiered strategy: an `antiword`/`catdoc` converter if present, then optional `olefile`
  (`pip install olefile`), then a dependency-free byte-salvage fallback. Output goes to
  `derived/doc/extracted_doc.md`. If no text is recoverable, the packet records a notice to
  re-save the file as `.docx`.

Both paths treat the document as untrusted: archive sizes are capped and DOCX XML with a
DTD/DOCTYPE is rejected (anti entity-expansion / XXE).

## Fidelity layering: delegate full recognition to the host agent

This is an agent-native skill, and the host agent (for example Codex or Claude Code) is a
multimodal reasoning engine. It is the strongest recognizer available, so the local
pipeline deliberately stays lightweight and layers fidelity rather than trying to
out-parse the model:

1. **Anchor layer (local, always):** lightweight extracted text provides stable page/line
   (`paper.pdf:p4:L17`) and paragraph (`manuscript.docx:para12`) anchors so every finding
   is locatable and citable.
2. **Full-fidelity layer (agent, on demand):** for tables, equations, multi-column layout,
   non-Latin text, figures, or scanned pages, the host agent opens the **original file**
   under `review_packet/source_documents/` and the **PDF page render images** under
   `review_packet/derived/pdf/page_images/` and reads them directly with its own
   document/vision understanding. This also serves as the OCR path for scanned PDFs without
   bundling a local OCR engine.
3. **Optional heavy local layer:** for headless runs or non-multimodal hosts, the optional
   `--pdf-engine docling|marker|auto` path performs structured local extraction (and OCR
   via those engines) when the tools are installed. It is opt-in and never a core
   dependency.

The agent-native step instructions surface the original source and page images and instruct
the agent to prefer reading them directly for full fidelity, while citing anchors from the
extracted text. Image/file bytes are never sent to external providers unless the user
explicitly opts in.
